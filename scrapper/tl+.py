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
# 1. CONFIGURACIÓN Y CONEXIÓN CON GOOGLE SHEETS
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
# 2. CONSTRUCTOR DE URL DINÁMICA POR FECHA DE SEMANA
# ==========================================

tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")
hoy = datetime.now(tz_ar)
fecha_hoy_str = hoy.strftime("%Y-%m-%d")

def obtener_urls_candidatas_xml(fecha_ref):
    """
    Calcula el lunes de la semana actual y genera las URLs probables
    siguiendo el patrón DD.MM.YY.12.00.xml
    """
    # Obtener el lunes de esta semana
    lunes_semana = fecha_ref - timedelta(days=fecha_ref.weekday())
    lunes_anterior = lunes_semana - timedelta(days=7)
    
    patron_semana_actual = lunes_semana.strftime("%d.%m.%y.12.00.xml")
    patron_semana_anterior = lunes_anterior.strftime("%d.%m.%y.12.00.xml")
    
    base_url = "https://tlmas.kift.live/assets/xml/epg/Telemas/Semana/"
    
    return [
        base_url + patron_semana_actual,
        base_url + patron_semana_anterior,
        "https://tlmas.kift.live/assets/xml/epg/Telemas/Semana/14.09.26.12.00.xml" # Fallback
    ]

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
        
        url_tv = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&language=es-MX"
        res = requests.get(url_tv, timeout=4)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results and results[0].get("overview"):
                return results[0]["overview"].strip()

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
    """Suma 3 horas (El Salvador UTC-6 a Argentina UTC-3)."""
    try:
        dt = datetime.strptime(hora_str.strip(), "%H:%M")
        dt_ajustada = dt + timedelta(hours=diferencia_horas)
        return dt_ajustada.strftime("%H:%M")
    except ValueError:
        return hora_str

# ==========================================
# 5. DESCARGA Y PARSEO ROBUSTO DE XMLTV
# ==========================================

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

urls_candidatas = obtener_urls_candidatas_xml(hoy)
xml_content = None
url_usada = ""

for url in urls_candidatas:
    try:
        print(f"Probando descargar XML desde: {url}")
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200 and len(res.content) > 100:
            xml_content = res.content
            url_usada = url
            print(f" Descargado con éxito desde: {url_usada}")
            break
    except Exception as e:
        continue

programas_raw = []

if xml_content:
    try:
        root = ET.fromstring(xml_content)
        
        # Parseo flexible de formato XML / XMLTV
        for elem in root.iter():
            tag = elem.tag.lower()
            if tag in ['programme', 'program', 'item', 'event']:
                # 1. Obtener Hora
                hora_sv = elem.attrib.get('start') or elem.attrib.get('time') or elem.attrib.get('begin')
                
                # Si la hora está en una subetiqueta
                if not hora_sv:
                    sub_time = elem.find('start') or elem.find('time')
                    if sub_time is not None:
                        hora_sv = sub_time.text

                # 2. Obtener Título
                nombre_prog = elem.attrib.get('title') or elem.attrib.get('name')
                if not nombre_prog:
                    sub_title = elem.find('title') or elem.find('name') or elem.find('heading')
                    if sub_title is not None:
                        nombre_prog = sub_title.text

                if hora_sv and nombre_prog:
                    # Extraer patrones HH:MM o marcas de tiempo YYYYMMDDHHMMSS
                    time_match = re.search(r'(\d{2}):(\d{2})', hora_sv)
                    if not time_match:
                        # Formato timestamp XMLTV: 20260914190000
                        ts_match = re.search(r'\d{8}(\d{2})(\d{2})', hora_sv)
                        if ts_match:
                            hora_sv_formatted = f"{ts_match.group(1)}:{ts_match.group(2)}"
                        else:
                            hora_sv_formatted = None
                    else:
                        hora_sv_formatted = time_match.group(0)

                    if hora_sv_formatted:
                        if len(hora_sv_formatted) == 4:
                            hora_sv_formatted = "0" + hora_sv_formatted
                        
                        hora_ar = convertir_horario_sv_a_ar(hora_sv_formatted, diferencia_horas=3)
                        nombre_clean = normalizar_nombre(nombre_prog)
                        
                        if nombre_clean and (not programas_raw or programas_raw[-1]["inicio"] != hora_ar or programas_raw[-1]["programa"] != nombre_clean):
                            programas_raw.append({"inicio": hora_ar, "programa": nombre_clean})

    except Exception as e:
        print(f"Error procesando XML: {e}")

# ==========================================
# 6. UNIFICACIÓN DE BLOQUES Y GOOGLE SHEETS
# ==========================================

if not programas_raw:
    print("⚠️ No se pudieron procesar los registros del XML. Revisa la estructura del archivo descargado.")
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

    # Armado final
    filas_epg = [["Fecha", "Inicio", "Fin", "Programa", "Descripcion"]]
    for b in bloques_unificados:
        sinopsis = obtener_sinopsis(b["programa"])
        filas_epg.append([b["fecha"], b["inicio"], b["fin"], b["programa"], sinopsis])

    sheet.clear()
    sheet.update(range_name='A1', values=filas_epg)
    print(f"¡Éxito! Se actualizaron {len(filas_epg) - 1} programas para el {fecha_hoy_str} en Google Sheets.")
