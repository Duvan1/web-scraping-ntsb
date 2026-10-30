"""
=============================================================================
PRÁCTICA 1: WEB SCRAPING - TIPOLOGÍA Y CICLO DE VIDA DE LOS DATOS (M2.851)
Máster Universitario en Ciencia de Datos - Universitat Oberta de Catalunya (UOC)
=============================================================================
Script: paso1_busqueda_ntsb.py
Descripción:
    Paso 1 del pipeline de extracción.
    1. Audita el protocolo de exclusión de robots (robots.txt) de la NTSB con
       urllib.robotparser para certificar la autorización ética y legal.
    2. Automatiza mediante Selenium Headless (Chrome) la interacción con el
       portal de búsqueda CAROL (Aviation Search) de la NTSB.
    3. Configura los filtros temporales para accidentes del periodo 2023-2024.
    4. Gestiona la paginación dinámica en JavaScript con esperas explícitas
       (WebDriverWait) y retardos de cortesía ética (time.sleep(2.5)).
    5. Extrae una muestra masiva (>200 expedientes) y almacena las URLs e IDs
       en 'source/expedientes_ntsb.json'.

Autores: Duván Quevedo (dquevedoagu@uoc.edu), Neydor Avila (navilana@uoc.edu)
=============================================================================
"""

import os
import sys
import io
import json
import time
import re
import argparse
import urllib.robotparser
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Asegurar codificación utf-8 en consola para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Constantes de configuración metodológica y ética UOC
USER_AGENT = "UOC_Academic_Scraper/1.0 (Contacto: dquevedoagu@uoc.edu, navilana@uoc.edu)"
COURTESY_DELAY_SECONDS = 2.5
NTSB_ROBOTS_URL = "https://www.ntsb.gov/robots.txt"
NTSB_SEARCH_URL = "https://my.ntsb.gov/aviation"
DEFAULT_TARGET_RECORDS = 225  # ~9 páginas de 25 registros para superar los 200 requeridos
DATE_FROM_DEFAULT = "2023-01-01"
DATE_TO_DEFAULT = "2024-12-31"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "expedientes_ntsb.json")


def auditar_robots_txt() -> bool:
    """
    Realiza una auditoría previa de cumplimiento ético y legal consultando el
    archivo robots.txt de la NTSB mediante urllib.robotparser.
    """
    print("\n" + "=" * 75)
    print("FASE 1: AUDITORÍA ÉTICA Y DE PERMISOS (robots.txt)")
    print("=" * 75)
    print(f"[*] Consultando robots.txt: {NTSB_ROBOTS_URL}")
    print(f"[*] User-Agent institucional: {USER_AGENT}")

    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(NTSB_ROBOTS_URL, headers=headers, timeout=10)
        status_code = response.status_code
        print(f"[+] HTTP Status obtenido: {status_code}")

        if status_code != 200:
            print(f"[!] Advertencia: Código inusual al consultar robots.txt: {status_code}")

        rp = urllib.robotparser.RobotFileParser()
        rp.parse(response.text.splitlines())

        rutas_clave = [
            ("Portal de Búsqueda CAROL", "https://www.ntsb.gov/Pages/AviationQuery.aspx"),
            ("Portal de Investigaciones", "https://www.ntsb.gov/investigations/Pages/Investigations.aspx"),
            ("Ficha Técnica de Expediente", "https://www.ntsb.gov/investigations/Pages/ERA23FA109.aspx"),
            ("Ruta de Control Restringida (Disallowed)", "https://www.ntsb.gov/_layouts/test.aspx"),
        ]

        todo_permitido = True
        for descripcion, url_prueba in rutas_clave:
            permitido = rp.can_fetch(USER_AGENT, url_prueba)
            estado = "PERMITIDO [OK]" if permitido else "DENEGADO (Disallow)"
            print(f"  - {descripcion:<35} -> {estado}")
            if "Restringida" not in descripcion and not permitido:
                todo_permitido = False

        if todo_permitido:
            print("[+] Dictamen Auditoría: Las rutas objetivo de consulta pública están autorizadas.")
            return True
        else:
            print("[!] Advertencia: Alguna ruta pública presentó restricciones en robots.txt.")
            return False

    except Exception as e:
        print(f"[!] Error durante la verificación de robots.txt: {e}")
        return False


