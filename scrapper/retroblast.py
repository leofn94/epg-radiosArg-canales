import os
import json
import time
import re
import urllib.parse
from datetime import datetime, timedelta
import pandas as pd
import requests
import gspread
from google.oauth2.service_account import Credentials

# 1. Conexión con Google Sheets
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

gcp_key = os.environ.get("GCP_SA_KEY")
if not gcp_key:
    raise ValueError("No se encontró GCP_SA_KEY en los Secrets de GitHub.")

credentials_info = json.loads(gcp_key)
credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
client = gspread.authorize(credentials)

# API Key de TMDb desde GitHub Secrets
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")

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

# --- CONFIGURACIÓN DE SHEETS ---
SHEET_ORIGEN_ID = "1GSqqTGAGtW32-n3XMFOaVs9bUEJSxgGfZe57yOqBS2o"  # Matriz origen
SHEET_DESTINO_ID = "1JKs0R5aFs4uWMBFDAuVtf2-hDDYd87ZkibTqFV600Rs" # Planilla principal
NOMBRE_PESTANA = "BLAST"

sheet_origen = abrir_sheet_con_reintento(SHEET_ORIGEN_ID)
sheet_destino = abrir_sheet_con_reintento(SHEET_DESTINO_ID, NOMBRE_PESTANA)

CACHE_SINOPSIS = {}

def buscar_en_tmdb_espanol(titulo):
    """Consulta la API de TMDb pidiendo explícitamente el resumen en español (es-MX)."""
    if not TMDB_API_KEY:
        return ""
        
    try:
        titulo_clean = re.sub(r'\b(EN VIVO|ESPECIAL|BLOQUE)\b', '', titulo, flags=re.I).strip()
        query = urllib.parse.quote(titulo_clean)
        
        # 1. Búsqueda en Series de TV (TV Shows)
        url_tv = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&language=es-MX"
        res = requests.get(url_tv, timeout=4)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                overview = results[0].get("overview", "").strip()
                if overview and len(overview) > 20:
                    return overview

        # 2. Si no halla en TV, busca en Películas (Movies)
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
    """Busca únicamente en TMDb (Español). Si no encuentra nada, devuelve una cadena vacía."""
    clean = re.sub(r'\bEN VIVO\b', '', nombre_programa, flags=re.I).strip()
    
    if clean in CACHE_SINOPSIS:
        return CACHE_SINOPSIS[clean]

    sinopsis_tmdb = buscar_en_tmdb_espanol(clean)
    
    # Se guarda en caché la sinopsis (o cadena vacía si no se encontró)
    CACHE_SINOPSIS[clean] = sinopsis_tmdb
    return sinopsis_tmdb

# 3. Descargar datos de la matriz
datos_matriz = sheet_origen.get_all_values()

if not datos_matriz:
    raise ValueError("No se encontraron datos en la hoja de origen.")

headers = datos_matriz[0]
df = pd.DataFrame(datos_matriz[1:], columns=headers)

DIAS_MAPA = {
    "Monday": "Lunes",
    "Tuesday": "Martes",
    "Wednesday": "Miércoles",
    "Thursday": "Jueves",
    "Friday": "Viernes",
    "Saturday": "Sábado",
    "Sunday": "Domingo"
}

DIAS_ORDEN = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

programas_procesados = []

# 4. Procesar matriz
col_hora = headers[0]

for col_dia in headers[1:]:
    dia_encontrado = None
    for k_eng, v_esp in DIAS_MAPA.items():
        if k_eng.lower() in col_dia.lower():
            dia_encontrado = v_esp
            break

    if not dia_encontrado:
        continue

    for idx, row in df.iterrows():
        hora_raw = str(row[col_hora]).strip()
        nombre_prog = str(row[col_dia]).strip()

        if not hora_raw or not nombre_prog or nombre_prog.lower() in ["nan", "none", ""]:
            continue

        try:
            if "AM" in hora_raw.upper() or "PM" in hora_raw.upper():
                dt_est = datetime.strptime(hora_raw.upper(), "%I:%M %p")
            elif len(hora_raw.split(":")) == 3:
                dt_est = datetime.strptime(hora_raw, "%H:%M:%S")
            else:
                dt_est = datetime.strptime(hora_raw, "%H:%M")
        except Exception:
            continue

        # SUMA DE 1 HORA (EST -> ART)
        dt_art = dt_est + timedelta(hours=1)
        hora_art_str = dt_art.strftime("%H:%M")

        if dt_est.hour == 23 and dt_art.hour == 0:
            idx_dia_sig = (DIAS_ORDEN.index(dia_encontrado) + 1) % 7
            dia_efectivo = DIAS_ORDEN[idx_dia_sig]
        else:
            dia_efectivo = dia_encontrado

        programas_procesados.append({
            "dia": dia_efectivo,
            "inicio": hora_art_str,
            "programa": nombre_prog
        })

# 5. Ordenar, calcular horas de fin y asignar Sinopsis
filas_epg = [
    ["Dia", "Inicio", "Fin", "Programa", "Descripcion"]
]

for dia_nombre in DIAS_ORDEN:
    progs_dia = [p for p in programas_procesados if p["dia"] == dia_nombre]
    progs_dia.sort(key=lambda x: x["inicio"])

    for i in range(len(progs_dia)):
        p_curr = progs_dia[i]
        
        if i < len(progs_dia) - 1:
            fin = progs_dia[i+1]["inicio"]
        else:
            fin = progs_dia[0]["inicio"]

        # Se obtiene la sinopsis únicamente desde TMDb o se deja en blanco
        sinopsis = obtener_sinopsis(p_curr["programa"])

        filas_epg.append([p_curr["dia"], p_curr["inicio"], fin, p_curr["programa"], sinopsis])

# 6. Volcar en la pestaña 'BLAST'
sheet_destino.clear()
sheet_destino.update(range_name='A1', values=filas_epg)
print(f"¡Éxito! Se procesó y se cargaron {len(filas_epg)-1} registros en BLAST.")
