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
# 1. CONFIGURACIÓN Y CONEXIÓN CON GOOGLE SHEETS
# ==========================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Cargar credenciales desde las variables de entorno / GitHub Secrets
gcp_key = os.environ.get("GCP_SA_KEY")
if not gcp_key:
    raise ValueError("No se encontró GCP_SA_KEY en las variables de entorno.")

credentials_info = json.loads(gcp_key)
credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
client = gspread.authorize(credentials)

# API Key de TMDb
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")

# ID de tu Google Spreadsheet
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
                print(f"Aviso: Google API respondió con error {code}. Reintentando en {espera}s (Intento {intento}/{max_intentos})...")
                time.sleep(espera)
            else:
                raise e

sheet = abrir_sheet_con_reintento(SPREADSHEET_ID, NOMBRE_PESTANA)

# ==========================================
# 2. DICCIONARIO LOCAL Y BÚSQUEDA DE SINOPSIS
# ==========================================

SINOPSIS_DB = {
    "ejemplo programa": "Sinopsis de prueba local para este programa.",
    "el chavo del 8": "Las disparatadas vivencias de un niño huérfano en una vecindad de México.",
    # Agrega aquí tus sinopsis locales personalizadas
}

CACHE_SINOPSIS = {}

def normalizar_nombre_programa(nombre_programa):
    """Limpia caracteres indeseados y espacios extra."""
    clean = re.sub(r'\bEN VIVO\b', '', nombre_programa, flags=re.I)
    clean = re.sub(r'\bx\s*\d+\b', '', clean, flags=re.I)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def buscar_en_tmdb_espanol(titulo):
    """Consulta la API de TMDb pidiendo la sinopsis en español latino (es-MX)."""
    if not TMDB_API_KEY:
        return ""
        
    try:
        titulo_clean = re.sub(r'\b(BLOQUE|RUN A|RUN B|SEASON \d+|EPISODIO \d+)\b', '', titulo, flags=re.I).strip()
        query = urllib.parse.quote(titulo_clean)
        
        # 1. Búsqueda en Series de TV
        url_tv = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&language=es-MX"
        res = requests.get(url_tv, timeout=4)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                overview = results[0].get("overview", "").strip()
                if overview and len(overview) > 20:
                    return overview

        # 2. Búsqueda en Películas
        url_movie = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=es-MX"
        res_movie = requests.get(url_movie, timeout=4)
        if res_movie.status_code == 200:
            results = res_movie.json().get("results", [])
            if results:
                overview = results[0].get("overview", "").strip()
                if overview and len(overview) > 20:
                    return overview

    except Exception as e:
        print(f"Error consultando TMDb para '{titulo}':", e)
        
    return ""

def obtener_sinopsis(nombre_programa):
    """
    1. Busca en el diccionario local SINOPSIS_DB.
    2. Consulta en la API de TMDb si no existe localmente.
    3. Retorna cadena vacía "" si no se encuentra en ningún lado.
    """
    clean = normalizar_nombre_programa(nombre_programa)
    
    if clean in CACHE_SINOPSIS:
        return CACHE_SINOPSIS[clean]

    key_norm = clean.lower()
    
    # 1. Búsqueda Local
    sinopsis_encontrada = ""
    if key_norm in SINOPSIS_DB:
        sinopsis_encontrada = SINOPSIS_DB[key_norm]
    else:
        for k, v in SINOPSIS_DB.items():
            if k in key_norm or key_norm in k:
                sinopsis_encontrada = v
                break

    # 2. Búsqueda Externa en TMDb
    if not sinopsis_encontrada:
        sinopsis_encontrada = buscar_en_tmdb_espanol(clean)

    CACHE_SINOPSIS[clean] = sinopsis_encontrada
    return sinopsis_encontrada

# ==========================================
# 3. AJUSTE DE HORARIOS (EL SALVADOR ➔ ARGENTINA)
# ==========================================

