"""Navegación autónoma a fichas individuales de la NTSB y extracción desde el DOM.

Asignatura: M2.851 - Tipología y ciclo de vida de los datos (PRA1: Web Scraping)
Autores:
    - Duván Quevedo (dquevedoagu@uoc.edu)
    - Neydor Gildardo Avila Navarrete (navilana@uoc.edu)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from config import ScraperConfig
from html_parser import InvestigationHTMLParser
from polite_policy import ExponentialBackoffPolicy


class NTSBDetailScraper:
    """Recorre autónomamente cada URL descubierta, hidrata sus pestañas y parsea el DOM."""

    DETAIL_TAB_CSS = "button.information-nav-item"

    def __init__(
        self,
        driver: webdriver.Chrome,
        config: ScraperConfig,
        backoff: ExponentialBackoffPolicy,
        parser: InvestigationHTMLParser,
        logger: logging.Logger,
    ) -> None:
        self._driver = driver
        self._config = config
        self._backoff = backoff
        self._parser = parser
        self._logger = logger

    def scrape_batch(self, links: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Visita el lote seleccionado de enlaces aplicando backoff exponencial y jitter."""
        batch = links if self._config.process_all else links[: self._config.detail_limit]
        total = len(batch)
        self._logger.info("Iniciando navegación autónoma sobre %d fichas HTML...", total)

        records: list[dict[str, Any]] = []
        for idx, entry in enumerate(batch, start=1):
            ntsb_id = str(entry.get("id", f"ITEM_{idx}"))
            target_url = str(
                entry.get("url") or f"{self._config.detail_base_url}?ntsbnumber={ntsb_id}"
            )

            if idx > 1:
                self._backoff.courtesy_pause()

            try:
                html_source = self._backoff.run_with_backoff(
                    f"Ficha DOM {ntsb_id}",
                    lambda url=target_url: self._navigate_and_expand_dom(url),
                )
                record = self._parser.parse_detail_html(html_source, entry)
                records.append(record)
                self._logger.info(
                    "[%3d/%3d] %s | Fecha: %-10s | Aeronave: %s %s | Estado: %s",
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
                    "[%3d/%3d] No se pudo extraer la ficha %s tras reintentos (%s).",
                    idx,
                    total,
                    ntsb_id,
                    exc,
                )

        return records

    def _navigate_and_expand_dom(self, url: str) -> str:
        """Carga la URL de la investigación, espera hidratación JS y despliega pestañas."""
        self._driver.get(url)
        wait = WebDriverWait(self._driver, self._config.explicit_wait_seconds)
        wait.until(self._is_summary_hydrated)

        # Expandir subsecciones interactivas del DOM para montar todas las filas HTML
        tab_buttons = self._driver.find_elements(By.CSS_SELECTOR, self.DETAIL_TAB_CSS)
        if tab_buttons:
            for button in tab_buttons:
                self._driver.execute_script("arguments[0].click();", button)
            time.sleep(0.25)

        return self._driver.page_source

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
