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

# Base de respaldo en español para programas o bloques especiales
SINOPSIS_ESPANOL = {
    "El Septimo Cielo": "Serie dramática familiar que sigue la vida del reverendo Eric Camden, su esposa Annie y sus siete hijos enfrentando los dilemas cotidianos de la vida.",
    "El Hombre Del Maletin": "Serie clásica de espionaje y suspenso que sigue las peligrosas misiones y misterios de un intrépido agente secreto.",
    "101 Dalmatas": "Serie animada que sigue las divertidas peripecias de los cachorros dálmatas en la granja mientras escapan de las ocurrencias de Cruella de Vil.",
    "Area 12": "Serie policíaca y de acción que retrata el trabajo diario de una patrulla urbana resolviendo crímenes e incidentes en las calles.",
    "La Mujer Bionica": "Jaime Sommers utiliza sus implantes cibernéticos de alta tecnología para cumplir arriesgadas misiones secretas para el gobierno.",
    "Chico Listo": "Comedia de situaciones sobre TJ Henderson, un niño prodigio de 10 años que es transferido a la escuela secundaria con compañeros mayores.",
    "El Show De Los Muppets": "El emblemático programa de variedades y comedia presentado por Kermit la Rana, Miss Piggy y un elenco inolvidable de marionetas.",
    "La Casa De La Pradera": "Las emotivas vivencias de la familia Ingalls en un pequeño pueblo del oeste estadounidense a finales del siglo XIX.",
    "El Senor De Las Bestias": "Serie de fantasía y aventuras sobre Dar, un guerrero capaz de comunicarse telepáticamente con los animales para proteger a los inocentes.",
    "Perdidos En El Espacio": "Las aventuras de la familia Robinson intentando sobrevivir tras quedar varados en los confines del espacio exterior.",
    "La Novicia Rebelde": "Una joven e independiente postulante a monja se convierte en la instructora de los siete hijos del estricto capitán Von Trapp.",
    "Odisea Burbujas": "Las divertidas aventuras educativas del Profesor Memelovsky y sus asistentes protegiendo al medio ambiente del ecoloco.",
    "Mi Bella Genio": "Un astronauta encuentra una botella mágica en una isla desierta y libera a una hermosa genio que se enamora de él.",
    "Blanco Y Negro": "Comedia de situaciones sobre dos hermanos afroamericanos de Harlem que son adoptados por un millonario de Manhattan.",
    "Tierra De Gigantes": "La tripulación de una nave espacial en un viaje interplanetario queda atrapada en un planeta habitado por seres gigantescos."
}

CACHE_SINOPSIS = {}

def obtener_nombre_base(titulo):
    """Limpia aclaraciones del título para quedarse con el nombre real de la serie/película."""
    # Elimina textos entre paréntesis o tras barras/días
    limpio = re.sub(r'\(.*?\)', '', titulo)
    limpio = re.split(r'/| De Lunes| Lunes| Viernes| Este Espacio', limpio, flags=re.I)[0]
    limpio = re.sub(r'^\s*[·•\-\:]+\s*', '', limpio)
    return limpio.strip()

def buscar_sinopsis_wikipedia(titulo_clean):
    """Busca el primer párrafo de resumen en Wikipedia en Español."""
    try:
        query = urllib.parse.quote(titulo_clean)
        url_wiki = f"https://es.wikipedia.org/api/rest_v1/page/summary/{query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url_wiki, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if "extract" in data and len(data["extract"]) > 30:
                extracto = data["extract"]
                # Cortar en el primer punto para mantener brevedad
                primer_punto = extracto.find('.')
                if primer_punto != -1 and primer_punto > 40:
                    extracto = extracto[:primer_punto + 1]
                return extracto
    except Exception:
        pass
    return None

def obtener_sinopsis_espanol(nombre_programa_raw):
    """Genera la sinopsis limpia en español combinando Wikipedia, diccionario y fallbacks."""
    nombre_clean = obtener_nombre_base(nombre_programa_raw)
    
    if nombre_clean in CACHE_SINOPSIS:
        return CACHE_SINOPSIS[nombre_clean]
        
    # 1. Búsqueda en el diccionario local
    for clave, desc in SINOPSIS_ESPANOL.items():
        if clave.lower() in nombre_clean.lower() or nombre_clean.lower() in clave.lower():
            CACHE_SINOPSIS[nombre_clean] = desc
            return desc
            
    # 2. Búsqueda automática en Wikipedia en Español
    desc_wiki = buscar_sinopsis_wikipedia(nombre_clean)
    if desc_wiki:
        CACHE_SINOPSIS[nombre_clean] = desc_wiki
        return desc_wiki

    # 3. Categorización inteligente en español
    if re.search(r'Cine|Pelicula|Film', nombre_clean, re.I):
        sinopsis = "Espacio cinematográfico dedicado a la emisión de películas destacadas y producciones inolvidables."
    elif re.search(r'Documental|Documentales', nombre_clean, re.I):
        sinopsis = "Espacio informativo dedicado a documentales sobre naturaleza, historia, ciencia y cultura general."
    elif re.search(r'Caricaturas|Animada|Dibujos', nombre_clean, re.I):
        sinopsis = "Bloque de entretenimiento animado con los personajes y cortometrajes clásicos preferidos de la televisión."
    else:
        sinopsis = f"Programa de entretenimiento y serie destacada de la grilla de {nombre_clean}."

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
    """Limpia encabezados y aplica Title Case."""
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
            sinopsis = obtener_sinopsis_espanol(nombre_prog)
            
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
print(f"¡Éxito! Se actualizaron {len(progs_weekdays)} programas para Weekdays y {len(progs_weekend)} para Weekend con sinopsis completas en español.")
