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

# 2. Diccionario de Sinopsis Predefinidas
SINOPSIS_DB = {
    "Las Aventuras De Sinbad": "Serie de aventuras y fantasía sobre las legendarias travesías del marino Sinbad y su tripulación enfrentando criaturas mitológicas.",
    "El Septimo Cielo": "Drama familiar centrado en la vida del reverendo Eric Camden, su esposa Annie y sus siete hijos.",
    "Scooby Do": "Serie animada clásica donde Misterio a la Orden resuelve enigmas y desenmascara supuestos fantasmas y monstruos.",
    "Sailor Moon": "Las aventuras de Usagi Tsukino y las Sailor Scouts luchando contra las fuerzas del mal para proteger la Tierra.",
    "Caricaturas Clasicas": "Bloque especial con los cortometrajes y dibujos animados más emblemáticos de la época dorada de la animación.",
    "101 Dalmatas": "Serie animada basada en la historia de los dálmatas enfrentando las disparatadas ocurrencias en la granja y huyendo de Cruella.",
    "Full House": "Comedia familiar centrada en Danny Tanner y cómo cría a sus tres hijas con la ayuda de su cuñado Jesse y su amigo Joey.",
    "El Hombre Del Maletin": "Serie clásica de suspenso y espionaje que sigue las misiones y misterios de un agente enigmático.",
    "Degrassi Junior High": "Drama juvenil que retrata los desafíos, dilemas y vivencias diarias de un grupo de estudiantes de secundaria.",
    "El Chavo Del 8": "Las divertidas situaciones y vivencias del Chavo y los vecinos en la emblemática vecindad.",
    "El Chavo El 8": "Las divertidas situaciones y vivencias del Chavo y los vecinos en la emblemática vecindad.",
    "Area 12": "Serie policíaca de acción y drama centrada en la patrulla urbana y la resolución de crímenes.",
    "Babylon 5": "Serie de ciencia ficción ambientada en una estación espacial neutra en medio de tensiones diplomáticas y guerras intergalácticas.",
    "La Mujer Bionica": "Jaime Sommers utiliza sus implantes cibernéticos de alta tecnología para llevar a cabo misiones secretas del gobierno.",
    "El Monk": "Un brillante detective privado con trastorno obsesivo-compulsivo resuelve los casos más complejos de San Francisco.",
    "Chico Listo": "Un niño prodigio de 10 años asiste a la escuela secundaria adaptándose a compañeros de clase mayores que él.",
    "El Show De Los Muppets": "El clásico programa de variedades encabezado por Kermit la Rana, Miss Piggy y sus hilarantes invitados.",
    "Viaje Al Fondo Del Mar": "Serie de ciencia ficción a bordo del submarino futurista Seaview enfrentando amenazas marítimas y alienígenas.",
    "Blanco Y Negro": "Comedia de situaciones sobre dos niños de Harlem adoptados por un millonario de Manhattan.",
    "Tierra De Gigantes": "La tripulación de una nave espacial queda atrapada en un planeta habitado por seres gigantescos.",
    "Cine Estelar": "Espacio cinematográfico con la emisión de películas destacadas de acción, drama y grandes producciones.",
    "Cine Clasico": "Selección especial de películas clásicas y producciones destacadas de la época dorada del cine.",
    "Los Angeles De Charlie": "Tres intrépidas detectives privadas trabajan para una agencia de investigación resolviendo intrincados casos.",
    "Jim West": "Dos agentes del servicio secreto en el Viejo Oeste utilizan ingeniosos artilugios para proteger al país.",
    "La Casa De La Pradera": "Las emotivas vivencias de la familia Ingalls en un pequeño pueblo del oeste estadounidense a finales del siglo XIX.",
    "El Senor De Las Bestias": "Serie de fantasía sobre un guerrero capaz de comunicarse telepáticamente con los animales.",
    "Mision Imposible": "Un equipo de élite del gobierno realiza operaciones secretas e imposibles con disfraces y tecnología.",
    "Perdidos En El Espacio": "Las aventuras y peripecias de la familia Robinson intentando sobrevivir tras perder el rumbo en el espacio exterior.",
    "El Auto Fantastico": "Michael Knight y KITT, un automóvil con inteligencia artificial avanzada, combaten el crimen.",
    "El Crucero Del Amor": "Historias románticas y comedias a bordo del lujoso crucero Pacific Princess.",
    "Lady Oscar": "Serie animada ambientada en la Francia del siglo XVIII previa a la Revolución Francesa.",
    "La Novicia Rebelde": "Una joven aspirante a monja se convierte en la instructora de los siete hijos de un capitán de la marina.",
    "Odisea Burbujas": "Las aventuras del Profesor Memelovsky y sus criaturas enseñando ciencia y protegiendo el medio ambiente.",
    "Caravana": "Un grupo de pioneros atraviesa el territorio estadounidense enfrentando peligros y aventuras.",
    "Mi Bella Genio": "Un astronauta encuentra una botella mágica que alberga a una hermosa genio de dos mil años.",
    "El Chapulin Colorado": "Las cómicas aventuras del torpe pero bienintencionado superhéroe mexicano."
}

