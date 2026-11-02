"""Gestor resiliente del navegador Selenium Chrome con auto-recuperación de sesión.

Asignatura: M2.851 - Tipología y ciclo de vida de los datos (PRA1: Web Scraping)
Autores:
    - Duván Quevedo (dquevedoagu@uoc.edu)
    - Neydor Gildardo Avila Navarrete (navilana@uoc.edu)
"""

from __future__ import annotations

import logging
from types import TracebackType

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options

from config import ScraperConfig


class HeadlessBrowserManager:
    """Context manager que gestiona, recicla y auto-recupera sesiones de Chrome."""

    def __init__(self, config: ScraperConfig, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger
        self._driver: webdriver.Chrome | None = None

    @property
    def driver(self) -> webdriver.Chrome:
        """Devuelve la instancia activa de Chrome, creándola si aún no existe."""
        if self._driver is None:
            self._driver = self._create_driver()
        return self._driver

    def __enter__(self) -> HeadlessBrowserManager:
        _ = self.driver
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def is_session_alive(self) -> bool:
        """Comprueba si el proceso chromedriver y la ventana siguen respondiendo."""
        if self._driver is None:
            return False
        try:
            _ = self._driver.current_url
            return True
        except Exception:  # noqa: BLE001
            return False

    def restart(self, reason: str = "reciclaje preventivo de memoria") -> webdriver.Chrome:
        """Cierra de forma segura cualquier sesión caída o antigua y abre una limpia."""
        self._logger.info("Reiniciando sesión de Google Chrome (%s)...", reason)
        self.close(silent=True)
        self._driver = self._create_driver()
        return self._driver

    def close(self, silent: bool = False) -> None:
        """Finaliza el navegador liberando recursos del sistema operativo."""
        if self._driver is not None:
            if not silent:
                self._logger.info("Cerrando sesión controlada de Google Chrome...")
            try:
                self._driver.quit()
            except WebDriverException:
                pass
            except Exception:  # noqa: BLE001
                pass
            finally:
                self._driver = None

    def _create_driver(self) -> webdriver.Chrome:
        """Construye una nueva instancia de Chrome optimizada para cargas largas."""
        options = Options()
        # 'eager' libera driver.get() en DOMContentLoaded sin colgarse por CDNs externos
        options.page_load_strategy = "eager"

        if self._config.headless:
            options.add_argument("--headless=new")

        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={self._config.user_agent}")
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        mode_label = "Headless" if self._config.headless else "Visible"
        self._logger.info("Inicializando navegador Google Chrome (%s)...", mode_label)
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(self._config.page_load_timeout)
        driver.set_script_timeout(self._config.explicit_wait_seconds)
        return driver
