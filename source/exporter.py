"""Exportación atómica y carga de reanudación para enlaces y dataset tabular.

Asignatura: M2.851 - Tipología y ciclo de vida de los datos (PRA1: Web Scraping)
Autores:
    - Duván Quevedo (dquevedoagu@uoc.edu)
    - Neydor Gildardo Avila Navarrete (navilana@uoc.edu)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd


class DatasetExporter:
    """Persiste y recupera artefactos de datos recolectados en dataset/."""

    COLUMN_ORDER: tuple[str, ...] = (
        "identificador",
        "fecha",
        "estado_investigacion",
        "ubicacion",
        "latitud",
        "longitud",
        "fabricante",
        "modelo",
        "matricula",
        "operador",
        "normativa_vuelo",
        "danos_aeronave",
        "fallecidos",
        "heridos_graves",
        "visibilidad_sm",
        "temperatura_f",
        "velocidad_viento_kts",
        "causa_probable",
        "url_docket",
        "url_expediente",
    )

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def save_discovered_links(self, links: list[dict[str, Any]], output_path: Path) -> None:
        """Guarda atómicamente en JSON los enlaces descubiertos en la búsqueda."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_suffix(".json.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(links, handle, indent=2, ensure_ascii=False)
        temp_path.replace(output_path)
        self._logger.info(
            "Enlaces descubiertos almacenados en %s (%d registros).",
            output_path,
            len(links),
        )

    def load_discovered_links(self, input_path: Path) -> list[dict[str, Any]]:
        """Recupera la lista de enlaces previamente descubiertos desde dataset/."""
        if not input_path.exists():
            raise FileNotFoundError(
                f"No existe el archivo de enlaces {input_path}. "
                "Ejecute primero el modo 'full' o 'discover'."
            )
        with input_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def load_existing_records(self, csv_path: Path) -> list[dict[str, Any]]:
        """Carga registros previos del CSV para reanudar ejecuciones largas sin repetir."""
        if not csv_path.exists() or csv_path.stat().st_size == 0:
            return []

        df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str)
        if df.empty or "identificador" not in df.columns:
            return []

        clean_df = df.where(pd.notna(df), None)
        records: list[dict[str, Any]] = clean_df.to_dict(orient="records")
        return [r for r in records if r.get("identificador")]

    def export_records_to_csv(
        self,
        records: list[dict[str, Any]],
        output_path: Path,
    ) -> pd.DataFrame:
        """Estructura los registros extraídos en un DataFrame y escribe CSV de forma atómica."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(records)

        if df.empty:
            df = pd.DataFrame(columns=list(self.COLUMN_ORDER))
        else:
            for col in self.COLUMN_ORDER:
                if col not in df.columns:
                    df[col] = pd.NA
            df = df[list(self.COLUMN_ORDER)]

            # Representación de tipos sin alterar ni imputar valores originales extraídos
            int_cols = ("fallecidos", "heridos_graves")
            float_cols = (
                "latitud",
                "longitud",
                "visibilidad_sm",
                "temperatura_f",
                "velocidad_viento_kts",
            )
            for col in int_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            for col in float_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

        temp_path = output_path.with_suffix(".csv.tmp")
        df.to_csv(temp_path, index=False, encoding="utf-8-sig")
        temp_path.replace(output_path)
        self._logger.info(
            "Dataset exportado en %s (%d filas x %d columnas).",
            output_path,
            len(df),
            len(df.columns),
        )
        return df
