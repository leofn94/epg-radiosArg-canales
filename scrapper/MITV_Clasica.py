import os
import json
import re
import time
import urllib.parse
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

# API Key de TMDb desde GitHub Secrets
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")

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

# 2. Diccionario de Sinopsis Enriquecidas Local
SINOPSIS_DB = {
    "las aventuras de sinbad": "Zarpando hacia lo desconocido, el audaz capitán Sinbad y su diversa tripulación surcan mares mágicos enfrentando temibles monstruos marinos, poderosos hechiceros y mitos legendarios en busca de valiosos tesoros y la justicia.",
    "el septimo cielo": "El reverendo Eric Camden y su esposa Annie guían a sus siete hijos a través de las complejidades del crecimiento, la fe, las tentaciones de la adolescencia y los dilemas morales del día a día en una conmovedora historia familiar.",
    "scooby do": "A bordo de la Máquina del Misterio, Fred, Daphne, Velma, Shaggy y el asustadizo perro Scooby-Doo recorren el país investigando apariciones sobrenaturales para desenmascarar a los villanos reales que se esconden tras las máscaras.",
    "sailor moon": "Usagi Tsukino es una estudiante ordinaria cuya vida cambia por completo al descubrir que es la reencarnación de una legendaria guerrera. Junto a las demás Sailor Guardians, defenderá a la Tierra y al universo de las fuerzas de la oscuridad.",
    "caricaturas clasicas": "Una cuidada selección con los cortometrajes inolvidables que marcaron la época dorada de la animación. Disfruta de la persecución constante, el humor slapstick y las locuras inolvidables de tus personajes favoritos de la infancia.",
    "101 dalmatas": "En una colorida granja, los intrépidos cachorros dálmatas Lucky, Rolly y Cadpig exploran su entorno y viven emocionantes aventuras diarias, ingeniándoselas para eludir las malévolas estratagemas de la obsesiva Cruella de Vil.",
    "full house": "Tras la trágica pérdida de su esposa, el presentador de noticias Danny Tanner recluta a su cuñado roquero Jesse y a su mejor amigo comediante Joey para ayudarlo a criar a sus tres dinámicas hijas: DJ, Stephanie y la pequeña Michelle.",
    "el hombre del maletin": "Un enigmático exagente de inteligencia viaja por el mundo resolviendo misiones impossibles y casos de alto riesgo. Su única herramienta es su agudo intelecto y un maletín repleto de dispositivos de alta tecnología e identidades falsas.",
    "degrassi junior high": "Con una mirada cruda y realista a la etapa de la adolescencia, un grupo de estudiantes de secundaria se enfrenta a la presión social, los primeros amores, la búsqueda de identidad y los imprevistos dilemas de la juventud.",
    "el chavo del 8": "Las disparatadas vivencias de un niño huérfano que vive dentro de un barril y desata toda clase de enredos, malentendidos y momentos cómicos junto a Don Ramón, Quico, La Chilindrina y los peculiares habitantes de la vecindad.",
    "el chavo el 8": "Las disparatadas vivencias de un niño huérfano que vive dentro de un barril y desata toda clase de enredos, malentendidos y momentos cómicos junto a Don Ramón, Quico, La Chilindrina y los peculiares habitantes de la vecindad.",
    "area 12": "Los oficiales de patrulla Pete Malloy y Jim Reed recorren las calles de Los Ángeles velando por la seguridad ciudadana. Cada jornada los enfrenta a persecuciones a alta velocidad, robos armados y dramas humanos al límite.",
    "babylon 5": "En una colosal estación espacial de cinco millas de largo diseñada como territorio neutral, diplomáticos humanos y alienígenas intentan mantener una frágil paz galáctica mientras oscuras conspiraciones amenazan con desatar la guerra.",
    "la mujer bionica": "Tras sufrir un trágico accidente de paracaidismo, la tenista Jaime Sommers es reconstruida con implantes cibernéticos que le otorgan fuerza, velocidad y un oído sobrehumanos, los cuales usa para trabajar como agente secreta.",
    "el monk": "Adrian Monk es un brillante detective privado de San Francisco cuya agudeza inductiva es impecable, pero debe lidiar constantemente con su trastorno obsesivo-compulsivo y fobias para resolver los crímenes más intrincados.",
    "chico listo": "TJ Henderson es un niño prodigio de solo 10 años cuya superinteligencia lo lleva directamente a la escuela secundaria. Allí deberá aprender a encajar entre estudiantes mucho mayores, incluyendo a sus propios hermanos.",
    "el show de los muppets": "Kermit la Rana intenta coordinar entre bambalinas un disparatado programa de variedades repleto de marionetas chifladas, sketches cómicos, números musicales y estrellas invitadas internacionales de primer nivel.",
    "viaje al fondo del mar": "El submarino nuclear Seaview explora las profundidades del océano bajo el mando del almirante Nelson y el capitán Crane, enfrentando no solo amenazas marinas y espías internacionales, sino también misteriosas criaturas.",
    "blanco y negro": "Un adinerado viudo de la Quinta Avenida adopta a Arnold y Willis, dos hermanos afroamericanos huérfanos de Harlem, dando paso a una conmovedora comedia de adaptación, valores familiares y reflexiones sociales.",
    "tierra de gigantes": "Tras atravesar una tormenta espacial, la nave Spindrift realiza un aterrizaje forzoso en un planeta idéntico a la Tierra, pero donde todo tiene doce veces su tamaño normal y sus habitantes consideran a los viajeros como fugitivos.",
    "cine estelar": "La pantalla se ilumina con grandes producciones cinematográficas, éxitos de taquilla y memorables historias de acción, suspenso y romance protagonizadas por las estrellas más icónicas de la industria.",
    "cine clasico": "Un recorrido por las joyas doradas del séptimo arte. Obras maestras, dramas intensos y comedias inolvidables que definieron la historia del cine mundial y cautivaron a generaciones enteras.",
    "los angeles de charlie": "Sabrina, Jill y Kelly son tres audaces e inteligentes exoficiales de policía contratadas por la agencia privada del misterioso millonario Charles Townsend para resolver peligrosos casos encubiertos.",
    "jim west": "En el intrépido Viejo Oeste, los agentes secretos Jim West y Artemus Gordon utilizan un tren blindado de alta tecnología y disfraces para detener a malévolos villanos que amenazan la seguridad de la nación.",
    "la casa de la pradera": "A finales del siglo XIX, la abnegada familia Ingalls lucha por salir adelante en la frontera estadounidense, viviendo momentos de amor, superación, fe y solidaridad comunitaria en el pintoresco poblado de Walnut Grove.",
    "el senor de las bestias": "Dotado con la capacidad única de comunicarse telepáticamente con los animales y apoyado por una pantera, un hurón y un águila, el guerrero Dar recorre tierras fantásticas combatiendo las fuerzas del mal.",
    "mision imposible": "Jim Phelps encabeza al equipo IMF, un grupo de élite especializado en infiltraciones, ingeniería de engaño y tecnología avanzada diseñado para desarticular amenazas internacionales que nadie más puede detener.",
    "perdidos en el espacio": "Rumbo al sistema Alfa Centauri, la nave de la familia Robinson es saboteada por el malicioso Dr. Smith, dejándolos a la deriva en un universo desconocido donde deberán sobrevivir a extraños mundos alienígenas.",
    "el auto fantastico": "El detective dado por muerto Michael Knight recibe una nueva identidad para combatir a los criminales fuera del alcance de la ley, respaldado por K.I.T.T., un prototipo de automóvil deportivo dotado de inteligencia artificial.",
    "el crucero del amor": "A bordo del lujoso trasatlántico Pacific Princess, pasajeros de todas las edades se embarcan en viajes llenos de enredos románticos y comedia, guiados por la carismática tripulación liderada por el Capitán Stubing.",
    "lady oscar": "En la Francia del siglo XVIII prerrevolucionaria, Oscar François de Jarjayes es criada como un hombre por su padre militar. Convertida en comandante de la guardia real, deberá proteger a María Antonieta entre conspiraciones.",
    "la novicia rebelde": "Maria, una alegre y libre postulante a monja, es enviada a la mansión del estricto capitán Von Trapp para ser la institutriz de sus siete hijos, devolviendo la música, las risas y el amor al hogar familiar.",
    "odisea burbujas": "El sabio Profesor Memelovsky, junto a Patas Verdes, Mimoso Ratón, Mafafa Musguito y Pistachón Zig-Zag, viajan por el tiempo y el espacio aprendiendo ciencia y desbaratando los mugrosos planes del Ecoloco.",
    "caravana": "Una extensa fila de carretas encabezada por el mayor Adams emprende una peligrosa travesía desde Misuri hasta California, enfrentando terrenos hostiles, desastres naturales y dramas personales entre los viajeros.",
    "mi bella genio": "Tras estrellarse en una isla desierta, el astronauta Tony Nelson encuentra una botella mística que alberga a Jeannie, una hermosa y juguetona genio que insiste en concederle todos sus deseos con inesperados resultados.",
    "el chapulin colorado": "Con su Chipote Chillón y las Pastillas de Chiquitolina, este héroe de corazón puro pero sumamente torpe acude al rescate de quienes lo necesitan, superando sus propios miedos con un humor inolvidable."
}

