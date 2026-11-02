"""Gestor de ciclo de vida del navegador Selenium Chrome para navegación autónoma.

Asignatura: M2.851 - Tipología y ciclo de vida de los datos (PRA1: Web Scraping)
Autores:
    - Duván Quevedo (dquevedoagu@uoc.edu)
    - Neydor Gildardo Avila Navarrete (navilana@uoc.edu)
"""

from __future__ import annotations

import logging
from types import TracebackType

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from config import ScraperConfig


class HeadlessBrowserManager:
    """Context manager que encapsula la sesión de Chrome y garantiza su cierre limpio."""

    def __init__(self, config: ScraperConfig, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger
        self._driver: webdriver.Chrome | None = None

    def __enter__(self) -> webdriver.Chrome:
        options = Options()
        if self._config.headless:
            options.add_argument("--headless=new")

        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={self._config.user_agent}")
        options.add_argument("--log-level=3")
        # Desactivar descarga de fuentes/multimedia innecesarias sin afectar el DOM JS
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        mode_label = "Headless" if self._config.headless else "Visible"
        self._logger.info("Inicializando navegador Google Chrome (%s)...", mode_label)
        self._driver = webdriver.Chrome(options=options)
        self._driver.set_page_load_timeout(self._config.page_load_timeout)
        return self._driver

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._driver is not None:
            self._logger.info("Cerrando sesión controlada de Google Chrome...")
            self._driver.quit()
            self._driver = None

