"""Punto de entrada CLI unificado del proyecto de Web Scraping de la NTSB.

Asignatura: M2.851 - Tipología y ciclo de vida de los datos (PRA1: Web Scraping)
Institución: Universitat Oberta de Catalunya (UOC)
Autores:
    - Duván Quevedo (dquevedoagu@uoc.edu)
    - Neydor Gildardo Avila Navarrete (navilana@uoc.edu)
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
import time
from pathlib import Path

from browser import HeadlessBrowserManager
from config import DATASET_DIR, ScraperConfig, setup_logger
from detail_scraper import NTSBDetailScraper
from exporter import DatasetExporter
from html_parser import InvestigationHTMLParser
from polite_policy import ExponentialBackoffPolicy, RobotsAuditor
from search_navigator import NTSBSearchNavigator, month_ranges


def build_arg_parser() -> argparse.ArgumentParser:
    """Construye la interfaz de línea de comandos con todos los parámetros soportados."""
    parser = argparse.ArgumentParser(
        description=(
            "Scraper modular de accidentes de aviación civil de la NTSB (CAROL) "
            "con descubrimiento autónomo de enlaces y extracción HTML/DOM."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("full", "discover", "extract"),
        default="full",
        help=(
            "Modo de ejecución: 'full' (búsqueda + fichas), "
            "'discover' o 'extract' (default: full)."
        ),
    )
    parser.add_argument(
        "--date-from",
        default="2023-01-01",
        help="Fecha inicial de búsqueda en formato YYYY-MM-DD (default: 2023-01-01).",
    )
    parser.add_argument(
        "--date-to",
        default="2024-12-31",
        help="Fecha final de búsqueda en formato YYYY-MM-DD (default: 2024-12-31).",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=None,
        help=(
            "Enlaces únicos a descubrir en paginación "
            "(default: 225, o sin límite si se indica --all)."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Número de fichas detalladas a extraer desde el DOM HTML (default: 100).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="process_all",
        help=(
            "Descubre todas las páginas disponibles del rango de fechas "
            "(si no se fija --target) y extrae todas las fichas."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reanuda la extracción conservando las fichas ya presentes en el CSV.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Fuerza extracción limpia desde cero ignorando fichas previas en el CSV.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Retardo base en segundos para cortesía y backoff exponencial (default: 1.5).",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Ejecuta Chrome con interfaz gráfica visible en lugar de modo Headless.",
    )
    parser.add_argument(
        "--links-json",
        type=Path,
        default=DATASET_DIR / "expedientes_ntsb.json",
        help="Ruta del archivo JSON de enlaces descubiertos dentro de dataset/.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DATASET_DIR / "dataset_ntsb_2023_2024.csv",
        help="Ruta del archivo CSV final exportado dentro de dataset/.",
    )
    return parser


def discover_links(driver, config: ScraperConfig, backoff, logger) -> list[dict]:
    """Descubre enlaces: búsqueda única o muestreo estratificado por mes."""
    if config.per_month <= 0:
        return NTSBSearchNavigator(driver, config, backoff, logger).discover_investigations()

    all_links: list[dict] = []
    seen: set[str] = set()
    for q_from, q_to in month_ranges(config.date_from, config.date_to):
        q_config = dataclasses.replace(
            config, date_from=q_from, date_to=q_to, target_links=config.per_month
        )
        logger.info("--- Mes %s a %s (objetivo: %d) ---", q_from, q_to, config.per_month)
        navigator = NTSBSearchNavigator(driver, q_config, backoff, logger)
        for item in navigator.discover_investigations():
            if item["id"] not in seen:
                seen.add(item["id"])
                all_links.append(item)
        backoff.courtesy_pause()
    return all_links


def run_pipeline(config: ScraperConfig, mode: str) -> int:
    """Orquesta la auditoría ética, el descubrimiento multipágina y la extracción DOM."""
    logger = setup_logger()
    start_time = time.perf_counter()

    logger.info("=" * 76)
    logger.info("WEB SCRAPING NTSB (UOC M2.851) | Modo: %s", mode.upper())
    logger.info("Autores: Duván Quevedo & Neydor Gildardo Avila Navarrete")
    logger.info("User-Agent: %s", config.user_agent)
    logger.info("=" * 76)

    auditor = RobotsAuditor(config, logger)
    if not auditor.verify_permissions():
        logger.error("Abortando ejecución: robots.txt no autoriza las rutas objetivo.")
        return 1

    backoff = ExponentialBackoffPolicy(
        config=config,
        logger=logger,
        min_crawl_delay=auditor.crawl_delay,
    )
    exporter = DatasetExporter(logger)
    html_parser = InvestigationHTMLParser()

    with HeadlessBrowserManager(config, logger) as browser:
        if mode in ("full", "discover"):
            navigator = NTSBSearchNavigator(browser, config, backoff, logger)
            discovered_links = navigator.discover_investigations(
                checkpoint_fn=lambda data: exporter.save_discovered_links(
                    data,
                    config.links_json_path,
                ),
            )
            exporter.save_discovered_links(discovered_links, config.links_json_path)
        else:
            discovered_links = exporter.load_discovered_links(config.links_json_path)
            logger.info(
                "Cargados %d enlaces previos desde %s",
                len(discovered_links),
                config.links_json_path,
            )

        if mode in ("full", "extract"):
            existing_records = (
                exporter.load_existing_records(config.output_csv_path)
                if config.resume
                else []
            )
            detail_scraper = NTSBDetailScraper(
                browser=browser,
                config=config,
                backoff=backoff,
                parser=html_parser,
                logger=logger,
            )
            records = detail_scraper.scrape_batch(
                discovered_links,
                existing_records=existing_records,
                checkpoint_fn=lambda partial: exporter.export_records_to_csv(
                    partial,
                    config.output_csv_path,
                ),
            )
            exporter.export_records_to_csv(records, config.output_csv_path)

    elapsed = time.perf_counter() - start_time
    logger.info("Proceso finalizado exitosamente en %.1f segundos.", elapsed)
    return 0


def main() -> int:
    """Parsea argumentos CLI y lanza la ejecución controlada del pipeline."""
    args = build_arg_parser().parse_args()
    if args.target is not None:
        target_links: int | None = max(1, args.target)
    elif args.process_all:
        target_links = None
    else:
        target_links = 225

    # En modo 'extract' reanudamos por defecto salvo que el usuario pida '--fresh'
    should_resume = False if args.fresh else (args.resume or args.mode == "extract")

    config = ScraperConfig(
        date_from=args.date_from,
        date_to=args.date_to,
        target_links=target_links,
        per_month=max(0, args.per_month),
        detail_limit=max(1, args.limit),
        process_all=args.process_all,
        resume=should_resume,
        headless=not args.headed,
        base_delay=max(0.5, args.delay),
        links_json_path=args.links_json,
        output_csv_path=args.output_csv,
    )
    return run_pipeline(config=config, mode=args.mode)


if __name__ == "__main__":
    sys.exit(main())
