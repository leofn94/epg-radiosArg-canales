import os
import json
import re
import time
import requests
from datetime import datetime, timedelta
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

def ajustar_hora(hora_str, horas_a_sumar=2):
    """Suma X horas a un formato HH:MM."""
    try:
        dt = datetime.strptime(hora_str, "%H:%M")
        dt_ajustada = dt + timedelta(hours=horas_a_sumar)
        return dt_ajustada.strftime("%H:%M")
    except ValueError:
        return hora_str

def limpiar_texto_programa(texto):
    """Limpia encabezados basuras, duraciones y aplica Title Case."""
    # Eliminar títulos de sección colados en el texto
    texto = re.sub(r'Lunes\s+[aA]\s+Viernes', '', texto, flags=re.I)
    texto = re.sub(r'S[áa]bados?\s*(y|e)?\s*Domingos?', '', texto, flags=re.I)
    texto = re.sub(r'Programaci[óo]n\s+Regular', '', texto, flags=re.I)
    
    # Eliminar marcas de duración y botones
    texto = re.sub(r'\b\d{1,3}\s*min\b', '', texto, flags=re.I)
    texto = re.sub(r'(Agendar|Google Calendar|Descargar|\.ics|18\+|13\+|TODOS)', '', texto, flags=re.I)
    
    # Normalizar espacios
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto.title()

url = "https://www.mi-television.com/programacion.php"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, "html.parser")

elementos = soup.find_all(["li", "tr", "div"], class_=re.compile(r'program|broadcast|item|row', re.I))
if not elementos:
    elementos = soup.find_all(["li", "tr", "div"])

items_raw = []
for elem in elementos:
    texto = elem.get_text(" ", strip=True)
    matches_hora = re.findall(r'\b\d{1,2}:\d{2}\b', texto)
    if matches_hora:
        hora_ini_original = matches_hora[0]
        if len(hora_ini_original) == 4:
            hora_ini_original = "0" + hora_ini_original
            
        # Sumar 2 horas para corregir el desfase
        hora_ini = ajustar_hora(hora_ini_original, horas_a_sumar=2)
            
        texto_prog = re.sub(r'^\d{1,2}:\d{2}\s*', '', texto)
        prog_formateado = limpiar_texto_programa(texto_prog)
        
        # Filtro estricto para ignorar bloques con listas concatenadas basuras
        if prog_formateado and len(prog_formateado) > 1 and len(prog_formateado) < 80:
            if not items_raw or items_raw[-1]["inicio"] != hora_ini:
                items_raw.append({"inicio": hora_ini, "programa": prog_formateado})

# Construir lista de filas final cargando Weekdays y Weekend
filas_epg = [["Dia", "Inicio", "Fin", "Programa", "Descripcion"]]

# 1. Cargar bloque de Lunes a Viernes como "Weekdays"
for i in range(len(items_raw)):
    p_curr = items_raw[i]
    fin = items_raw[i+1]["inicio"] if i < len(items_raw) - 1 else items_raw[0]["inicio"]
    filas_epg.append(["Weekdays", p_curr["inicio"], fin, p_curr["programa"], ""])

# 2. Cargar bloque de Fin de semana como "Weekend"
for i in range(len(items_raw)):
    p_curr = items_raw[i]
    fin = items_raw[i+1]["inicio"] if i < len(items_raw) - 1 else items_raw[0]["inicio"]
    filas_epg.append(["Weekend", p_curr["inicio"], fin, p_curr["programa"], ""])

# Volcado a Google Sheets
sheet.clear()
sheet.update(range_name='A1', values=filas_epg)
print(f"¡Éxito! Se actualizaron {len(filas_epg)-1} registros correctamente en la pestaña MITV con etiquetas Weekdays/Weekend.")
