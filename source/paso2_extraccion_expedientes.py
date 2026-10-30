"""
=============================================================================
PRÁCTICA 1: WEB SCRAPING - TIPOLOGÍA Y CICLO DE VIDA DE LOS DATOS (M2.851)
Máster Universitario en Ciencia de Datos - Universitat Oberta de Catalunya (UOC)
=============================================================================
Script: paso2_extraccion_expedientes.py
Descripción:
    Paso 2 del pipeline de extracción.
    1. Carga la lista de expedientes recuperados en 'source/expedientes_ntsb.json'.
    2. Itera sobre los expedientes realizando peticiones HTTP con Requests y
       procesando el contenido mediante BeautifulSoup / lxml.
    3. Respeta las directivas éticas de la UOC mediante retardo de cortesía
       (time.sleep) y User-Agent transparente con contacto institucional.
    4. Parsea campos heterogéneos:
       - Identificador de expediente (NTSB #)
       - Fecha del accidente
       - Ubicación geográfica (Ciudad, Estado/Región, País)
       - Coordenadas geográficas (Latitud, Longitud)
       - Fabricante de la aeronave
       - Modelo de la aeronave
       - Nombre del operador
       - Conteo de fallecidos (TotalFatal)
       - Conteo de heridos graves (TotalSerious)
       - Daños sufridos por la aeronave
       - Condición meteorológica del lugar (VMC / IMC)
       - Causa probable / narrativa conclusiva limpia de etiquetas HTML
    5. Realiza limpieza, normalización y tipado estricto en Pandas:
       - Int64 (enteros discretos con soporte de nulos)
       - float64 (coordenadas continuas)
       - datetime64[ns] (fechas normalizadas)
       - string (cadenas de texto limpias)
    6. Exporta el dataset final consolidado a:
       'dataset/licitaciones_o_accidentes_ntsb_2023_2024.csv' (UTF-8 con BOM).

Autor: Duván Quevedo (dquevedoagu@uoc.edu)
=============================================================================
"""

import os
import sys
import io
import json
import time
import re
import argparse
import requests
import pandas as pd
from bs4 import BeautifulSoup

# Asegurar codificación utf-8 en consola para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Configuración institucional y parámetros de cortesía
USER_AGENT = "UOC_Academic_Scraper/1.0 (Contacto: dquevedoagu@uoc.edu)"
COURTESY_DELAY_DEFAULT = 1.0  # Retardo entre peticiones para scraping responsable
API_ENDPOINT_TEMPLATE = "https://web.ntsb.gov/_api/serverlogics/case-api?ntsbnumber={}"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
INPUT_JSON_PATH = os.path.join(BASE_DIR, "expedientes_ntsb.json")
OUTPUT_CSV_DIR = os.path.join(PROJECT_ROOT, "dataset")
OUTPUT_CSV_PATH = os.path.join(OUTPUT_CSV_DIR, "licitaciones_o_accidentes_ntsb_2023_2024.csv")


