# Extracción y Construcción de Dataset de Accidentes de Aviación (NTSB)

**Práctica 1: Web Scraping**  
**Asignatura:** M2.851 - Tipología y ciclo de vida de los datos  
**Titulación:** Máster Universitario en Ciencia de Datos  
**Institución:** Universitat Oberta de Catalunya (UOC)  
**Semestre:** 2025-2026  

---

## 1. Descripción General del Proyecto

Este proyecto implementa un pipeline robusto, modular y reproducible de **Web Scraping** para la recolección, estructuración y normalización de información sobre accidentes e incidentes de aviación civil investigados por la **NTSB (*National Transportation Safety Board*)** de los Estados Unidos, correspondientes al periodo 2023-2024.

La arquitectura de recolección se articula en una estrategia metodológica desacoplada en **dos pasos**:
1. **Paso 1 (Selenium Headless - Navegación y Paginación Dinámica):** Automatización de la consulta interactiva en el portal público [NTSB CAROL (Aviation Search)](https://my.ntsb.gov/aviation), gestionando filtros temporales, interacción DOM, modales asíncronos y paginación reactiva en JavaScript mediante esperas explícitas (`WebDriverWait`).
2. **Paso 2 (Requests + BeautifulSoup / lxml - Extracción Técnica y Tipado):** Consumo estructurado de los expedientes mediante peticiones HTTP optimizadas (sesiones persistentes con Keep-Alive), parseo y saneamiento de texto enriquecido con `BeautifulSoup` y normalización estricta de variables en un DataFrame de `pandas`.

El dataset resultante se exporta en formato CSV (`utf-8-sig`) en la carpeta `/dataset`.

---

## 2. Autores y Filiación Académica

* **Autores:**
  * **Duván Quevedo** — `dquevedoagu@uoc.edu`
  * **Neydor Avila** — `navilana@uoc.edu`
* **Programa:** Máster Universitario en Ciencia de Datos
* **Centro:** Universitat Oberta de Catalunya (UOC)

---

## 3. Estructura del Repositorio

El proyecto mantiene una estructura modular y organizada conforme a los estándares académicos de la UOC:

```text
web-scraping-ntsb/
├── .gitignore                                      # Exclusiones de Git (entornos virtuales, temporales)
├── README.md                                       # Memoria técnica y documentación académica
├── dataset/
│   └── licitaciones_o_accidentes_ntsb_2023_2024.csv # Dataset final consolidado con tipado estricto
└── source/
    ├── requirements.txt                            # Especificación de dependencias de Python
    ├── expedientes_ntsb.json                       # Muestra masiva de URLs e identificadores recuperados
    ├── paso1_busqueda_ntsb.py                      # Script Paso 1: Auditoría robots.txt, búsqueda y paginación
    └── paso2_extraccion_expedientes.py             # Script Paso 2: Extracción detallada, parsing y exportación
```

---

## 4. Requisitos Previos e Instalación

### 4.1. Requisitos del Sistema
- **Python:** Versión 3.10 o superior (verificado con Python 3.13 en Windows 11).
- **Navegador Google Chrome:** Instalado en el sistema anfitrión.
- **Conectividad a Internet:** Acceso sin restricciones a los dominios públicos de la NTSB (`ntsb.gov` y `my.ntsb.gov`).

### 4.2. Instalación Paso a Paso

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/Duvan1/web-scraping-ntsb.git
   cd web-scraping-ntsb
   ```

2. **Crear y activar un entorno virtual:**
   * En Linux/macOS:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   * En Windows (PowerShell):
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```

3. **Instalar las dependencias exactas:**
   ```bash
   pip install -r source/requirements.txt
   ```

---

## 5. Instrucciones de Ejecución

El pipeline se ejecuta secuencialmente en dos etapas independientes:

### Etapa 1: Búsqueda, Auditoría y Paginación Masiva
Ejecuta la verificación de `robots.txt` mediante `urllib.robotparser`, abre Chrome en modo headless, introduce el rango temporal 2023-2024, recorre las páginas interactivas y almacena los identificadores en `source/expedientes_ntsb.json`.

```bash
python source/paso1_busqueda_ntsb.py --date-from 2023-01-01 --date-to 2024-12-31 --target 225
```
*Parámetros opcionales:*
- `--target`: Cantidad mínima de registros a recolectar (por defecto `225`, superando los >200 solicitados).
- `--date-from` / `--date-to`: Rango de fechas de búsqueda en formato `YYYY-MM-DD`.

### Etapa 2: Extracción en Profundidad y Generación del Dataset
Lee `source/expedientes_ntsb.json`, realiza peticiones HTTP con `requests`, parsea el HTML/texto con `BeautifulSoup`/`lxml`, estructura los datos en `pandas` con tipado estricto y exporta el CSV consolidado.

```bash
python source/paso2_extraccion_expedientes.py --limit 60 --delay 1.0
```
*Parámetros opcionales:*
- `--limit`: Número de registros a procesar del lote (por defecto `60`).
- `--all`: Procesa la totalidad de expedientes contenidos en el JSON.
- `--delay`: Retardo de cortesía ética entre peticiones consecutivas en segundos (por defecto `1.0`).

---

## 6. Diccionario de Datos

El dataset consolidado (`dataset/licitaciones_o_accidentes_ntsb_2023_2024.csv`) contiene las siguientes variables normalizadas:

| Columna | Tipo de Dato (Pandas) | Descripción | Ejemplo |
| :--- | :--- | :--- | :--- |
| `identificador` | `string` | Clave única alfanumérica del expediente NTSB. | `"WPR23LA091"`, `"ANC25LA014"` |
| `fecha` | `datetime64[ns]` | Fecha del accidente en formato normalizado ISO 8601 (`YYYY-MM-DD`). | `2023-01-15`, `2024-12-31` |
| `ubicacion` | `string` | Localización geográfica (Ciudad, Estado/Región, País). | `"San Diego, California, United States"` |
| `latitud` | `float64` | Latitud decimal en grados geográficos del lugar del evento. | `32.8155` |
| `longitud` | `float64` | Longitud decimal en grados geográficos del lugar del evento. | `-117.1394` |
| `fabricante` | `string` | Fabricante o constructor de la aeronave siniestrada. | `"PIPER"`, `"CESSNA"`, `"BOEING"` |
| `modelo` | `string` | Modelo técnico de la aeronave involucrada. | `"PA-28-180"`, `"172N"` |
| `operador` | `string` | Nombre del operador, propietario registrado o entidad de vuelo. | `"Christopher Cardoza"`, `"On File"` |
| `fallecidos` | `Int64` (nullable) | Conteo de personas fallecidas a bordo o en tierra. | `0`, `1`, `<NA>` |
| `heridos_graves` | `Int64` (nullable) | Conteo de personas con lesiones graves según clasificación NTSB. | `0`, `1`, `<NA>` |
| `danos_aeronave` | `string` | Severidad del daño estructural (`Destroyed`, `Substantial`, `Minor`, `None`). | `"Substantial"`, `"Destroyed"` |
| `condicion_meteo` | `string` | Régimen visual o meteorológico (`Visual (VMC)`, `Instrument (IMC)`). | `"Visual (VMC)"`, `"Instrument (IMC)"` |
| `causa_probable` | `string` | Texto de la determinación de causa probable y hallazgos finales saneado de HTML. | *"The flight instructor's failure to maintain altitude..."* |

---

## 7. Justificación Ética y Legal del Web Scraping

El diseño y ejecución de esta práctica se rigen rigurosamente por los principios éticos y metodológicos de la investigación académica de la UOC:

1. **Cumplimiento de `robots.txt`:**
   - Previo a cualquier recolección, el script `source/paso1_busqueda_ntsb.py` evalúa programáticamente el archivo oficial [robots.txt de la NTSB](https://www.ntsb.gov/robots.txt) utilizando `urllib.robotparser`.
   - Se certificó que las rutas públicas objetivo (`/Pages/AviationQuery.aspx`, `/aviation` e `/investigations/*`) tienen estado **PERMITIDO (`can_fetch: True`)** y no colisionan con ninguna directiva `Disallow`.

2. **Naturaleza Legal de la Información (Dominio Público Federal):**
   - La NTSB es una agencia federal independiente del gobierno de los Estados Unidos.
   - De conformidad con el título **17 U.S.C. § 105** (*Copyright Law of the United States*), las obras e informes elaborados por oficiales y empleados del gobierno federal de EE. UU. en el marco de sus funciones oficiales son de **Dominio Público** (*United States Government Works*), careciendo de derechos de autor privativos y autorizando su libre reutilización para fines educativos, analíticos y científicos.

3. **Identificación Transparente (User-Agent Institucional):**
   - Todas las peticiones HTTP (tanto en Selenium como en Requests) incluyen un encabezado de cabecera institucional claro:
     ```http
     User-Agent: UOC_Academic_Scraper/1.0 (Contacto: dquevedoagu@uoc.edu, navilana@uoc.edu)
     ```
   - Permite a los administradores de sistemas identificar la naturaleza académica y no comercial del tráfico, así como el punto de contacto directo.

4. **Scraping Responsable y Retardos de Cortesía:**
   - Se implementan retardos de cortesía ética mediante pausas de ejecución (`time.sleep`) entre peticiones, previniendo cualquier sobrecarga en los servidores de la agencia federal.
   - Reutilización de conexiones mediante `requests.Session` para minimizar handshakes SSL y optimizar la huella de tráfico en red.

---

## 8. Licencia de Publicación

- **Código fuente:** Distribuido bajo la [Licencia MIT](https://opensource.org/licenses/MIT).
- **Datos consolidados:** Los datos provienen de informes gubernamentales de dominio público (17 U.S.C. § 105) y se publican bajo la licencia [Creative Commons CC0 1.0 Universal (Public Domain Dedication)](https://creativecommons.org/publicdomain/zero/1.0/).
