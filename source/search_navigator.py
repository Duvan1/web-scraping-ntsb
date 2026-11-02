"""Descubrimiento autónomo de enlaces y paginación dinámica en NTSB CAROL.

Asignatura: M2.851 - Tipología y ciclo de vida de los datos (PRA1: Web Scraping)
Autores:
    - Duván Quevedo (dquevedoagu@uoc.edu)
    - Neydor Gildardo Avila Navarrete (navilana@uoc.edu)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from browser import HeadlessBrowserManager
from config import ScraperConfig
from polite_policy import ExponentialBackoffPolicy


class NTSBSearchNavigator:
    """Automatiza la consulta interactiva y paginación multipágina en CAROL."""

    MODAL_CLOSE_CSS = "button.announcement-modal-close"
    DATE_FROM_CSS = 'input[title="Event Date From"]'
    DATE_TO_CSS = 'input[title="Event Date To"]'
    SEARCH_BTN_CSS = "button.aviation-searchpanel__button--primary"
    RESULT_ROW_CSS = "tr.investigation-result-row"
    NEXT_PAGE_CSS = 'button.table-pagination__button[title="Next page"]'

    def __init__(
        self,
        browser: HeadlessBrowserManager,
        config: ScraperConfig,
        backoff: ExponentialBackoffPolicy,
        logger: logging.Logger,
    ) -> None:
        self._browser = browser
        self._config = config
        self._backoff = backoff
        self._logger = logger

    @property
    def _driver(self) -> webdriver.Chrome:
        return self._browser.driver

    def _wait(self, seconds: int | None = None) -> WebDriverWait[webdriver.Chrome]:
        timeout = seconds if seconds is not None else self._config.explicit_wait_seconds
        return WebDriverWait(self._driver, timeout)

    def discover_investigations(
        self,
        checkpoint_fn: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Ejecuta la búsqueda por fechas y pagina hasta target_links o fin de páginas."""
        self._logger.info("Navegando al portal dinámico CAROL: %s", self._config.search_url)
        self._backoff.run_with_backoff(
            "Carga inicial de buscador CAROL",
            self._open_search_portal,
        )

        self._dismiss_announcement_modal()
        self._submit_date_query()

        discovered: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        page_number = 1
        target = self._config.target_links
        target_label = str(target) if target is not None else "TODOS"

        while target is None or len(discovered) < target:
            new_items = self._extract_current_page_rows(seen_ids)
            discovered.extend(new_items)

            self._logger.info(
                "Página %3d procesada: +%2d enlaces descubiertos (acumulado: %d/%s).",
                page_number,
                len(new_items),
                len(discovered),
                target_label,
            )

            if checkpoint_fn is not None and page_number % 10 == 0:
                checkpoint_fn(discovered)

            if not new_items:
                self._logger.info("Sin nuevos registros en la página actual; fin de resultados.")
                break

            if target is not None and len(discovered) >= target:
                break

            if not self._advance_to_next_page():
                self._logger.info("Fin de paginación alcanzado en la tabla de resultados.")
                break

            page_number += 1

        return discovered[:target] if target is not None else discovered

    def _open_search_portal(self) -> None:
        """Abre la URL del buscador recuperando el navegador si la sesión cayó."""
        try:
            self._driver.get(self._config.search_url)
        except Exception:
            if not self._browser.is_session_alive():
                self._browser.restart(reason="fallo al abrir buscador CAROL")
            raise

    def _dismiss_announcement_modal(self) -> None:
        """Cierra el diálogo modal emergente si el portal lo muestra al iniciar."""
        try:
            close_btn = self._wait(6).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.MODAL_CLOSE_CSS))
            )
            close_btn.click()
            self._logger.info("Modal informativo inicial cerrado.")
        except TimeoutException:
            self._logger.debug("Sin modal informativo inicial activo.")

    def _submit_date_query(self) -> None:
        """Inyecta fechas despachando eventos nativos de React y lanza la búsqueda."""
        self._logger.info(
            "Aplicando filtro temporal en DOM React: %s a %s",
            self._config.date_from,
            self._config.date_to,
        )
        input_from = self._wait().until(
            EC.presence_of_element_located((By.CSS_SELECTOR, self.DATE_FROM_CSS))
        )
        input_to = self._driver.find_element(By.CSS_SELECTOR, self.DATE_TO_CSS)

        # React controla el descriptor nativo value; despachar input/change sincroniza estado
        self._driver.execute_script(
            """
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            const applyDate = (el, val) => {
                setter.call(el, val);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            };
            applyDate(arguments[0], arguments[2]);
            applyDate(arguments[1], arguments[3]);
            """,
            input_from,
            input_to,
            self._config.date_from,
            self._config.date_to,
        )
        self._backoff.courtesy_pause(multiplier=0.5)

        search_btn = self._driver.find_element(By.CSS_SELECTOR, self.SEARCH_BTN_CSS)
        self._driver.execute_script("arguments[0].click();", search_btn)
        self._wait().until(
            EC.presence_of_element_located((By.CSS_SELECTOR, self.RESULT_ROW_CSS))
        )

    def _extract_current_page_rows(self, seen_ids: set[str]) -> list[dict[str, Any]]:
        """Parsea con BeautifulSoup las filas HTML de la página activa del buscador."""
        soup = BeautifulSoup(self._driver.page_source, "lxml")
        rows = soup.select(self.RESULT_ROW_CSS)
        extracted: list[dict[str, Any]] = []

        for row in rows:
            anchor = row.find("a", href=True)
            if anchor is None:
                continue

            href = str(anchor["href"]).strip()
            ntsb_id = anchor.get_text(strip=True)
            if not ntsb_id:
                match = re.search(r"ntsbnumber=([A-Z0-9]+)", href)
                ntsb_id = match.group(1) if match else ""

            if not ntsb_id or ntsb_id in seen_ids:
                continue

            cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
            summary_meta = self._parse_row_cells(cells)
            seen_ids.add(ntsb_id)
            extracted.append(
                {
                    "id": ntsb_id,
                    "url": href,
                    **summary_meta,
                }
            )

        return extracted

    @staticmethod
    def _parse_row_cells(cells: list[str]) -> dict[str, str | None]:
        """Extrae metadatos preliminares visibles en las celdas HTML de la tabla."""
        def cell_at(index: int) -> str | None:
            if index < len(cells) and cells[index]:
                return cells[index]
            return None

        vehicle_raw = cell_at(8)
        registration: str | None = None
        make: str | None = None
        model: str | None = None

        # Formato habitual en tabla HTML: "N3552E : CESSNA/172N"
        if vehicle_raw:
            parts = [p.strip() for p in vehicle_raw.split(":", maxsplit=1)]
            if len(parts) == 2:
                registration = parts[0] or None
                make_model = parts[1]
            else:
                make_model = parts[0]

            if "/" in make_model:
                mk, md = make_model.split("/", maxsplit=1)
                make = mk.strip() or None
                model = md.strip() or None
            elif make_model:
                make = make_model.strip()

        return {
            "table_date": cell_at(3),
            "table_location": cell_at(4),
            "table_event_type": cell_at(6),
            "table_injuries": cell_at(7),
            "table_registration": registration,
            "table_make": make,
            "table_model": model,
            "table_status": cell_at(9),
        }

    def _advance_to_next_page(self) -> bool:
        """Pulsa 'Next page' con pausa ética y verifica que el DOM actualice la tabla."""
        next_buttons = self._driver.find_elements(By.CSS_SELECTOR, self.NEXT_PAGE_CSS)
        if not next_buttons or not next_buttons[0].is_enabled():
            return False

        previous_first_id = self._read_first_row_id()
        self._backoff.courtesy_pause(multiplier=1.2)

        def click_and_wait_update() -> None:
            btn = self._driver.find_element(By.CSS_SELECTOR, self.NEXT_PAGE_CSS)
            self._driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            self._driver.execute_script("arguments[0].click();", btn)
            self._wait().until(lambda _: self._read_first_row_id() != previous_first_id)

        try:
            self._backoff.run_with_backoff(
                "Paginación React siguiente página",
                click_and_wait_update,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("No se pudo avanzar a la siguiente página (%s).", exc)
            return False

    def _read_first_row_id(self) -> str:
        """Obtiene el identificador de la primera fila visible para detectar cambios DOM."""
        rows = self._driver.find_elements(By.CSS_SELECTOR, f"{self.RESULT_ROW_CSS} a")
        return rows[0].text.strip() if rows else ""