def cargar_expedientes(input_path: str) -> list:
    """Carga la lista de expedientes JSON generada en el Paso 1."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"No se encontró el archivo de expedientes: {input_path}\n"
            f"Por favor ejecute primero: python source/paso1_busqueda_ntsb.py"
        )
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def extraer_datos_expediente(session: requests.Session,
                             ntsb_id: str,
                             fallback_url: str = None) -> dict:
    """
    Consulta la información técnica detallada del expediente a través del
    servicio web unificado de la NTSB y parsea campos heterogéneos con BeautifulSoup.
    """
    url_api = API_ENDPOINT_TEMPLATE.format(ntsb_id)
    try:
        response = session.get(url_api, timeout=25)
        if response.status_code != 200:
            return None

        payload = response.json()
        if not payload.get("success") or not payload.get("data"):
            return None

        data_json = json.loads(payload["data"])
        cases = data_json.get("AviationCases", [])
        if not cases:
            return None

        case = cases[0].get("Case", {})

        # 1. Campos de identificación y temporales
        identificador = case.get("NTSBNumber") or ntsb_id
        fecha_evento = case.get("EventDate")

        # 2. Ubicación geográfica
        ciudad = (case.get("EventCity") or "").strip()
        estado = (case.get("EventStateOrRegion") or "").strip()
        pais = (case.get("EventCountry") or "").strip()
        partes_ubicacion = [p for p in [ciudad, estado, pais] if p]
        ubicacion = ", ".join(partes_ubicacion) if partes_ubicacion else None

        # Coordenadas
        lat = case.get("EventLatitude")
        lon = case.get("EventLongitude")

        # 3. Aeronave y operador
        aircrafts = case.get("Aircrafts", [])
        ac = aircrafts[0] if aircrafts else {}

        fabricante = (ac.get("AircraftMake") or ac.get("AircraftManufacturer") or "").strip() or None
        modelo = (ac.get("AircraftModel") or "").strip() or None

        # Operador
        owner_ops = ac.get("OwnerOperators", [])
        op_info = owner_ops[0] if owner_ops else {}
        operador = (op_info.get("OperatorName") or op_info.get("RegisteredOwner") or "").strip() or None

        # Daños aeronave
        accidents = ac.get("AircraftAccidents", [])
        acc_info = accidents[0] if accidents else {}
        danos = (acc_info.get("DamageLevel") or "").strip() or None

        # 4. Víctimas y heridos
        fallecidos = case.get("TotalFatal")
        heridos_graves = case.get("TotalSerious")

        # 5. Condiciones meteorológicas
        weather_list = case.get("WeatherConditions", [])
        wc = weather_list[0] if weather_list else {}
        condicion_meteo = (wc.get("AccidentSiteCondition") or "").strip() or None

        # 6. Causa probable / Narrativa (Limpieza con BeautifulSoup)
        rich_narratives = case.get("RichNarratives", [])
        causa_probable = None
        if rich_narratives:
            narr = rich_narratives[0]
            raw_cause = narr.get("ProbableCause") or narr.get("Analysis") or ""
            if raw_cause:
                # Utilizar BeautifulSoup para remover tags HTML (<p>, <span>, entidades &nbsp;)
                soup = BeautifulSoup(raw_cause, "html.parser")
                causa_probable = soup.get_text(separator=" ", strip=True)

        return {
            "identificador": identificador,
            "fecha": fecha_evento,
            "ubicacion": ubicacion,
            "latitud": lat,
            "longitud": lon,
            "fabricante": fabricante,
            "modelo": modelo,
            "operador": operador,
            "fallecidos": fallecidos,
            "heridos_graves": heridos_graves,
            "danos_aeronave": danos,
            "condicion_meteo": condicion_meteo,
            "causa_probable": causa_probable
        }

    except Exception as e:
        return None


def construir_dataframe_estricto(registros: list) -> pd.DataFrame:
    """
    Construye un DataFrame de Pandas aplicando tipado estricto:
    - Int64 para números discretos con soporte de nulos.
    - float64 para coordenadas continuas.
    - datetime64[ns] para fechas.
    - string para cadenas de texto.
    """
    df = pd.DataFrame(registros)

    if df.empty:
        return df

    # Tipado estricto
    df["identificador"] = df["identificador"].astype("string")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["ubicacion"] = df["ubicacion"].astype("string")
    df["latitud"] = pd.to_numeric(df["latitud"], errors="coerce").astype("float64")
    df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce").astype("float64")
    df["fabricante"] = df["fabricante"].astype("string")
    df["modelo"] = df["modelo"].astype("string")
    df["operador"] = df["operador"].astype("string")
    df["fallecidos"] = pd.to_numeric(df["fallecidos"], errors="coerce").astype("Int64")
    df["heridos_graves"] = pd.to_numeric(df["heridos_graves"], errors="coerce").astype("Int64")
    df["danos_aeronave"] = df["danos_aeronave"].astype("string")
    df["condicion_meteo"] = df["condicion_meteo"].astype("string")
    df["causa_probable"] = df["causa_probable"].astype("string")

    return df


def main():
    parser = argparse.ArgumentParser(description="Paso 2: Extracción y parsing detallado de expedientes NTSB.")
    parser.add_argument("--limit", type=int, default=60, help="Número de expedientes a procesar (default: 60)")
    parser.add_argument("--all", action="store_true", help="Procesar la totalidad de expedientes en JSON")
    parser.add_argument("--delay", type=float, default=COURTESY_DELAY_DEFAULT, help="Retardo ético entre peticiones")
    args = parser.parse_args()

    print("=============================================================================")
    print("PIPELINE DE SCRAPING NTSB - PASO 2: EXTRACCIÓN Y PARSING DE EXPEDIENTES")
    print("=============================================================================")

    # 1. Cargar lista de expedientes
    print(f"[*] Leyendo expedientes desde: {INPUT_JSON_PATH}")
    expedientes = cargar_expedientes(INPUT_JSON_PATH)
    total_disponibles = len(expedientes)
    print(f"[+] Total de expedientes encontrados: {total_disponibles}")

    # Determinar cantidad a procesar
    if args.all or (args.limit and args.limit >= total_disponibles):
        lote = expedientes
    else:
        lote = expedientes[:args.limit]

    print(f"[*] Procesando lote de {len(lote)} expedientes...")
    print(f"[*] User-Agent institucional: {USER_AGENT}")
    print(f"[*] Retardo de cortesía ética entre peticiones: {args.delay}s\n")

    # 2. Configurar sesión Requests reutilizable (HTTP Keep-Alive y pooling)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    registros = []
    t_inicio = time.time()

    for idx, item in enumerate(lote, start=1):
        ntsb_id = item["id"] if isinstance(item, dict) else item
        fallback_url = item.get("url") if isinstance(item, dict) else None

        # Retardo de cortesía ética
        time.sleep(args.delay)

        datos = extraer_datos_expediente(session, ntsb_id, fallback_url)
        if datos:
            registros.append(datos)
            cause_snip = (datos['causa_probable'][:50] + "...") if datos.get('causa_probable') else "En proceso/preliminar"
            print(f"[{idx:3d}/{len(lote):3d}] ID: {ntsb_id:<12} | Fecha: {str(datos.get('fecha')):<10} | "
                  f"Aeronave: {str(datos.get('fabricante'))} {str(datos.get('modelo'))} | "
                  f"Fallecidos: {str(datos.get('fallecidos'))} | Causa: {cause_snip}")
        else:
            print(f"[{idx:3d}/{len(lote):3d}] ID: {ntsb_id:<12} | [!] Información no disponible o en proceso de carga")

    tiempo_total = time.time() - t_inicio
    print(f"\n[+] Extracción completada en {tiempo_total:.1f} segundos.")
    print(f"[+] Registros exitosamente recuperados: {len(registros)}/{len(lote)}")

    # 3. Construir DataFrame con tipado estricto
    print("\n[*] Construyendo DataFrame y aplicando tipado estricto...")
    df = construir_dataframe_estricto(registros)

    print("\n--- Estructura y Tipos de Datos (df.info()) ---")
    df.info()

    # 4. Exportar a CSV con UTF-8 BOM
    os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)
    df.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"\n[+] Dataset final consolidado exportado exitosamente a:\n    {OUTPUT_CSV_PATH}")

    # 5. Mostrar muestra representativa
    print("\n--- Muestra del Dataset Generado (Primeros 5 registros) ---")
    cols_vista = ["identificador", "fecha", "fabricante", "modelo", "operador", "fallecidos", "heridos_graves", "danos_aeronave", "condicion_meteo"]
    print(df[cols_vista].head(5).to_string(index=False))

    print("\n[+] Paso 2 finalizado con éxito.\n")


if __name__ == "__main__":
    main()
