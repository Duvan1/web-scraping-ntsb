# Web Scraping de Accidentes e Incidentes de Aviación Civil (NTSB)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23811523.svg)](https://doi.org/10.5281/zenodo.23811523)

**Práctica 1: Web Scraping**  
**Asignatura:** M2.851 - Tipología y ciclo de vida de los datos  
**Titulación:** Máster Universitario en Ciencia de Datos  
**Institución:** Universitat Oberta de Catalunya (UOC)  
**DOI del Dataset (Zenodo):** [10.5281/zenodo.23811523](https://doi.org/10.5281/zenodo.23811523)  

---

## 1. Integrantes del Grupo

* **Duván Quevedo** — `dquevedoagu@uoc.edu`
* **Neydor Gildardo Avila Navarrete** — `navilana@uoc.edu`

---

## 2. Descripción General del Proyecto

### 2.1. Contexto del Sitio Web Objetivo

Este proyecto implementa un pipeline robusto, modular y reproducible de **Web Scraping** para la recolección, estructuración y normalización de información sobre accidentes e incidentes de aviación civil investigados por la **NTSB (*National Transportation Safety Board*)** de los Estados Unidos, correspondientes al periodo 2023-2024.

La arquitectura de recolección se articula en una estrategia metodológica desacoplada en **dos paginas webs dínamicas**:

1. **Paso 1 o modo discover (Selenium Headless - Navegación y Paginación Dinámica):**  Automatización de la consulta interactiva en el portal público [NTSB CAROL (Aviation Search)](https://my.ntsb.gov/aviation), gestionando filtros temporales, interacción DOM, modales asíncronos y paginación reactiva en JavaScript mediante esperas explícitas (`WebDriverWait`).
**Paso 2 o modo extract (Requests + BeautifulSoup / lxml - Extracción Técnica y Tipado):** Consumo estructurado de los expedientes mediante peticiones HTTP optimizadas (<https://web.ntsb.gov/investigations/>). Cada enlace descubierto conduce a una página dinámica cuyo contenido (resumen del expediente, mapa georreferenciado, narrativa de causa probable, enlaces al *Docket* documental y 7 pestañas desplegables de información técnica) se hidrata asíncronamente en el DOM mediante JavaScript.

---

## 3. Publicación del Dataset en Zenodo

El conjunto de datos resultante se encuentra publicado en abierto en el repositorio científico **Zenodo**:

* **Título del nodo:** *NTSB Civil Aviation Accident Dataset (2023-2024)*
* **Identificador DOI:** [`10.5281/zenodo.23811523`](https://doi.org/10.5281/zenodo.23811523)
* **URL directa del registro:** [https://zenodo.org/records/23811523](https://zenodo.org/records/23811523)
* **Autores:** Duván Quevedo y Neydor Gildardo Avila Navarrete
* **Licencia de los datos:** Creative Commons CC0 1.0 Universal (*Public Domain Dedication*)

---

## 4. Estructura y Descripción de los Archivos del Repositorio

El repositorio cumple estrictamente la separación entre código fuente (`source/`) y datos extraídos (`dataset/`), siguiendo principios de **Clean Code**, **PEP 8** y programación modular orientada a objetos:

```text
web-scraping-ntsb/
├── .gitignore                        # Exclusiones de Git (entornos virtuales, temporales)
├── README.md                         # Documentación técnica, ética y guía de replicación
├── dataset/                          
│   ├── expedientes_ntsb.json         # Muestra masiva de URLs e identificadores recuperados
│   └── dataset_ntsb_2023_2024.csv    # Dataset tabular extraído desde el DOM HTML de las fichas
└── source/
    ├── requirements.txt              # Especificación de dependencias de Python
    ├── config.py                     # Clase ScraperConfig (dataclass) y configuración de logging UTF-8
    ├── polite_policy.py              # Clases RobotsAuditor y ExponentialBackoffPolicy (backoff + jitter)
    ├── browser.py                    # Clase HeadlessBrowserManager (context manager Selenium Chrome)
    ├── search_navigator.py           # Clase NTSBSearchNavigator (formulario React y paginación multipágina)
    ├── html_parser.py                # Clase InvestigationHTMLParser (parseo DOM con BeautifulSoup / lxml)
    ├── detail_scraper.py             # Clase NTSBDetailScraper (navegación autónoma e hidratación de pestañas)
    ├── exporter.py                   # Clase DatasetExporter (persistencia JSON y exportación CSV UTF-8)
    └── main.py                       # Punto de entrada CLI unificado (argparse) y orquestación del flujo
```

### Responsabilidad Modular de las Clases (`source/`)

| Módulo | Clase Principal | Reutilización |
| :--- | :--- | :--- |
| `source/config.py` | `ScraperConfig` | Centraliza constantes institucionales, `User-Agent`, rutas y parámetros de espera sin duplicación. |
| `source/polite_policy.py` | `RobotsAuditor`, `ExponentialBackoffPolicy` | Audita `robots.txt` (`Crawl-delay` / `can_fetch`) y reutiliza pausas con *jitter* y reintentos exponenciales en todo el scraper. |
| `source/browser.py` | `HeadlessBrowserManager` | Gestiona el ciclo de vida seguro (`__enter__`/`__exit__`) de una única instancia reutilizada de Chrome WebDriver. |
| `source/search_navigator.py` | `NTSBSearchNavigator` | Interactúa con el buscador React CAROL, despacha eventos JS nativos, pagina resultados y descubre hipervínculos. |
| `source/html_parser.py` | `InvestigationHTMLParser` | Desacopla el análisis sintáctico del HTML (`BeautifulSoup` + `lxml`) respecto del navegador para facilitar mantenimiento. |
| `source/detail_scraper.py` | `NTSBDetailScraper` | Visita autónomamente cada URL descubierta, espera hidratación asíncrona `#rsStatus` y despliega las pestañas del DOM. |
| `source/exporter.py` | `DatasetExporter` | Lee/escribe el índice JSON de enlaces y exporta el `DataFrame` crudo a CSV (`utf-8-sig`) dentro de `dataset/`. |
| `source/main.py` | CLI (`main`, `run_pipeline`) | Expone los parámetros por consola y coordina las fases `full`, `discover` y `extract`. |

---

## 5. Instalación con Entorno Virtual y Guía de Uso

### 5.1. Requisitos Previos

* **Python:** 3.10 o superior.
* **Google Chrome:** instalado en el sistema operativo (Selenium Manager resuelve automáticamente el `chromedriver` compatible).
* **Conexión a Internet:** acceso HTTPS a `www.ntsb.gov`, `my.ntsb.gov` y `web.ntsb.gov`.

### 5.2. Configuración Paso a Paso con Entorno Virtual (`venv`)

1. **Clonar el repositorio y situarse en la carpeta raíz:**

   ```bash
   git clone https://github.com/Duvan1/web-scraping-ntsb.git
   cd web-scraping-ntsb
   ```

2. **Crear y activar el entorno virtual aislado:**
  
   * En **Linux / macOS**:

     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

      * En **Windows (CMD)**:

     ```cmd
     python -m venv venv
     .\venv\Scripts\Activate
     ```

3. **Actualizar `pip` e instalar las dependencias:**

   ```bash
   python -m pip install --upgrade pip
   pip install -r source/requirements.txt
   ```

### 5.3. Parámetros Admitidos por el Script (`source/main.py`)

| Parámetro | Tipo | Valor por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--mode` | `{full,discover,extract}` | `full` | `full`: ejecuta auditoría + descubrimiento + extracción DOM; `discover`: solo descubre enlaces; `extract`: extrae fichas desde el JSON previo. |
| `--date-from` | `YYYY-MM-DD` | `2023-01-01` | Fecha inicial del filtro temporal de sucesos en el buscador CAROL. |
| `--date-to` | `YYYY-MM-DD` | `2024-12-31` | Fecha final del filtro temporal de sucesos en el buscador CAROL. |
| `--target` | `int` | `225` | Número mínimo de enlaces únicos a descubrir recorriendo la paginación dinámica (~9 páginas de 25 filas). |
| `--limit` | `int` | `100` | Cantidad de fichas individuales detalladas a visitar y extraer del DOM HTML. |
| `--all` | *flag* | `False` | Si se incluye, ignora `--limit` y visita la totalidad de enlaces disponibles en `dataset/expedientes_ntsb.json`. |
| `--delay` | `float` | `1.5` | Tiempo base (segundos) para las pausas de cortesía con *jitter* y para la fórmula de backoff exponencial. |
| `--headed` | *flag* | `False` | Abre Google Chrome con ventana gráfica visible en lugar de ejecutarse en segundo plano (*Headless*). |
| `--links-json` | `Path` | `dataset/expedientes_ntsb.json` | Ruta de almacenamiento/lectura del archivo JSON de enlaces descubiertos. |
| `--output-csv` | `Path` | `dataset/dataset_ntsb_2023_2024.csv` | Ruta de exportación del archivo CSV final. |

### 5.4. Ejemplos Replicables de Ejecución

1. **Replicación estándar completa del dataset entregado (auditoría + 225 enlaces descubiertos + 100 fichas DOM extraídas):**

   ```bash
   python source/main.py --date-from 2023-01-01 --date-to 2024-12-31 --target 225 --limit 100 --delay 1.5
   ```

2. **Ejecución desacoplada por fases (primero descubrimiento de enlaces y después extracción detallada):**

   ```bash
   python source/main.py --mode discover --date-from 2023-01-01 --date-to 2024-12-31 --target 225
   python source/main.py --mode extract --limit 100 --delay 1.5
   ```

3. **Extracción completa de todas las fichas descubiertas (`--all`) o prueba rápida acotada:**

   ```bash
   # Procesar las 225 fichas descubiertas
   python source/main.py --mode extract --all --delay 1.5

   # Prueba rápida de validación (2 páginas de búsqueda y 5 fichas detalladas)
   python source/main.py --target 30 --limit 5 --delay 1.0
   ```

4. **Ejecución con navegador visible para observar en vivo la navegación autónoma y apertura de pestañas:**

   ```bash
   python source/main.py --target 25 --limit 3 --headed
   ```

---

## 6. Diccionario de Datos (`dataset/dataset_ntsb_2023_2024.csv`)

Todas las variables provienen directamente del **DOM HTML renderizado** en las páginas del portal web (codificación `utf-8-sig`):

| Columna | Tipo | Origen en el DOM HTML | Descripción |
| :--- | :--- | :--- | :--- |
| `identificador` | `string` | `#rsNtsbNumber` / celda enlace `<a>` | Código único oficial del expediente NTSB (p. ej. `ANC25LA014`). |
| `fecha` | `string` (ISO) | `#rsDate` / fila `Event Date` | Fecha del accidente o incidente en formato `YYYY-MM-DD`. |
| `estado_investigacion` | `string` | `#rsStatus` | Estado actual del expediente (`Completed`, `Ongoing`, `Open`). |
| `ubicacion` | `string` | `#rsLocation` / filas `Event City..Country` | Ciudad, estado/región y país del suceso. |
| `latitud` | `float64` | `#rsStaticMap[src]` | Latitud geográfica decimal extraída del mapa renderizado en la ficha. |
| `longitud` | `float64` | `#rsStaticMap[src]` | Longitud geográfica decimal extraída del mapa renderizado en la ficha. |
| `fabricante` | `string` | Pestaña DOM `Aircraft Make` / `Vehicle Details` | Fabricante de la aeronave involucrada (`CESSNA`, `BOEING`, `PIPER`...). |
| `modelo` | `string` | Pestaña DOM `Aircraft Model / Aircraft Series` | Modelo y serie técnica de la aeronave (`172N`, `737`, `PA-28`...). |
| `matricula` | `string` | Pestaña DOM `Registration` / `Vehicle Details` | Matrícula oficial de registro aeronáutico (`N3552E`, `HL8088`...). |
| `operador` | `string` | Pestaña DOM `Operator Name` / `Registered Owner` | Operador comercial, entidad o propietario registrado (`On File` si está anonimizado). |
| `normativa_vuelo` | `string` | Pestaña DOM `Flight Conducted Under` | Regulación bajo la que operaba el vuelo (p. ej. `Part 91: General aviation`). |
| `danos_aeronave` | `string` | Pestaña DOM `Aircraft Damage` | Nivel de daño estructural (`Substantial`, `Destroyed`, `Minor`, `None`). |
| `fallecidos` | `Int64` | Pestaña DOM `Crew / Passenger / Ground Injuries` | Conteo total de víctimas mortales registrado en las tablas HTML de lesiones. |
| `heridos_graves` | `Int64` | Pestaña DOM `Crew / Passenger / Ground Injuries` | Conteo total de heridos graves registrado en las tablas HTML de lesiones. |
| `visibilidad_sm` | `float64` | Pestaña DOM `Visibility (SM)` | Visibilidad horizontal en millas terrestres (*statute miles*) en la zona. |
| `temperatura_f` | `float64` | Pestaña DOM `Temperature (F)` | Temperatura ambiente en grados Fahrenheit reportada en la ficha meteorológica. |
| `velocidad_viento_kts` | `float64` | Pestaña DOM `Wind Speed (kts)` | Velocidad del viento en nudos (*knots*). |
| `causa_probable` | `string` | `section#whatWeFoundSection .investigation-narrative` | Determinación oficial de hallazgos / causa probable limpia de etiquetas HTML. |
| `url_docket` | `string` | `#rsDocketLinks a` / `#rsReportLinks a` | Enlace público al repositorio documental (*Docket*) o informe PDF oficial. |
| `url_expediente` | `string` | Hipervínculo descubierto en Paso 1 | URL pública de la ficha web inspeccionada en `web.ntsb.gov/investigations/`. |

---

## 7. Justificación Ética y Legal del Web Scraping

El diseño y ejecución de esta práctica se rigen rigurosamente por los principios éticos y metodológicos de la investigación académica de la UOC:

1. **Cumplimiento de `robots.txt`:**
   * Previo a cualquier recolección, el script `source/paso1_busqueda_ntsb.py` evalúa programáticamente el archivo oficial [robots.txt de la NTSB](https://www.ntsb.gov/robots.txt) utilizando `urllib.robotparser`.
   * Se certificó que las rutas públicas objetivo (`/Pages/AviationQuery.aspx`, `/aviation` e `/investigations/*`) tienen estado **PERMITIDO (`can_fetch: True`)** y no colisionan con ninguna directiva `Disallow`.

2. **Naturaleza Legal de la Información (Dominio Público Federal):**
   * La NTSB es una agencia federal independiente del gobierno de los Estados Unidos.
   * De conformidad con el título **17 U.S.C. § 105** (*Copyright Law of the United States*), las obras e informes elaborados por oficiales y empleados del gobierno federal de EE. UU. en el marco de sus funciones oficiales son de **Dominio Público** (*United States Government Works*), careciendo de derechos de autor privativos y autorizando su libre reutilización para fines educativos, analíticos y científicos.

3. **Identificación Transparente (User-Agent Institucional):**
   * Todas las peticiones HTTP (tanto en Selenium como en Requests) incluyen un encabezado de cabecera institucional claro:

     ```http
     User-Agent: UOC_Academic_Scraper/1.0 (Contacto: dquevedoagu@uoc.edu, navilana@uoc.edu)
     ```

   * Permite a los administradores de sistemas identificar la naturaleza académica y no comercial del tráfico, así como el punto de contacto directo.

4. **Scraping Responsable y Retardos de Cortesía:**
   * Reutilización de conexiones mediante `requests.Session` para minimizar handshakes SSL y optimizar la huella de tráfico en red.La clase `ExponentialBackoffPolicy` evita ráfagas deterministas añadiendo una componente aleatoria uniforme (*jitter*) a cada pausa de cortesía ($\Delta t = t_{\text{base}} + U(0.25, 0.75)$) e implementa **espera exponencial** ($t_k = t_{\text{base}} \cdot 2^k + \text{jitter}$) ante cualquier latencia o error transitorio del servidor.

---

## 8. Licencia de Publicación

* **Código fuente:** Distribuido bajo la [Licencia MIT](https://opensource.org/licenses/MIT).
* **Datos consolidados:** Los datos provienen de informes gubernamentales de dominio público (17 U.S.C. § 105) y se publican bajo la licencia [Creative Commons CC0 1.0 Universal (Public Domain Dedication)](https://creativecommons.org/publicdomain/zero/1.0/).
