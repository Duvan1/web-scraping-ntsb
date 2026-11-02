"""Navegación autónoma resiliente a fichas de la NTSB con reanudación y auto-restart.

Asignatura: M2.851 - Tipología y ciclo de vida de los datos (PRA1: Web Scraping)
Autores:
    - Duván Quevedo (dquevedoagu@uoc.edu)
    - Neydor Gildardo Avila Navarrete (navilana@uoc.edu)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from browser import HeadlessBrowserManager
from config import ScraperConfig
from html_parser import InvestigationHTMLParser
from polite_policy import ExponentialBackoffPolicy


class NTSBDetailScraper:
    """Recorre autónomamente cada URL descubierta con auto-recuperación de Chrome."""

    DETAIL_TAB_CSS = "button.information-nav-item"
    FATAL_SESSION_TOKENS = (
        "invalid session id",
        "disconnected",
        "not reachable",
        "target frame detached",
        "read timed out",
        "httpconnectionpool",
        "connection refused",
        "connection aborted",
        "session deleted",
    )

    def __init__(
        self,
        browser: HeadlessBrowserManager,
        config: ScraperConfig,
        backoff: ExponentialBackoffPolicy,
        parser: InvestigationHTMLParser,
        logger: logging.Logger,
    ) -> None:
        self._browser = browser
        self._config = config
        self._backoff = backoff
        self._parser = parser
        self._logger = logger

    def scrape_batch(
        self,
        links: list[dict[str, Any]],
        existing_records: list[dict[str, Any]] | None = None,
        checkpoint_fn: Callable[[list[dict[str, Any]]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Visita el lote con reanudación incremental, reciclaje de RAM y auto-restart."""
        batch = links if self._config.process_all else links[: self._config.detail_limit]
        total = len(batch)

        records_by_id: dict[str, dict[str, Any]] = {}
        if existing_records:
            batch_ids = {str(item.get("id", "")).strip() for item in batch}
            for rec in existing_records:
                rec_id = str(rec.get("identificador") or "").strip()
                if rec_id and rec_id in batch_ids:
                    records_by_id[rec_id] = rec

        pending = total - len(records_by_id)
        if records_by_id:
            self._logger.info(
                "Reanudando desde CSV previo: %d fichas completadas, %d pendientes (de %d).",
                len(records_by_id),
                pending,
                total,
            )
        else:
            self._logger.info("Iniciando navegación autónoma sobre %d fichas HTML...", total)

        newly_scraped = 0
        try:
            for idx, entry in enumerate(batch, start=1):
                ntsb_id = str(entry.get("id", f"ITEM_{idx}")).strip()
                if ntsb_id in records_by_id:
                    continue

                target_url = str(
                    entry.get("url") or f"{self._config.detail_base_url}?ntsbnumber={ntsb_id}"
                )

                if newly_scraped > 0:
                    if newly_scraped % self._config.recycle_browser_every == 0:
                        every = self._config.recycle_browser_every
                        self._browser.restart(
                            reason=f"reciclaje preventivo cada {every} fichas"
                        )
                    self._backoff.courtesy_pause()

                try:
                    html_source = self._backoff.run_with_backoff(
                        f"Ficha DOM {ntsb_id}",
                        lambda url=target_url: self._navigate_and_expand_dom(url),
                    )
                    record = self._parser.parse_detail_html(html_source, entry)
                    records_by_id[ntsb_id] = record
                    newly_scraped += 1

                    self._logger.info(
                        "[%4d/%4d] %s | Fecha: %-10s | Aeronave: %s %s | Estado: %s",
                        idx,
                        total,
                        ntsb_id,
                        record.get("fecha") or "N/D",
                        record.get("fabricante") or "N/D",
                        record.get("modelo") or "",
                        record.get("estado_investigacion") or "N/D",
                    )
                except Exception as exc:  # noqa: BLE001
                    self._logger.error(
                        "[%4d/%4d] No se pudo extraer la ficha %s tras reintentos (%s).",
                        idx,
                        total,
                        ntsb_id,
                        exc,
                    )

                if (
                    checkpoint_fn is not None
                    and newly_scraped > 0
                    and newly_scraped % self._config.checkpoint_every == 0
                    and idx < total
                ):
                    checkpoint_fn(self._ordered_records(batch, records_by_id))
        except KeyboardInterrupt:
            self._logger.warning(
                "Interrupción manual detectada; conservando %d fichas acumuladas.",
                len(records_by_id),
            )

        return self._ordered_records(batch, records_by_id)

    @staticmethod
    def _ordered_records(
        batch: list[dict[str, Any]],
        records_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Devuelve los registros respetando el orden cronológico del lote descubierto."""
        ordered: list[dict[str, Any]] = []
        for entry in batch:
            ntsb_id = str(entry.get("id", "")).strip()
            if ntsb_id in records_by_id:
                ordered.append(records_by_id[ntsb_id])
        return ordered

    def _navigate_and_expand_dom(self, url: str) -> str:
        """Carga la URL, hidrata el DOM y reinicia Chrome si detecta sesión caída."""
        try:
            driver = self._browser.driver
            driver.get(url)
            wait = WebDriverWait(driver, self._config.explicit_wait_seconds)
            wait.until(self._is_summary_hydrated)

            # Expandir subsecciones interactivas del DOM para montar todas las filas HTML
            tab_buttons = driver.find_elements(By.CSS_SELECTOR, self.DETAIL_TAB_CSS)
            if tab_buttons:
                for button in tab_buttons:
                    driver.execute_script("arguments[0].click();", button)
                time.sleep(0.25)

            return driver.page_source
        except Exception as exc:
            if self._needs_browser_recovery(exc):
                self._browser.restart(reason=f"auto-recuperación tras {exc.__class__.__name__}")
            raise

    def _needs_browser_recovery(self, exc: Exception) -> bool:
        """Determina si el fallo se debe a muerte, suspensión o cuelgue de chromedriver."""
        if isinstance(exc, InvalidSessionIdException):
            return True

        error_text = f"{exc.__class__.__name__}: {exc}".lower()
        if any(token in error_text for token in self.FATAL_SESSION_TOKENS):
            return True

        if isinstance(exc, WebDriverException) and not self._browser.is_session_alive():
            return True

        return not self._browser.is_session_alive()

    @staticmethod
    def _is_summary_hydrated(driver: webdriver.Chrome) -> bool:
        """Verifica que el estado asíncrono #rsStatus haya terminado de cargar."""
        status_nodes = driver.find_elements(By.ID, "rsStatus")
        if status_nodes:
            status_text = status_nodes[0].text.strip()
            if status_text and status_text not in ("Loading…", "Loading..."):
                return True

        error_nodes = driver.find_elements(By.ID, "invError")
        if error_nodes and error_nodes[0].is_displayed():
            return True

        return False
