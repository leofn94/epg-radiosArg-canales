import os
import json
import re
import time
import requests
from bs4 import BeautifulSoup
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

SPREADSHEET_ID = "1JKs0R5aFs4uWMBFDAuVtf2-hDDYd87ZkibTqFV600Rs"

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

sheet = abrir_sheet_con_reintento(SPREADSHEET_ID, "MITV")

def formatear_titulo(texto):
    """Limpia el texto y aplica formato Capitalizado (Title Case)."""
    texto = re.sub(r'\b\d{1,3}\s*min\b', '', texto, flags=re.I)
    texto = re.sub(r'(Agendar|Google Calendar|Descargar|\.ics|18\+|13\+|TODOS)', '', texto, flags=re.I)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto.title()

url = "https://www.mi-television.com/programacion.php"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, "html.parser")

# Agrupamiento de días
WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
WEEKEND = ["Sábado", "Domingo"]

# Buscar bloques/secciones completas en la página
secciones = soup.find_all(["div", "section", "article"])

programas_por_bloque = {
    "weekdays": [],
    "weekend": []
}

# Extraer ítems de programación
elementos = soup.find_all(["li", "tr", "div"], class_=re.compile(r'program|broadcast|item|row', re.I))
if not elementos:
    elementos = soup.find_all(["li", "tr", "div"])

items_raw = []
for elem in elementos:
    texto = elem.get_text(" ", strip=True)
    matches_hora = re.findall(r'\b\d{1,2}:\d{2}\b', texto)
    if matches_hora:
        hora_ini = matches_hora[0]
        if len(hora_ini) == 4:
            hora_ini = "0" + hora_ini
            
        texto_prog = re.sub(r'^\d{1,2}:\d{2}\s*', '', texto)
        prog_formateado = formatear_titulo(texto_prog)
        
        if prog_formateado and len(prog_formateado) > 1:
            if not items_raw or items_raw[-1]["inicio"] != hora_ini:
                items_raw.append({"inicio": hora_ini, "programa": prog_formateado})

# Construir lista de filas final para el EPG
filas_epg = [["Dia", "Inicio", "Fin", "Programa", "Descripcion"]]

# Mapear la grilla extraída a los días de la semana (Lunes a Viernes)
for dia in WEEKDAYS:
    for i in range(len(items_raw)):
        p_curr = items_raw[i]
        fin = items_raw[i+1]["inicio"] if i < len(items_raw) - 1 else items_raw[0]["inicio"]
        filas_epg.append([dia, p_curr["inicio"], fin, p_curr["programa"], ""])

# Mapear la grilla a los días del fin de semana (Sábado y Domingo)
for dia in WEEKEND:
    for i in range(len(items_raw)):
        p_curr = items_raw[i]
        fin = items_raw[i+1]["inicio"] if i < len(items_raw) - 1 else items_raw[0]["inicio"]
        filas_epg.append([dia, p_curr["inicio"], fin, p_curr["programa"], ""])

# Volcado a Google Sheets
sheet.clear()
sheet.update(range_name='A1', values=filas_epg)
print(f"¡Éxito! Se actualizaron {len(filas_epg)-1} registros correctamente en la pestaña MITV.")