def convertir_horario_el_salvador_a_argentina(hora_str, diferencia_horas=3):
    """
    Suma 3 horas al horario recibido de El Salvador (UTC-6)
    para adaptarlo al horario de Argentina (UTC-3).
    """
    try:
        dt = datetime.strptime(hora_str.strip(), "%H:%M")
        dt_ajustada = dt + timedelta(hours=diferencia_horas)
        return dt_ajustada.strftime("%H:%M")
    except ValueError:
        return hora_str

# ==========================================
# 4. SCRAPING Y EXTRACCIÓN DE DATOS
# ==========================================

# Obtener fecha de hoy en Argentina
tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")
hoy_ar = datetime.now(tz_ar)
fecha_hoy_str = hoy_ar.strftime("%Y-%m-%d")

URL_PROGRAMACION = "https://tlmas.kift.live/programacion/index.html"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

print(f"Descargando programación para hoy ({fecha_hoy_str})...")
response = requests.get(URL_PROGRAMACION, headers=headers)
soup = BeautifulSoup(response.content, "html.parser")

programas_raw = []

# Recorremos los elementos que contengan texto en la página
elementos = soup.find_all(['tr', 'li', 'div', 'p'])

for elem in elementos:
    texto = elem.get_text(" ", strip=True)
    # Busca patrones de hora HH:MM o H:MM
    matches = re.findall(r'\b\d{1,2}:\d{2}\b', texto)
    if matches:
        hora_sv = matches[0]
        if len(hora_sv) == 4:
            hora_sv = "0" + hora_sv
            
        # Convertir hora de El Salvador (+3h) a Argentina
        hora_ar = convertir_horario_el_salvador_a_argentina(hora_sv, diferencia_horas=3)
        
        # Limpiar el nombre del programa quitando la hora y caracteres indeseados
        nombre_prog = re.sub(r'^\d{1,2}:\d{2}\s*', '', texto)
        nombre_prog = re.sub(r'\s+', ' ', nombre_prog).strip()
        nombre_prog = normalizar_nombre_programa(nombre_prog)
        
        if nombre_prog and len(nombre_prog) > 1 and len(nombre_prog) < 100:
            # Evitar duplicados inmediatos leídos del mismo HTML
            if not programas_raw or programas_raw[-1]["inicio"] != hora_ar or programas_raw[-1]["programa"] != nombre_prog:
                programas_raw.append({
                    "inicio": hora_ar,
                    "programa": nombre_prog
                })

# ==========================================
# 5. CÁLCULO DE BLOQUES Y UNIFICACIÓN CONTINUA
# ==========================================

bloques_individuales = []
for i in range(len(programas_raw)):
    p_curr = programas_raw[i]
    # La hora de fin es el inicio del siguiente programa o el reinicio del ciclo
    fin = programas_raw[i+1]["inicio"] if i < len(programas_raw) - 1 else programas_raw[0]["inicio"]
    
    bloques_individuales.append({
        "fecha": fecha_hoy_str,
        "inicio": p_curr["inicio"],
        "fin": fin,
        "programa": p_curr["programa"]
    })

# Unificar transmisiones consecutivas del mismo programa
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

if bloque_actual is not None:
    bloques_unificados.append(bloque_actual)

# ==========================================
# 6. GENERACIÓN Y CARGA EN GOOGLE SHEETS
# ==========================================

filas_epg = [["Fecha", "Inicio", "Fin", "Programa", "Descripcion"]]

for b in bloques_unificados:
    sinopsis = obtener_sinopsis(b["programa"])
    filas_epg.append([
        b["fecha"],
        b["inicio"],
        b["fin"],
        b["programa"],
        sinopsis
    ])

# Actualizar en Google Sheets
sheet.clear()
sheet.update(range_name='A1', values=filas_epg)

print(f"¡Éxito! Se cargaron {len(filas_epg) - 1} programas para el día {fecha_hoy_str} en la pestaña '{NOMBRE_PESTANA}'.")
