import os
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pytz
import requests
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. CONFIGURACIÓN Y GOOGLE SHEETS
# ==========================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

gcp_key = os.environ.get("GCP_SA_KEY")
if not gcp_key:
    raise ValueError("No se encontró GCP_SA_KEY en las variables de entorno.")

credentials_info = json.loads(gcp_key)
credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
client = gspread.authorize(credentials)

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
SPREADSHEET_ID = "1JKs0R5aFs4uWMBFDAuVtf2-hDDYd87ZkibTqFV600Rs"
NOMBRE_PESTANA = "TLMAS"

def abrir_sheet_con_reintento(spreadsheet_id, nombre_pestana=None, max_intentos=5):
    for intento in range(1, max_intentos + 1):
        try:
            doc = client.open_by_key(spreadsheet_id)
            if nombre_pestana:
                try:
                    return doc.worksheet(nombre_pestana)
                except Exception:
                    return doc.add_worksheet(title=nombre_pestana, rows=1000, cols=10)
            return doc.sheet1
        except gspread.exceptions.APIError as e:
            code = getattr(e.response, "status_code", None)
            if code in [500, 502, 503, 504] and intento < max_intentos:
                espera = intento * 5
                print(f"Error {code} en Google API. Reintentando en {espera}s...")
                time.sleep(espera)
            else:
                raise e

sheet = abrir_sheet_con_reintento(SPREADSHEET_ID, NOMBRE_PESTANA)

# ==========================================
# 2. LOCALIZADOR AUTOMÁTICO DE XML
# ==========================================

URL_DIRECTORIO = "https://tlmas.kift.live/assets/xml/epg/Telemas/Semana/"
URL_FALLBACK_PAGINA = "https://tlmas.kift.live/inicio/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def encontrar_url_xml_actualizada():
    """
    Busca automáticamente en el sitio web el archivo .xml de EPG más reciente.
    """
    xml_encontrados = []

    # Intento 1: Escanear la carpeta de la EPG directamente
    try:
        res = requests.get(URL_DIRECTORIO, headers=headers, timeout=8)
        if res.status_code == 200:
            matches = re.findall(r'href=["\']?([^"\'>]+\.xml)["\']?', res.text, re.I)
            for m in matches:
                url_completa = urllib.parse.urljoin(URL_DIRECTORIO, m)
                xml_encontrados.append(url_completa)
    except Exception as e:
        print(f"Aviso al listar directorio: {e}")

    # Intento 2: Escanear la página de inicio en busca de referencias a archivos XML
    if not xml_encontrados:
        try:
            res = requests.get(URL_FALLBACK_PAGINA, headers=headers, timeout=8)
            if res.status_code == 200:
                matches = re.findall(r'https?://[^\s"\']+\.xml|/assets/[^\s"\']+\.xml', res.text, re.I)
                for m in matches:
                    url_completa = urllib.parse.urljoin(URL_FALLBACK_PAGINA, m)
                    xml_encontrados.append(url_completa)
        except Exception as e:
            print(f"Aviso al escanear inicio: {e}")

    # Seleccionar el último archivo XML encontrado (normalmente el más reciente por orden alfabético/fecha)
    if xml_encontrados:
        xml_encontrados.sort()
        url_optima = xml_encontrados[-1]
        print(f" XML detectado automáticamente: {url_optima}")
        return url_optima

    # Fallback por defecto si la búsqueda automática no devuelve nada
    print("⚠️ No se pudo autodetectar el XML. Usando URL fallback por defecto.")
    return "https://tlmas.kift.live/assets/xml/epg/Telemas/Semana/14.09.26.12.00.xml"

# ==========================================
# 3. BASE DE SINOPSIS LOCAL Y EXTERNA (TMDB)
# ==========================================

SINOPSIS_DB = {
    "komi-san no puede comunicarse": "Komi-san padece un severo trastorno de comunicación, pero junto a Tadano intentará cumplir su sueño de hacer 100 amigos.",
    "bocchi the rock!": "Hitori Gotou es una chica introvertida que sueña con tocar en una banda de rock, enfrentando sus miedos sociales con su guitarra.",
    "bleach": "Ichigo Kurosaki obtiene los poderes de un Shinigami para proteger a los inocentes de los espíritus malignos llamados Hollows.",
    "umamusume: pretty derby": "Chicas caballo con habilidades de carrera sobrehumanas entrenan para convertirse en las mejores atletas de la nación.",
    "love live!": "Un grupo de estudiantes decide convertirse en idols escolares para evitar el cierre de su escuela.",
    "amagami-san chi no enmusubi": "Uryu Kamiki intenta ingresar a la facultad de medicina mientras vive en un templo con tres hermanas sacerdotisas."
}

CACHE_SINOPSIS = {}