def obtener_o_generar_sinopsis(nombre_programa):
    """Busca en el diccionario o genera una descripción automática si no existe."""
    nombre_clean = nombre_programa.strip()
    
    # 1. Búsqueda exacta en la base de datos
    if nombre_clean in SINOPSIS_DB:
        return SINOPSIS_DB[nombre_clean]
    
    # 2. Búsqueda por coincidencia parcial
    for clave, sinopsis in SINOPSIS_DB.items():
        if clave.lower() in nombre_clean.lower() or nombre_clean.lower() in clave.lower():
            return sinopsis
            
    # 3. Generación automática genérica según palabras clave
    if re.search(r'Cine|Pelicula|Film', nombre_clean, re.I):
        return f"Espacio cinematográfico dedicado a la emisión de producciones de {nombre_clean}."
    elif re.search(r'Documental|Documentales', nombre_clean, re.I):
        return "Programa documental enfocado en cultura, historia, naturaleza y temas de interés general."
    elif re.search(r'Caricaturas|Animada|Dibujos', nombre_clean, re.I):
        return "Bloque de entretenimiento animado destinado a todo público."
    
    return f"Emisión regular del programa {nombre_clean}."

def ajustar_hora(hora_str, horas_a_sumar=2):
    """Suma 2 horas a un formato HH:MM (ejemplo 01:00 -> 03:00)."""
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

# 3. Descarga de la web
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
            sinopsis = obtener_o_generar_sinopsis(nombre_prog)
            
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

# 4. Armar las filas finales
filas_epg = [["Dia", "Inicio", "Fin", "Programa", "Descripcion"]]

for i in range(len(progs_weekdays)):
    p_curr = progs_weekdays[i]
    fin = progs_weekdays[i+1]["inicio"] if i < len(progs_weekdays) - 1 else progs_weekdays[0]["inicio"]
    filas_epg.append(["Weekdays", p_curr["inicio"], fin, p_curr["programa"], p_curr["descripcion"]])

for i in range(len(progs_weekend)):
    p_curr = progs_weekend[i]
    fin = progs_weekend[i+1]["inicio"] if i < len(progs_weekend) - 1 else progs_weekend[0]["inicio"]
    filas_epg.append(["Weekend", p_curr["inicio"], fin, p_curr["programa"], p_curr["descripcion"]])

# 5. Volcado a Google Sheets
sheet.clear()
sheet.update(range_name='A1', values=filas_epg)
print(f"¡Éxito! Se actualizaron {len(progs_weekdays)} programas para Weekdays y {len(progs_weekend)} para Weekend con sinopsis generadas.")