CACHE_SINOPSIS = {}

def normalizar_nombre_programa(nombre_programa):
    """Limpia caracteres indeseados y sufijos como x2, x 2, etc."""
    clean = re.sub(r'\bEN VIVO\b', '', nombre_programa, flags=re.I)
    clean = re.sub(r'\bx\s*\d+\b', '', clean, flags=re.I)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def buscar_en_tmdb_espanol(titulo):
    """Consulta la API de TMDb pidiendo la sinopsis en español latino (es-MX)."""
    if not TMDB_API_KEY:
        return ""
        
    try:
        titulo_clean = re.sub(r'\b(BLOQUE|RUN A|RUN B|SEASON 1|FUN B)\b', '', titulo, flags=re.I).strip()
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
    1. Busca en el diccionario local.
    2. Si no la encuentra, busca en TMDb.
    3. Si no existe en TMDb, devuelve cadena vacía "".
    """
    clean = normalizar_nombre_programa(nombre_programa)
    
    if clean in CACHE_SINOPSIS:
        return CACHE_SINOPSIS[clean]

    key_norm = clean.lower()
    
    # 1. Búsqueda en DB Local
    sinopsis_encontrada = ""
    if key_norm in SINOPSIS_DB:
        sinopsis_encontrada = SINOPSIS_DB[key_norm]
    else:
        for k, v in SINOPSIS_DB.items():
            if k in key_norm or key_norm in k:
                sinopsis_encontrada = v
                break

    # 2. Búsqueda en TMDb si no estuvo en DB local
    if not sinopsis_encontrada:
        sinopsis_encontrada = buscar_en_tmdb_espanol(clean)

    CACHE_SINOPSIS[clean] = sinopsis_encontrada
    return sinopsis_encontrada

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
        nombre_prog = normalizar_nombre_programa(nombre_prog)
        
        if nombre_prog and len(nombre_prog) > 1 and len(nombre_prog) < 80:
            item = {
                "inicio": hora_ajustada, 
                "programa": nombre_prog
            }
            
            if modo_actual == "Weekdays":
                if not progs_weekdays or progs_weekdays[-1]["inicio"] != hora_ajustada:
                    progs_weekdays.append(item)
            else:
                if not progs_weekend or progs_weekend[-1]["inicio"] != hora_ajustada:
                    progs_weekend.append(item)

# 4. Cálculo de rangos individuales (Inicio / Fin)
bloques_individuales = []

# Procesar Weekdays
for i in range(len(progs_weekdays)):
    p_curr = progs_weekdays[i]
    fin = progs_weekdays[i+1]["inicio"] if i < len(progs_weekdays) - 1 else progs_weekdays[0]["inicio"]
    bloques_individuales.append({
        "dia": "Weekdays",
        "inicio": p_curr["inicio"],
        "fin": fin,
        "programa": p_curr["programa"]
    })

# Procesar Weekend
for i in range(len(progs_weekend)):
    p_curr = progs_weekend[i]
    fin = progs_weekend[i+1]["inicio"] if i < len(progs_weekend) - 1 else progs_weekend[0]["inicio"]
    bloques_individuales.append({
        "dia": "Weekend",
        "inicio": p_curr["inicio"],
        "fin": fin,
        "programa": p_curr["programa"]
    })

# 5. Unificación de bloques continuos consecutivos
bloques_unificados = []
bloque_actual = None

for b in bloques_individuales:
    if bloque_actual is None:
        bloque_actual = b
    else:
        # Si el programa es idéntico y pertenece al mismo bloque de días, unificar
        if b["programa"].lower() == bloque_actual["programa"].lower() and b["dia"] == bloque_actual["dia"]:
            bloque_actual["fin"] = b["fin"]
        else:
            bloques_unificados.append(bloque_actual)
            bloque_actual = b

if bloque_actual is not None:
    bloques_unificados.append(bloque_actual)

# 6. Armado final de la tabla con sinopsis
filas_epg = [["Dia", "Inicio", "Fin", "Programa", "Descripcion"]]

for b in bloques_unificados:
    sinopsis = obtener_sinopsis(b["programa"])
    filas_epg.append([b["dia"], b["inicio"], b["fin"], b["programa"], sinopsis])

# 7. Volcado a Google Sheets
sheet.clear()
sheet.update(range_name='A1', values=filas_epg)
print(f"¡Éxito! Se actualizaron {len(filas_epg)-1} registros unificados en MITV.")