def normalizar_nombre(nombre):
    clean = re.sub(r'\bEN VIVO\b', '', nombre, flags=re.I)
    clean = re.sub(r'\bx\s*\d+\b', '', clean, flags=re.I)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def buscar_en_tmdb_espanol(titulo):
    if not TMDB_API_KEY:
        return ""
    try:
        titulo_clean = re.sub(r'\b(BLOQUE|RUN A|RUN B|SEASON \d+|EPISODIO \d+)\b', '', titulo, flags=re.I).strip()
        query = urllib.parse.quote(titulo_clean)
        
        # Búsqueda en Series TV
        url_tv = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&language=es-MX"
        res = requests.get(url_tv, timeout=4)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results and results[0].get("overview"):
                return results[0]["overview"].strip()

        # Búsqueda en Películas
        url_movie = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=es-MX"
        res_movie = requests.get(url_movie, timeout=4)
        if res_movie.status_code == 200:
            results = res_movie.json().get("results", [])
            if results and results[0].get("overview"):
                return results[0]["overview"].strip()
    except Exception as e:
        print(f"Error en TMDb para '{titulo}':", e)
    return ""

def obtener_sinopsis(nombre_programa):
    clean = normalizar_nombre(nombre_programa)
    if clean in CACHE_SINOPSIS:
        return CACHE_SINOPSIS[clean]

    key_norm = clean.lower()
    sinopsis = SINOPSIS_DB.get(key_norm, "")
    
    if not sinopsis:
        for k, v in SINOPSIS_DB.items():
            if k in key_norm or key_norm in k:
                sinopsis = v
                break

    if not sinopsis:
        sinopsis = buscar_en_tmdb_espanol(clean)

    CACHE_SINOPSIS[clean] = sinopsis
    return sinopsis

# ==========================================
# 4. CONVERSIÓN DE HORARIO (SV ➔ AR)
# ==========================================

def convertir_horario_sv_a_ar(hora_str, diferencia_horas=3):
    """Suma 3 horas al horario recibido de El Salvador (UTC-6) a Argentina (UTC-3)."""
    try:
        dt = datetime.strptime(hora_str.strip(), "%H:%M")
        dt_ajustada = dt + timedelta(hours=diferencia_horas)
        return dt_ajustada.strftime("%H:%M")
    except ValueError:
        return hora_str

# ==========================================
# 5. DESCARGA Y PARSEO DEL XML
# ==========================================

tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")
fecha_hoy_str = datetime.now(tz_ar).strftime("%Y-%m-%d")

url_xml_actual = encontrar_url_xml_actualizada()
print(f"Descargando programación desde: {url_xml_actual}")

res = requests.get(url_xml_actual, headers=headers, timeout=10)
programas_raw = []

if res.status_code == 200:
    root = ET.fromstring(res.content)
    
    # Extraer los elementos del XML
    for elem in root.findall('.//programme') or root.findall('.//item') or root.findall('.//*'):
        inicio_elem = elem.find('start') if elem.find('start') is not None else elem.find('time')
        titulo_elem = elem.find('title') if elem.find('title') is not None else elem.find('name')
        
        hora_sv = elem.attrib.get('start') or elem.attrib.get('time') or (inicio_elem.text if inicio_elem is not None else None)
        nombre_prog = elem.attrib.get('title') or elem.attrib.get('name') or (titulo_elem.text if titulo_elem is not None else None)
            
        if hora_sv and nombre_prog:
            time_match = re.search(r'\d{1,2}:\d{2}', hora_sv)
            if time_match:
                hora_sv = time_match.group(0)
                if len(hora_sv) == 4:
                    hora_sv = "0" + hora_sv
                
                hora_ar = convertir_horario_sv_a_ar(hora_sv, diferencia_horas=3)
                nombre_clean = normalizar_nombre(nombre_prog)
                
                if nombre_clean and (not programas_raw or programas_raw[-1]["inicio"] != hora_ar or programas_raw[-1]["programa"] != nombre_clean):
                    programas_raw.append({"inicio": hora_ar, "programa": nombre_clean})

# ==========================================
# 6. UNIFICACIÓN DE BLOQUES Y CARGA EN SHEETS
# ==========================================

if not programas_raw:
    print("⚠️ No se pudieron obtener datos del XML.")
else:
    bloques_individuales = []
    for i in range(len(programas_raw)):
        p_curr = programas_raw[i]
        fin = programas_raw[i+1]["inicio"] if i < len(programas_raw) - 1 else programas_raw[0]["inicio"]
        bloques_individuales.append({
            "fecha": fecha_hoy_str,
            "inicio": p_curr["inicio"],
            "fin": fin,
            "programa": p_curr["programa"]
        })

    # Unificar programas consecutivos
    bloques_unificados = []
    bloque_actual = None
    for b in bloques_individuales:
        if bloque_actual is None:
            bloque_actual = b
        else:
            if b["programa"].lower() == bloque_actual["programa"].lower():
                bloque_actual["fin"] = b["fin"]
            else:
                bloques_unificados.append(bloque_actual)
                bloque_actual = b
    if bloque_actual:
        bloques_unificados.append(bloque_actual)

    # Confeccionar filas para la planilla
    filas_epg = [["Fecha", "Inicio", "Fin", "Programa", "Descripcion"]]
    for b in bloques_unificados:
        sinopsis = obtener_sinopsis(b["programa"])
        filas_epg.append([b["fecha"], b["inicio"], b["fin"], b["programa"], sinopsis])

    sheet.clear()
    sheet.update(range_name='A1', values=filas_epg)
    print(f" ¡Éxito! Se actualizaron {len(filas_epg) - 1} filas en Google Sheets para el {fecha_hoy_str}.")
