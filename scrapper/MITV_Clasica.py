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
    """Suma 2 horas a la hora ingresada (formato HH:MM)."""
    try:
        dt = datetime.strptime(hora_str, "%H:%M")
        dt_ajustada = dt + timedelta(hours=horas_a_sumar)
        return dt_ajustada.strftime("%H:%M")
    except ValueError:
        return hora_str

def limpiar_texto_programa(texto):
    """Limpia la basura y aplica Title Case."""
    texto = re.sub(r'Lunes\s+[aA]\s+Viernes', '', texto, flags=re.I)
    texto = re.sub(r'Fin\s+de\s+Semana|S[áa]bados?\s*(y|e)?\s*Domingos?', '', texto, flags=re.I)
    texto = re.sub(r'\b\d{1,3}\s*min\b', '', texto, flags=re.I)
    texto = re.sub(r'(Agendar|Google Calendar|Descargar|\.ics|18\+|13\+|TODOS)', '', texto, flags=re.I)
    texto = re.sub(r'^\s*[\cdot\•\-\:]+\s*', '', texto)  # Quita puntos o guiones al inicio (ej: "• 101 Dalmatas")
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto.title()

def extraer_programas_de_texto(bloque_texto):
    """Parsea un bloque de texto buscando patrones de HORA PROGRAMA."""
    lineas = bloque_texto.split('\n')
    programas = []
    
    for linea in lineas:
        linea = linea.strip()
        match = re.search(r'(\b\d{1,2}:\d{2}\b)\s*(.*)', linea)
        if match:
            hora_raw = match.group(1)
            if len(hora_raw) == 4:
                hora_raw = "0" + hora_raw
                
            hora_ajustada = ajustar_hora(hora_raw, horas_a_sumar=2)
            nombre_prog = limpiar_texto_programa(match.group(2))
            
            if nombre_prog and len(nombre_prog) > 1:
                # Evitar duplicados consecutivos de la misma hora
                if not programas or programas[-1]["inicio"] != hora_ajustada:
                    programas.append({"inicio": hora_ajustada, "programa": nombre_prog})
                    
    return programas

# 2. Descarga del sitio web
url = "https://www.mi-television.com/programacion.php"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, "html.parser")

# Obtener todo el texto manteniendo saltos de línea para facilitar el parseo
texto_completo = soup.get_text("\n")

# Separar el texto en los dos bloques principales
bloque_weekdays = ""
bloque_weekend = ""

# Buscar división por encabezados en el texto
match_weekdays = re.search(r'Lunes\s+a\s+Viernes(.*?)(Fin\s+de\s+Semana|S[áa]bado|$)', texto_completo, re.DOTALL | re.I)
match_weekend = re.search(r'(Fin\s+de\s+Semana|S[áa]bados?\s+y\s+Domingos?)(.*)', texto_completo, re.DOTALL | re.I)

if match_weekdays:
    bloque_weekdays = match_weekdays.group(1)
if match_weekend:
    bloque_weekend = match_weekend.group(2)

# Extraer programas de cada bloque por separado
progs_weekdays = extraer_programas_de_texto(bloque_weekdays)
progs_weekend = extraer_programas_de_texto(bloque_weekend)

# 3. Armar las filas finales para el EPG
filas_epg = [["Dia", "Inicio", "Fin", "Programa", "Descripcion"]]

# Cargar Weekdays
for i in range(len(progs_weekdays)):
    p_curr = progs_weekdays[i]
    fin = progs_weekdays[i+1]["inicio"] if i < len(progs_weekdays) - 1 else progs_weekdays[0]["inicio"]
    filas_epg.append(["Weekdays", p_curr["inicio"], fin, p_curr["programa"], ""])

# Cargar Weekend
for i in range(len(progs_weekend)):
    p_curr = progs_weekend[i]
    fin = progs_weekend[i+1]["inicio"] if i < len(progs_weekend) - 1 else progs_weekend[0]["inicio"]
    filas_epg.append(["Weekend", p_curr["inicio"], fin, p_curr["programa"], ""])

# 4. Volcado limpio a Google Sheets
sheet.clear()
sheet.update(range_name='A1', values=filas_epg)
print(f"¡Éxito! Se cargaron {len(progs_weekdays)} programas para Weekdays y {len(progs_weekend)} para Weekend en la pestaña MITV.")
