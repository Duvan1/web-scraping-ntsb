"""Políticas de uso responsable: auditoría de robots.txt y backoff exponencial.

Asignatura: M2.851 - Tipología y ciclo de vida de los datos (PRA1: Web Scraping)
Autores:
    - Duván Quevedo (dquevedoagu@uoc.edu)
    - Neydor Gildardo Avila Navarrete (navilana@uoc.edu)
"""

from __future__ import annotations

import logging
import random
import time
import urllib.robotparser
from typing import Callable, TypeVar

import requests

from config import ScraperConfig

T = TypeVar("T")


class RobotsAuditor:
    """Evalúa directivas de exclusión y Crawl-delay en el archivo robots.txt."""

    def __init__(self, config: ScraperConfig, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger
        self.crawl_delay: float | None = None

    def verify_permissions(self) -> bool:
        """Verifica que las rutas públicas de consulta e investigación estén permitidas."""
        self._logger.info("Iniciando auditoría ética de permisos en %s", self._config.robots_url)
        headers = {"User-Agent": self._config.user_agent}

        try:
            response = requests.get(self._config.robots_url, headers=headers, timeout=12)
            response.raise_for_status()
        except requests.RequestException as exc:
            self._logger.warning("No fue posible recuperar robots.txt (%s).", exc)
            return False

        parser = urllib.robotparser.RobotFileParser()
        parser.parse(response.text.splitlines())

        # Respetar Crawl-delay explícito si el servidor lo define para nuestro agente o '*'
        delay = parser.crawl_delay(self._config.user_agent) or parser.crawl_delay("*")
        if delay is not None:
            self.crawl_delay = float(delay)
            self._logger.info("Directiva Crawl-delay detectada: %.2fs", self.crawl_delay)

        checked_routes = [
            ("Portal de investigaciones públicas", "https://www.ntsb.gov/investigations/"),
            ("Buscador de aviación CAROL", self._config.search_url),
            ("Fichas técnicas de investigación", self._config.detail_base_url),
            ("Ruta interna restringida (control)", "https://www.ntsb.gov/_layouts/test.aspx"),
        ]

        public_allowed = True
        for label, target_url in checked_routes:
            allowed = parser.can_fetch(self._config.user_agent, target_url)
            status = "PERMITIDO" if allowed else "RESTRINGIDO (Disallow)"
            self._logger.info("  - %-38s -> %s", label, status)
            if "control" not in label and not allowed:
                public_allowed = False

        return public_allowed


class ExponentialBackoffPolicy:
    """Gestiona pausas de cortesía con jitter y reintentos con espera exponencial."""

    def __init__(
        self,
        config: ScraperConfig,
        logger: logging.Logger,
        min_crawl_delay: float | None = None,
    ) -> None:
        self._config = config
        self._logger = logger
        self._effective_delay = max(config.base_delay, min_crawl_delay or 0.0)

    def courtesy_pause(self, multiplier: float = 1.0) -> float:
        """Aplica una pausa base más jitter aleatorio para suavizar la carga de red."""
        jitter = random.uniform(self._config.jitter_min, self._config.jitter_max)
        wait_seconds = (self._effective_delay * multiplier) + jitter
        time.sleep(wait_seconds)
        return wait_seconds

    def run_with_backoff(self, action_name: str, operation: Callable[[], T]) -> T:
        """Ejecuta una acción aplicando backoff exponencial (base * 2^k + jitter) ante fallos."""
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries):
            try:
                return operation()
            except Exception as exc:  # noqa: BLE001 - Reintento controlado de fallos de red/DOM
                last_error = exc
                if attempt == self._config.max_retries - 1:
                    break

                jitter = random.uniform(self._config.jitter_min, self._config.jitter_max)
                backoff_wait = (
                    self._effective_delay * (self._config.backoff_factor ** attempt)
                ) + jitter
                self._logger.warning(
                    "Intento %d/%d fallido en '%s' (%s). Backoff exponencial: %.2fs...",
                    attempt + 1,
                    self._config.max_retries,
                    action_name,
                    exc.__class__.__name__,
                    backoff_wait,
                )
                time.sleep(backoff_wait)

        assert last_error is not None
        raise last_error

