import os
import json
import re
import time
import requests
import urllib.parse
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

# Cache local durante la ejecución para evitar buscar el mismo programa múltiples veces
CACHE_SINOPSIS = {}

def buscar_sinopsis_dinamica(nombre_programa):
    """Busca dinámicamente la sinopsis del programa vía TVMaze/Wikipedia si cambia la grilla."""
    nombre_clean = re.sub(r'\(.*?\)', '', nombre_programa).strip()
    
    # 1. Verificar si ya fue buscado en esta corrida
    if nombre_clean in CACHE_SINOPSIS:
        return CACHE_SINOPSIS[nombre_clean]

    # 2. Intentar buscar en la API pública de TVMaze
    try:
        query = urllib.parse.quote(nombre_clean)
        url_api = f"https://api.tvmaze.com/singlesearch/shows?q={query}"
        res = requests.get(url_api, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data and "summary" in data and data["summary"]:
                # Limpiar etiquetas HTML de la respuesta (<p>, <b>, etc.)
                summary_text = re.sub(r'<[^>]+>', '', data["summary"]).strip()
                if len(summary_text) > 20:
                    CACHE_SINOPSIS[nombre_clean] = summary_text
                    return summary_text
    except Exception:
        pass

    # 3. Respuesta fallback dinámica según tipo de programa
    if re.search(r'Cine|Pelicula|Film', nombre_clean, re.I):
        sinopsis = f"Espacio cinematográfico dedicado a la emisión de producciones de {nombre_clean}."
    elif re.search(r'Documental|Documentales', nombre_clean, re.I):
        sinopsis = "Programa documental enfocado en cultura, historia, naturaleza y temas de interés general."
    elif re.search(r'Caricaturas|Animada|Dibujos', nombre_clean, re.I):
        sinopsis = "Bloque de entretenimiento animado destinado a todo público."
    else:
        sinopsis = f"Emisión regular del programa {nombre_clean}."
        
    CACHE_SINOPSIS[nombre_clean] = sinopsis
    return sinopsis

def ajustar_hora(hora_str, horas_a_sumar=2):
    """Suma 2 horas a un formato HH:MM."""
    try:
        dt = datetime.strptime(hora_str, "%H:%M")
        dt_ajustada = dt + timedelta(hours=horas_a_sumar)
        return dt_ajustada.strftime("%H:%M")
    except ValueError:
        return hora_str

def limpiar_texto_programa(texto):
    """Limpia encabezados, viñetas y aplica Title Case."""
    texto = re.sub(r'Lunes\s+[aA]\s+Viernes', '', texto, flags=re.I)
    texto = re.sub(r'Fin\s+de\s+Semana|S[áa]bados?\s*(y|e)?\s*Domingos?', '', texto, flags=re.I)
    texto = re.sub(r'\b\d{1,3}\s*min\b', '', texto, flags=re.I)
    texto = re.sub(r'(Agendar|Google Calendar|Descargar|\.ics|18\+|13\+|TODOS)', '', texto, flags=re.I)
    texto = re.sub(r'^\s*[·•\-\:]+\s*', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto.title()

# 2. Descarga de la web
url = "https://www.mi-television.com/programacion.php"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, "html.parser")

progs_weekdays = []
progs_weekend = []
modo_actual = "Weekdays"

elementos = soup.find_all(['h1', 'h2', 'h3', 'h4', 'div', 'li', 'tr', 'p'])

for elem in elementos:
    texto = elem.get_text(" ", strip=True)
    
    if re.search(r'(Fin\s+de\s+Semana|S[áa]bado|Domingo)', texto, re.I) and len(texto) < 40:
        modo_actual = "Weekend"
        continue
    
    matches_hora = re.findall(r'\b\d{1,2}:\d{2}\b', texto)
    if matches_hora:
        hora_raw = matches_hora[0]
        if len(hora_raw) == 4:
            hora_raw = "0" + hora_raw
            
        hora_ajustada = ajustar_hora(hora_raw, horas_a_sumar=2)
        
        texto_prog = re.sub(r'^\d{1,2}:\d{2}\s*', '', texto)
        nombre_prog = limpiar_texto_programa(texto_prog)
        
        if nombre_prog and len(nombre_prog) > 1 and len(nombre_prog) < 80:
            # Obtener o consultar la sinopsis en vivo
            sinopsis = buscar_sinopsis_dinamica(nombre_prog)
            
            item = {
                "inicio": hora_ajustada, 
                "programa": nombre_prog,
                "descripcion": sinopsis
            }
            
            if modo_actual == "Weekdays":
                if not progs_weekdays or progs_weekdays[-1]["inicio"] != hora_ajustada:
                    progs_weekdays.append(item)
            else:
                if not progs_weekend or progs_weekend[-1]["inicio"] != hora_ajustada:
                    progs_weekend.append(item)

# 3. Armar las filas finales
filas_epg = [["Dia", "Inicio", "Fin", "Programa", "Descripcion"]]

for i in range(len(progs_weekdays)):
    p_curr = progs_weekdays[i]
    fin = progs_weekdays[i+1]["inicio"] if i < len(progs_weekdays) - 1 else progs_weekdays[0]["inicio"]
    filas_epg.append(["Weekdays", p_curr["inicio"], fin, p_curr["programa"], p_curr["descripcion"]])

for i in range(len(progs_weekend)):
    p_curr = progs_weekend[i]
    fin = progs_weekend[i+1]["inicio"] if i < len(progs_weekend) - 1 else progs_weekend[0]["inicio"]
    filas_epg.append(["Weekend", p_curr["inicio"], fin, p_curr["programa"], p_curr["descripcion"]])

# 4. Volcado a Google Sheets
sheet.clear()
sheet.update(range_name='A1', values=filas_epg)
print(f"¡Éxito! Se actualizaron {len(progs_weekdays)} programas para Weekdays y {len(progs_weekend)} para Weekend con sinopsis dinámicas.")
