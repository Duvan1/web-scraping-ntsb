"""Parser HTML/DOM con BeautifulSoup (lxml) para fichas individuales de la NTSB.

Asignatura: M2.851 - Tipología y ciclo de vida de los datos (PRA1: Web Scraping)
Autores:
    - Duván Quevedo (dquevedoagu@uoc.edu)
    - Neydor Gildardo Avila Navarrete (navilana@uoc.edu)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup


class InvestigationHTMLParser:
    """Extrae variables estructuradas directamente desde el HTML renderizado del DOM."""

    MAP_COORDS_RE = re.compile(r"center=([+-]?\d+(?:\.\d+)?),([+-]?\d+(?:\.\d+)?)")
    FATAL_COUNT_RE = re.compile(r"(\d+)\s+Fatal", re.IGNORECASE)
    SERIOUS_COUNT_RE = re.compile(r"(\d+)\s+Serious", re.IGNORECASE)

    def parse_detail_html(
        self,
        html: str,
        link_entry: dict[str, Any],
    ) -> dict[str, Any]:
        """Parsea una ficha HTML completa combinando el DOM de detalle y metadatos de enlace."""
        soup = BeautifulSoup(html, "lxml")
        detail_rows = self._extract_labeled_rows(soup)

        ntsb_id = (
            self._text_by_id(soup, "rsNtsbNumber")
            or detail_rows.get("NTSB Number")
            or str(link_entry.get("id", "")).strip()
        )
        status = self._text_by_id(soup, "rsStatus") or link_entry.get("table_status")

        raw_date = (
            self._text_by_id(soup, "rsDate")
            or detail_rows.get("Event Date")
            or link_entry.get("table_date")
        )
        iso_date = self._format_iso_date(raw_date)

        location = (
            self._text_by_id(soup, "rsLocation")
            or self._compose_location(detail_rows)
            or link_entry.get("table_location")
        )
        latitude, longitude = self._extract_map_coordinates(soup)

        make, model, registration = self._extract_aircraft_identity(detail_rows, link_entry)
        operator = detail_rows.get("Operator Name") or detail_rows.get("Registered Owner")
        regulation = detail_rows.get("Flight Conducted Under")
        damage = detail_rows.get("Aircraft Damage")

        fatalities, serious_injuries = self._extract_injury_counts(
            detail_rows,
            table_injury_hint=link_entry.get("table_injuries"),
        )

        probable_cause = self._extract_probable_cause(soup)
        docket_url = self._extract_docket_or_report_url(soup)

        return {
            "identificador": self._clean_placeholder(ntsb_id),
            "fecha": iso_date,
            "estado_investigacion": self._clean_placeholder(status),
            "ubicacion": self._clean_placeholder(location),
            "latitud": latitude,
            "longitud": longitude,
            "fabricante": make,
            "modelo": model,
            "matricula": registration,
            "operador": self._clean_placeholder(operator),
            "normativa_vuelo": self._clean_placeholder(regulation),
            "danos_aeronave": self._clean_placeholder(damage),
            "fallecidos": fatalities,
            "heridos_graves": serious_injuries,
            "visibilidad_sm": self._clean_placeholder(detail_rows.get("Visibility (SM)")),
            "temperatura_f": self._clean_placeholder(detail_rows.get("Temperature (F)")),
            "velocidad_viento_kts": self._clean_placeholder(detail_rows.get("Wind Speed (kts)")),
            "causa_probable": probable_cause,
            "url_docket": docket_url,
            "url_expediente": link_entry.get("url"),
        }

    @staticmethod
    def _extract_labeled_rows(soup: BeautifulSoup) -> dict[str, str]:
        """Construye un diccionario clave-valor de todas las filas de pestañas DOM."""
        extracted: dict[str, str] = {}
        selectors = ".information-item-wrapper, .investigation-details-table [role='row']"
        for row in soup.select(selectors):
            cells = row.find_all(attrs={"role": "cell"})
            if len(cells) >= 2:
                label = cells[0].get_text(" ", strip=True)
                value = cells[1].get_text("\n", strip=True)
                if label and value and label not in extracted:
                    extracted[label] = value
        return extracted

    @staticmethod
    def _text_by_id(soup: BeautifulSoup, element_id: str) -> str | None:
        element = soup.find(id=element_id)
        if element is None:
            return None
        text = element.get_text(" ", strip=True)
        return text or None

    @staticmethod
    def _clean_placeholder(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or cleaned in ("—", "-", "N/A", "Loading…", "Loading..."):
            return None
        return cleaned

    @staticmethod
    def _format_iso_date(raw_date: str | None) -> str | None:
        """Convierte fechas MM/DD/YYYY del DOM a formato estándar YYYY-MM-DD."""
        if not raw_date:
            return None
        token = raw_date.strip().split()[0]
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(token, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return raw_date.strip()

    @classmethod
    def _compose_location(cls, detail_rows: dict[str, str]) -> str | None:
        parts = [
            cls._clean_placeholder(detail_rows.get("Event City")),
            cls._clean_placeholder(detail_rows.get("Event State/Region")),
            cls._clean_placeholder(detail_rows.get("Event Country")),
        ]
        valid = [p for p in parts if p]
        return ", ".join(valid) if valid else None

    @classmethod
    def _extract_map_coordinates(cls, soup: BeautifulSoup) -> tuple[float | None, float | None]:
        """Obtiene latitud y longitud del mapa estático renderizado en #rsStaticMap."""
        map_img = soup.find(id="rsStaticMap")
        if map_img is None:
            return None, None

        src = str(map_img.get("src") or "")
        match = cls.MAP_COORDS_RE.search(src)
        if not match:
            return None, None

        try:
            return float(match.group(1)), float(match.group(2))
        except ValueError:
            return None, None

    @classmethod
    def _extract_aircraft_identity(
        cls,
        detail_rows: dict[str, str],
        link_entry: dict[str, Any],
    ) -> tuple[str | None, str | None, str | None]:
        """Resuelve fabricante, modelo y matrícula desde pestañas DOM o Vehicle Details."""
        make = cls._clean_placeholder(detail_rows.get("Aircraft Make"))
        model = cls._clean_placeholder(detail_rows.get("Aircraft Model / Aircraft Series"))
        registration = cls._clean_placeholder(detail_rows.get("Registration"))

        if not make and "Vehicle Details" in detail_rows:
            first_vehicle = detail_rows["Vehicle Details"].splitlines()[0].strip()
            parts = [p.strip() for p in first_vehicle.split(":", maxsplit=1)]
            if len(parts) == 2:
                registration = registration or (parts[0] or None)
                make_model = parts[1]
            else:
                make_model = parts[0]
            if "/" in make_model:
                mk, md = make_model.split("/", maxsplit=1)
                make = mk.strip() or None
                model = model or (md.strip() or None)

        return (
            make or cls._clean_placeholder(link_entry.get("table_make")),
            model or cls._clean_placeholder(link_entry.get("table_model")),
            registration or cls._clean_placeholder(link_entry.get("table_registration")),
        )

    @classmethod
    def _extract_injury_counts(
        cls,
        detail_rows: dict[str, str],
        table_injury_hint: str | None,
    ) -> tuple[int | None, int | None]:
        """Suma fallecidos y heridos graves desglosados en tripulación, pasajeros y tierra."""
        injury_keys = ("Crew Injuries", "Passenger Injuries", "Ground Injuries")
        present_blocks = [detail_rows[k] for k in injury_keys if k in detail_rows]

        if present_blocks:
            fatal_total = 0
            serious_total = 0
            for block in present_blocks:
                fatal_total += sum(int(m) for m in cls.FATAL_COUNT_RE.findall(block))
                serious_total += sum(int(m) for m in cls.SERIOUS_COUNT_RE.findall(block))
            return fatal_total, serious_total

        if table_injury_hint and table_injury_hint.strip().lower() in ("none", "minor"):
            return 0, 0

        return None, None

    @classmethod
    def _extract_probable_cause(cls, soup: BeautifulSoup) -> str | None:
        """Extrae y sanea de HTML el texto oficial de 'What We Found' / causa probable."""
        candidate_selectors = (
            "section#whatWeFoundSection div.investigation-narrative",
            "#majorWhatWeFound",
            "#probable-cause-narrative",
        )
        for selector in candidate_selectors:
            for node in soup.select(selector):
                text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
                cleaned = cls._clean_placeholder(text)
                if cleaned:
                    return cleaned
        return None

    @staticmethod
    def _extract_docket_or_report_url(soup: BeautifulSoup) -> str | None:
        """Obtiene el hipervínculo público al Docket o informe PDF si figura en la ficha."""
        anchors = soup.select("#rsDocketLinks a[href], #rsReportLinks a[href]")
        for anchor in anchors:
            href = str(anchor.get("href") or "").strip()
            if "data.ntsb.gov" in href:
                return href
        for anchor in anchors:
            href = str(anchor.get("href") or "").strip()
            if href.startswith("http"):
                return href
        return None

