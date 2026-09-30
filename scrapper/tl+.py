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
    "komi-san no puede comunicarse": "Komi-san es una chica hermosa y admirada por todos, pero padece un severo trastorno de comunicación. Junto a Tadano, intentará cumplir su sueño de hacer 100 amigos.",
    "bocchi the rock!": "Hitori Gotou es una chica extremadamente introvertida y solitaria que sueña con tocar en una banda de rock, enfrentando sus miedos sociales con su guitarra.",
    "bleach": "Ichigo Kurosaki es un adolescente capaz de ver espíritus que obtiene los poderes de un Shinigami para proteger a los inocentes y combatir a los espíritus malignos llamados Hollows.",
    "umamusume: pretty derby": "Chicas caballo con habilidades de carrera sobrehumanas entrenan para convertirse en las mejores atletas de la nación y triunfar en la gran escena de las competencias.",
    "love live": "Un grupo de estudiantes decide convertirse en idols escolares para evitar el cierre de su amada preparatoria y salvar su escuela.",
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
# 4. EXTRACCIÓN DE DATOS DESDE ENDPOINTS
# ==========================================

tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")
fecha_hoy_str = datetime.now(tz_ar).strftime("%Y-%m-%d")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://tlmas.kift.live/"
}

programas_raw = []

print(f"Extrayendo programación para {fecha_hoy_str}...")

# Posibles URLs de API / JSON del reproductor
endpoints = [
    "https://tlmas.kift.live/api/programacion",
    "https://tlmas.kift.live/programacion.json",
    "https://tlmas.kift.live/api/schedule",
    "https://tlmas.kift.live/data/schedule.json",
    "https://tlmas.kift.live/programacion/index.html"
]

for endpoint in endpoints:
    try:
        res = requests.get(endpoint, headers=headers, timeout=5)
        if res.status_code == 200:
            # Intento de parseo JSON
            try:
                data = res.json()
                items = data.get("epg") or data.get("programacion") or data.get("schedule") or (data if isinstance(data, list) else [])
                for item in items:
                    hora_sv = item.get("time") or item.get("hora") or item.get("start")
                    nombre = item.get("title") or item.get("programa") or item.get("name")
                    if hora_sv and nombre:
                        if len(hora_sv) == 4:
                            hora_sv = "0" + hora_sv
                        hora_ar = convertir_horario_sv_a_ar(hora_sv)
                        programas_raw.append({"inicio": hora_ar, "programa": normalizar_nombre(nombre)})
                if programas_raw:
                    break
            except Exception:
                # Parseo HTML con BeautifulSoup si devuelve HTML
                soup = BeautifulSoup(res.content, "html.parser")
                # Extraer de tarjetas de guía o listas
                elementos = soup.select(".guia, .schedule-item, .program-item, tr, div")
                for elem in elementos:
                    texto = elem.get_text(" ", strip=True)
                    match = re.search(r'(\d{1,2}:\d{2})\s*-\s*\d{1,2}:\d{2}\s+(.+)', texto)
                    if match:
                        hora_sv = match.group(1)
                        if len(hora_sv) == 4:
                            hora_sv = "0" + hora_sv
                        nombre_prog = match.group(2)
                        hora_ar = convertir_horario_sv_a_ar(hora_sv)
                        programas_raw.append({"inicio": hora_ar, "programa": normalizar_nombre(nombre_prog)})
                if programas_raw:
                    break
    except Exception as e:
        continue

# ==========================================
# 5. BLOQUES Y CARGA A GOOGLE SHEETS
# ==========================================

if not programas_raw:
    print("⚠️ No se pudo extraer información desde las peticiones directas. Verifica las peticiones de red (Fetch/XHR) en el navegador.")
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

    # Unificar transmisiones consecutivas
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

    # Armado final de la tabla
    filas_epg = [["Fecha", "Inicio", "Fin", "Programa", "Descripcion"]]
    for b in bloques_unificados:
        sinopsis = obtener_sinopsis(b["programa"])
        filas_epg.append([b["fecha"], b["inicio"], b["fin"], b["programa"], sinopsis])

    sheet.clear()
    sheet.update(range_name='A1', values=filas_epg)
    print(f"¡Éxito! Se actualizaron {len(filas_epg) - 1} registros para la fecha {fecha_hoy_str} en Google Sheets.")
