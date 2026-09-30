import os
import json
import re
import time
import urllib.parse
import requests
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
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
# 2. SINOPSIS LOCAL Y EXTERNA (TMDB)
# ==========================================

SINOPSIS_DB = {
    "ejemplo programa": "Sinopsis de prueba local.",
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
        
        # Búsqueda en TV
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
# 3. CONVERSIÓN DE HORARIO (SV ➔ AR)
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
# 4. SCRAPING AVANZADO Y EXTRACCIÓN
# ==========================================

tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")
fecha_hoy_str = datetime.now(tz_ar).strftime("%Y-%m-%d")

URL_BASE = "https://tlmas.kift.live/programacion/"
URL_INDEX = "https://tlmas.kift.live/programacion/index.html"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

programas_raw = []

print(f"Extrayendo programación para {fecha_hoy_str}...")

# Intento 1: Intentar leer archivo JSON interno si la web usa API
try:
    url_json = "https://tlmas.kift.live/programacion/data.json" # o schedule.json
    res_json = requests.get(url_json, headers=headers, timeout=5)
    if res_json.status_code == 200:
        data = res_json.json()
        for item in data:
            hora_sv = item.get("time") or item.get("hora")
            nombre = item.get("title") or item.get("programa")
            if hora_sv and nombre:
                hora_ar = convertir_horario_sv_a_ar(hora_sv)
                programas_raw.append({"inicio": hora_ar, "programa": normalizar_nombre(nombre)})
except Exception:
    pass

# Intento 2: Parseo directo HTML (Tabla/Estructura flexible)
if not programas_raw:
    res = requests.get(URL_INDEX, headers=headers, timeout=10)
    soup = BeautifulSoup(res.content, "html.parser")

    # Buscar filas o contenedores
    filas = soup.find_all(['tr', 'div', 'li', 'article'])
    for f in filas:
        texto = f.get_text(" ", strip=True)
        # Coincidencia con formato HH:MM o H:MM
        match = re.search(r'(\d{1,2}:\d{2})\s*(?:AM|PM|hs)?\s*[-–—]?\s*(.+)', texto, re.I)
        if match:
            hora_sv = match.group(1)
            if len(hora_sv) == 4:
                hora_sv = "0" + hora_sv
            
            nombre_prog = match.group(2)
            # Limpiar textos basura
            nombre_prog = re.sub(r'\b(AM|PM|hs)\b', '', nombre_prog, flags=re.I)
            nombre_prog = normalizar_nombre(nombre_prog)
            
            if nombre_prog and len(nombre_prog) > 2 and len(nombre_prog) < 90:
                hora_ar = convertir_horario_sv_a_ar(hora_sv)
                if not programas_raw or programas_raw[-1]["inicio"] != hora_ar or programas_raw[-1]["programa"] != nombre_prog:
                    programas_raw.append({"inicio": hora_ar, "programa": nombre_prog})

# ==========================================
# 5. BLOQUES Y CARGA A GOOGLE SHEETS
# ==========================================

if not programas_raw:
    print("⚠️ No se pudo extraer información. Revisa si el sitio requiere renderizado de JavaScript.")
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

    # Unificar bloques continuos
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
    print(f"¡Éxito! Se actualizaron {len(filas_epg) - 1} registros para la fecha {fecha_hoy_str}.")