def configurar_driver_headless() -> webdriver.Chrome:
    """Configura e inicializa el navegador Chrome en modo Headless optimizado."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-agent={USER_AGENT}")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(35)
    return driver


def ejecutar_busqueda_y_paginacion(driver: webdriver.Chrome,
                                   date_from: str,
                                   date_to: str,
                                   target_records: int) -> list:
    """
    Automatiza la navegación, llenado de formulario, consulta y paginación en CAROL.
    Extrae la lista de identificadores y URLs de expedientes hasta alcanzar target_records.
    """
    print("\n" + "=" * 75)
    print("FASE 2: AUTOMATIZACIÓN DE BÚSQUEDA Y PAGINACIÓN DINÁMICA (Selenium)")
    print("=" * 75)
    print(f"[*] Navegando al buscador interactivo: {NTSB_SEARCH_URL}")
    driver.get(NTSB_SEARCH_URL)

    wait = WebDriverWait(driver, 20)

    # 1. Cerrar anuncio / modal inicial si está presente
    try:
        close_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.announcement-modal-close")))
        close_btn.click()
        print("[+] Modal de anuncio inicial cerrado exitosamente.")
    except Exception:
        print("[*] Modal de anuncio no presente o ya procesado.")

    # 2. Localizar y rellenar formulario de consulta (Rango de fechas)
    print(f"[*] Configurando rango temporal de eventos: {date_from} al {date_to}...")
    date_from_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[title="Event Date From"]')))
    date_to_input = driver.find_element(By.CSS_SELECTOR, 'input[title="Event Date To"]')

    # Despachar eventos de cambio nativos en el framework reactivo de CAROL
    driver.execute_script("""
        let inputFrom = arguments[0];
        let inputTo = arguments[1];
        let dateFrom = arguments[2];
        let dateTo = arguments[3];
        
        let setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        setter.call(inputFrom, dateFrom);
        inputFrom.dispatchEvent(new Event('input', { bubbles: true }));
        inputFrom.dispatchEvent(new Event('change', { bubbles: true }));
        
        setter.call(inputTo, dateTo);
        inputTo.dispatchEvent(new Event('input', { bubbles: true }));
        inputTo.dispatchEvent(new Event('change', { bubbles: true }));
    """, date_from_input, date_to_input, date_from, date_to)

    time.sleep(1)

    # 3. Ejecutar búsqueda
    search_btn = driver.find_element(By.CSS_SELECTOR, "button.aviation-searchpanel__button--primary")
    print("[*] Enviando formulario de búsqueda...")
    driver.execute_script("arguments[0].click();", search_btn)

    # 4. Esperar carga inicial de resultados
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr.investigation-result-row")))
    print("[+] Primera página de resultados cargada exitosamente.")

    # 5. Paginación dinámica y extracción progresiva
    expedientes = []
    ids_registrados = set()
    pagina = 1

    while len(expedientes) < target_records:
        # Extraer filas de la página actual
        rows = driver.find_elements(By.CSS_SELECTOR, "tr.investigation-result-row")
        nuevos_en_pagina = 0

        for row in rows:
            try:
                link = row.find_element(By.CSS_SELECTOR, "a")
                href = link.get_attribute("href")
                ntsb_id = link.text.strip()
                if not ntsb_id:
                    m = re.search(r"ntsbnumber=([A-Z0-9]+)", href or "")
                    ntsb_id = m.group(1) if m else None

                if ntsb_id and ntsb_id not in ids_registrados:
                    ids_registrados.add(ntsb_id)
                    expedientes.append({
                        "id": ntsb_id,
                        "url": href
                    })
                    nuevos_en_pagina += 1
            except Exception:
                continue

        print(f"  [+] Página {pagina:2d}: {nuevos_en_pagina:2d} nuevos expedientes capturados "
              f"(Total acumulado: {len(expedientes)}/{target_records})")

        if len(expedientes) >= target_records:
            break

        # Buscar y verificar botón de siguiente página
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, 'button.table-pagination__button[title="Next page"]')
            if not next_btn.is_enabled():
                print("[*] Se ha alcanzado la última página disponible en el paginador.")
                break

            # Respetar retardo de cortesía ética antes de solicitar siguiente página
            time.sleep(COURTESY_DELAY_SECONDS)

            driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
            driver.execute_script("arguments[0].click();", next_btn)

            # Esperar a que la tabla se actualice
            time.sleep(1.5)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr.investigation-result-row")))
            pagina += 1

        except Exception as e:
            print(f"[!] Fin de paginación o excepción en control: {e}")
            break

    print(f"\n[+] Total de expedientes únicos recuperados: {len(expedientes)}")
    return expedientes


def main():
    parser = argparse.ArgumentParser(description="Paso 1: Búsqueda y extracción de URLs de accidentes NTSB.")
    parser.add_argument("--date-from", default=DATE_FROM_DEFAULT, help="Fecha inicio (YYYY-MM-DD)")
    parser.add_argument("--date-to", default=DATE_TO_DEFAULT, help="Fecha fin (YYYY-MM-DD)")
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET_RECORDS, help="Número objetivo de registros")
    args = parser.parse_args()

    print("=============================================================================")
    print("PIPELINE DE SCRAPING NTSB - PASO 1: BÚSQUEDA Y PAGINACIÓN MASIVA")
    print("=============================================================================")

    # 1. Auditoría ética
    auditar_robots_txt()

    # 2. Inicialización de Selenium
    print("\n[*] Inicializando Chrome Headless...")
    driver = configurar_driver_headless()

    try:
        # 3. Búsqueda y paginación
        expedientes = ejecutar_busqueda_y_paginacion(driver, args.date_from, args.date_to, args.target)

        # 4. Guardar resultados en JSON
        with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(expedientes, f, indent=2, ensure_ascii=False)

        print(f"\n[+] Archivo de expedientes guardado exitosamente en:\n    {OUTPUT_JSON_PATH}")
        print(f"[+] Total de registros disponibles para Paso 2: {len(expedientes)}")

    finally:
        print("\n[*] Cerrando navegador headless...")
        driver.quit()
        print("[+] Paso 1 finalizado con éxito.\n")


if __name__ == "__main__":
    main()
