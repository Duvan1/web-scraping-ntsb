"""Configuración centralizada y registro estructurado para el scraper de la NTSB.

Asignatura: M2.851 - Tipología y ciclo de vida de los datos (PRA1: Web Scraping)
Institución: Universitat Oberta de Catalunya (UOC)
Autores:
    - Duván Quevedo (dquevedoagu@uoc.edu)
    - Neydor Gildardo Avila Navarrete (navilana@uoc.edu)
"""

from __future__ import annotations

import io
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SOURCE_DIR.parent
DATASET_DIR = PROJECT_ROOT / "dataset"


@dataclass(frozen=True)
class ScraperConfig:
    """Parámetros inmutables de configuración técnica, ética y de rutas."""

    user_agent: str = (
        "UOC_Academic_Scraper/1.0 "
        "(Contacto: dquevedoagu@uoc.edu, navilana@uoc.edu)"
    )
    robots_url: str = "https://www.ntsb.gov/robots.txt"
    search_url: str = "https://my.ntsb.gov/aviation"
    detail_base_url: str = "https://web.ntsb.gov/investigations/"

    date_from: str = "2023-01-01"
    date_to: str = "2024-12-31"
    target_links: int | None = 225
    detail_limit: int = 100
    process_all: bool = False
    resume: bool = False
    checkpoint_every: int = 25
    recycle_browser_every: int = 80
    headless: bool = True

    base_delay: float = 1.5
    backoff_factor: float = 2.0
    max_retries: int = 4
    jitter_min: float = 0.25
    jitter_max: float = 0.75
    page_load_timeout: int = 35
    explicit_wait_seconds: int = 20

    links_json_path: Path = DATASET_DIR / "expedientes_ntsb.json"
    output_csv_path: Path = DATASET_DIR / "dataset_ntsb_2023_2024.csv"


def setup_logger(name: str = "ntsb_scraper", level: int = logging.INFO) -> logging.Logger:
    """Configura un logger de consola UTF-8 evitando duplicación de manejadores."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    stream = sys.stdout
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    handler = logging.StreamHandler(stream)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger

