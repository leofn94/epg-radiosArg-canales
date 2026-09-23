import os
import json
import re
import time
import urllib.parse
from datetime import datetime
import zoneinfo
import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

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

sheet = abrir_sheet_con_reintento(SPREADSHEET_ID, "CNCITY")

dias_mapa = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# 2. Diccionario de Sinopsis Local Enriquecida (CN City)
SINOPSIS_DB = {
    "duck dodgers": "El torpe e inflado héroe galáctico Duck Dodgers navega por el espacio del siglo 24 y medio junto a su fiel Cadete, intentando defender la Tierra de los malévolos planes del marciano Marvin.",
    "megas xlr": "Coop, un simpático chico amante de la comida chatarra, encuentra un robot gigante del futuro en un basurero. Tras modificarlo con controles de videojuegos, defenderá a la Tierra de letales amenazas alienígenas.",
    "hi hi puffy amiyumi": "Las superestrellas del pop japonés Ami y Yumi viajan por todo el mundo a bordo de su extravagante autobús, viviendo cómicas aventuras junto a su avaro representante Kaz.",
    "the grim adventures of billy & mandy": "Billy, un niño extremadamente despistado, y Mandy, una niña cínica y dominante, le ganan una apuesta a la Muerte (Puro Hueso), obligándolo a ser su mejor amigo para siempre.",
    "las sombrías aventuras de billy y mandy": "Billy, un niño extremadamente despistado, y Mandy, una niña cínica y dominante, le ganan una apuesta a la Muerte (Puro Hueso), obligándolo a ser su mejor amigo para siempre.",
    "dexter's laboratory": "El pequeño niño genio Dexter realiza increíbles experimentos en su laboratorio secreto oculto tras la biblioteca de su cuarto, batallando constantemente contra las travesuras de su hermana Dee Dee y su rival Mandark.",
    "el laboratorio de dexter": "El pequeño niño genio Dexter realiza increíbles experimentos en su laboratorio secreto oculto tras la biblioteca de su cuarto, batallando constantemente contra las travesuras de su hermana Dee Dee y su rival Mandark.",
    "cow and chicken": "Vaca y Pollito son dos hermanos biológicos muy peculiares que lidian con la vida escolar cotidiana mientras evitan los retorcidos planes del Trasero Rojo, con la imprevista ayuda de Súper Vaca.",
    "la vaca y el pollito": "Vaca y Pollito son dos hermanos biológicos muy peculiares que lidian con la vida escolar cotidiana mientras evitan los retorcidos plans del Trasero Rojo, con la imprevista ayuda de Súper Vaca.",
    "the marvelous misadventures of flapjack": "El ingenuo niño Flapjack y el veterano Capitán Nudillos exploran los peligrosos mares desde la Ciudad Marea Alta, buscando obsesivamente la mítica Isla Caramelizada.",
    "las maravillosas desventuras de flapjack": "El ingenuo niño Flapjack y el veterano Capitán Nudillos exploran los peligrosos mares desde la Ciudad Marea Alta, buscando obsesivamente la mítica Isla Caramelizada.",
    "johnny bravo": "Con su copete perfecto, gafas de sol y desbordante confianza, Johnny Bravo busca incansablemente conquistar al amor de su vida, metiéndose continuamente en aprietos por su vanidad e ingenio torpe.",
    "foster's home for imaginary friends": "Cuando Mac debe despedirse de su amigo imaginario Bloo, lo lleva al hogar de adopción de la Sra. Foster, un lugar fantástico habitado por cientos de coloridas e insólitas criaturas.",
    "mansión foster para amigos imaginarios": "Cuando Mac debe despedirse de su amigo imaginario Bloo, lo lleva al hogar de adopción de la Sra. Foster, un lugar fantástico habitado por cientos de coloridas e insólitas criaturas.",
    "courage the cowardly dog": "En medio del desolado poblado de Ningún Lugar, el miedoso perro Coraje debe reunir valor para proteger a sus amables dueños, Muriel y Justo, de espeluznantes amenazas sobrenaturales.",
    "coraje el perro cobarde": "En medio del desolado poblado de Ningún Lugar, el miedoso perro Coraje debe reunir valor para proteger a sus amables dueños, Muriel y Justo, de espeluznantes amenazas sobrenaturales.",
    "robotboy": "Un androide altamente avanzado capaz de transformarse en una destructiva máquina de combate aprende a vivir como un niño normal bajo la custodia del joven Tommy Turnbull y sus amigos.",
    "dragon ball z": "Goku y los Guerreros Z protegen a la Tierra y al universo de temibles amenazas como saiyajins, tiranos espaciales y androides en batallas de poder verdaderamente épicas.",
    "codename: kids next door": "Cinco intrépidos niños de diez años operan en una casa del árbol de alta tecnología como el Sector V, luchando contra la tiranía de los adultos y los adolescentes para defender los derechos infantiles.",
    "los chicos del barrio": "Cinco intrépidos niños de diez años operan en una casa del árbol de alta tecnología como el Sector V, luchando contra la tiranía de los adultos y los adolescentes para defender los derechos infantiles.",
    "what's new scooby-doo?": "Scooby-Doo y la pandilla de Misterio a la Orden regresan con tecnología moderna para resolver enigmas tenebrosos alrededor del mundo, desenmascarando a falsos monstruos.",
    "¿qué hay de nuevo, scooby-doo?": "Scooby-Doo y la pandilla de Misterio a la Orden regresan con tecnología moderna para resolver enigmas tenebrosos alrededor del mundo, desenmascarando a falsos monstruos.",
    "ed, edd n' eddy": "Tres niños llamados Ed con personalidades completamente opuestas idean disparatados e ingeniados planes en el vecindario para conseguir dinero y comprar enormes caramelos.",
    "totally spies!": "Tres adolescentes de Beverly Hills —Sam, Clover y Alex— combinan sus vidas escolares cotidianas con misiones encubiertas como agentes secretas de la organización WOOHP.",
    "tres espías sin límite": "Tres adolescentes de Beverly Hills —Sam, Clover y Alex— combinan sus vidas escolares cotidianas con misiones encubiertas como agentes secretas de la organización WOOHP.",
    "¡mucha lucha!": "Rikochet, Buena Niña y Pulga asisten a una prestigiosa academia de lucha libre donde aprenden a dominar el Honor, la Familia, la Tradición y sus movimientos especiales.",
    "the life and times of juniper lee": "Juniper Lee mantiene el equilibrio entre el mundo humano y el mágico en la ciudad de Orchid Bay, protegiendo a los civiles de monstruos sin descuidar sus deberes escolares.",
    "ben 10": "El joven Ben Tennyson descubre el Omnitrix, un misterioso reloj alienígena que le permite transformarse en diez poderosos extraterrestres para combatir el mal.",
    "naruto": "Naruto Uzumaki, un joven ninja marginado que lleva en su interior al Zorro de Nueve Colas, entrena sin descanso para convertirse en Hokage y ganar el respeto de su aldea.",
    "teen titans": "Robin, Cyborg, Raven, Starfire y Chico Bestia unen sus habilidades extraordinarias para proteger Jump City como un dinámico equipo de jóvenes superhéroes.",
    "los jóvenes titanes": "Robin, Cyborg, Raven, Starfire y Chico Bestia unen sus habilidades extraordinarias para proteger Jump City como un dinámico equipo de jóvenes superhéroes.",
    "ben 10: alien force": "Cinco años después de quitarse el Omnitrix, Ben Tennyson, de 15 años, debe colocárselo de nuevo para reclutar a un equipo y salvar a la Tierra de la invasión Highbreed.",
    "generator rex": "Rex Salazar es un joven capaz de hacer crecer impresionante tecnología de su cuerpo gracias a nanites, trabajando para la organización Providencia.",
    "justice league unlimited": "Superman, Batman, Mujer Maravilla y docenas de superhéroes expanden su equipo en la Liga de la Justicia para defender al universo entero de amenazas cósmicas.",
    "tom and jerry": "El gato Tom y el astuto ratón Jerry se enfrascan en las persecuciones más divertidas y clásicas de la televisión, llenas de slapstick y comedia atemporal.",
    "looney tunes": "Bugs Bunny, el Pato Lucas, Porky y el icónico elenco de personajes de Warner Bros. protagonizan disparatados cortometrajes llenos de ingenio y humor inolvidable.",
    "pokémon": "Ash Ketchum y su Pikachu recorren diversas regiones capturando criaturas Pokémon, ganando medallas de gimnasio y buscando cumplir el sueño de ser un Maestro Pokémon.",
    "pokemon": "Ash Ketchum y su Pikachu recorren diversas regiones capturando criaturas Pokémon, ganando medallas de gimnasio y buscando cumplir el sueño de ser un Maestro Pokémon.",
    "the powerpuff girls": "Nacidas del azúcar, las especias, las cosas bonitas y la Sustancia X, las hermanas Bombón, Burbuja y Bellota protegen a Saltadilla de villanos como Mojo Jojo.",
    "las chicas superpoderosas": "Nacidas del azúcar, las especias, las cosas bonitas y la Sustancia X, las hermanas Bombón, Burbuja y Bellota protegen a Saltadilla de villanos como Mojo Jojo.",
    "code lyoko": "Un grupo de estudiantes de internado descubre un superordenador que alberga el mundo virtual de Lyoko, luchando contra el malvado virus X.A.N.A. para proteger al mundo.",
    "samurai jack": "Un noble guerrero samurái es enviado a un futuro distópico controlado por el demonio Aku, emprendiendo un viaje interminable para regresar al pasado.",
    "xiaolin showdown": "Cuatro jóvenes monjes entrenan para dominar las artes marciales y proteger los poderosos objetos místicos Shen Gong Wu de las fuerzas del mal.",
    "atomic betty": "Para sus amigos es una niña común y corriente, pero en secreto Betty Barrett es una Guardiana Galáctica que protege el cosmos de malévolos extraterrestres.",
    "one piece": "Monkey D. Luffy y los Piratas de Sombrero de Paja navegan por la Gran Ruta buscando el tesoro legendario para convertirse en el próximo Rey de los Piratas.",
    "saint seiya": "Los Caballeros del Zodiaco visten sus armaduras sagradas para proteger a la reencarnación de la diosa Atenea librando intensas batallas cósmicas.",
    "los caballeros del zodiaco": "Los Caballeros del Zodiaco visten sus armaduras sagradas para proteger a la reencarnación de la diosa Atenea librando intensas batallas cósmicas.",
    "yu yu hakusho: ghost files": "Tras morir salvando a un niño, el joven rebelde Yusuke Urameshi es revivido como Detective Espiritual para investigar casos sobrenaturales en el mundo humano.",
    "rurouni kenshin": "Kenshin Himura, un legendario exasesino que ha jurado no volver a matar, viaja por el Japón de la era Meiji protegiendo a los inocentes con su espada de filo invertido.",
    "aqua teen hunger force": "Una caja de papas fritas, un batido de chocolate y una bola de carne picada viven como vecinos en Nueva Jersey, envueltos en las situaciones más absurdas del bloque nocturno.",
    "the boondocks": "Huey y Riley Freeman son dos hermanos que se mudan con su abuelo a un suburbio predominantemente blanco, enfrentando temas culturales con una sátira social afilada.",
    "robot chicken": "Sketches veloces y parodias ácidas de la cultura pop, cómics y televisión realizadas completamente en animación stop-motion con muñecos y figuras de acción.",
    "harvey birdman, attorney at law": "El antiguo superhéroe ex-cohete opera ahora como abogado defensor representando a clásicos personajes de caricaturas en disparatados juicios legales.",
    "sealab 2021": "La tripulación incompetente de una investigación submarina enfrenta absurdas crisis cotidianas bajo una disparatada convivencia sin sentido.",
    "space ghost coast to coast": "El héroe intergaláctico Fantasma del Espacio conduce su propio programa de entrevistas nocturno recibiendo a celebridades humanas en un ambiente surrealista.",
    "clone high": "Clones genéticos de figuras históricas como Abraham Lincoln, Cleopatra y Gandhi asisten juntos a la escuela secundaria mientras atraviesan los dramas típicos de la adolescencia."
}

CACHE_SINOPSIS = {}

def normalizar_nombre_programa(nombre_programa):
    """Limpia caracteres indeseados y sufijos como x2, x 2, etc."""
    clean = re.sub(r'\bEN VIVO\b', '', nombre_programa, flags=re.I)
    clean = re.sub(r'\bx\s*\d+\b', '', clean, flags=re.I)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def buscar_en_tmdb_espanol(titulo):
    """Consulta la API de TMDb pidiendo el resumen en español latino (es-MX)."""
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
    1. Revisa si está en la DB local.
    2. Si no, busca en TMDb.
    3. Si falla todo, retorna cadena vacía "".
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
        # Búsqueda parcial en DB local
        for k, v in SINOPSIS_DB.items():
            if k in key_norm or key_norm in k:
                sinopsis_encontrada = v
                break

    # 2. Búsqueda en TMDb si no estuvo en DB local
    if not sinopsis_encontrada:
        sinopsis_encontrada = buscar_en_tmdb_espanol(clean)

    CACHE_SINOPSIS[clean] = sinopsis_encontrada
    return sinopsis_encontrada

def limpiar_texto_programa(texto_raw):
    texto = re.sub(r'\b\d{1,3}\s*min\b', '', texto_raw, flags=re.I)
    texto = re.sub(r'(Agendar|Google Calendar|Descargar|\.ics|18\+|13\+|TODOS)', '', texto, flags=re.I)
    return re.sub(r'\s+', ' ', texto).strip()

# --- SCRAPING DE CNCITY ---
url = "https://cncity.live/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        timezone_id="America/Argentina/Buenos_Aires",
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    try:
        grilla_btn = page.get_by_text("GRILLA", exact=False).first
        if grilla_btn.is_visible():
            grilla_btn.click()
            page.wait_for_timeout(2000)
    except Exception as e:
        print("Aviso al ingresar a Grilla:", e)

    try:
        arg_btn = page.get_by_text("ARGENTINA", exact=False).first
        if arg_btn.is_visible():
            arg_btn.click()
            page.wait_for_timeout(2000)
    except Exception as e:
        print("Aviso al seleccionar Argentina:", e)

    for _ in range(3):
        page.evaluate("window.scrollBy(0, 800)")
        page.wait_for_timeout(1000)

    html_content = page.content()
    browser.close()

soup = BeautifulSoup(html_content, "html.parser")
bloques = soup.find_all("article")
if not bloques:
    bloques = soup.find_all(["div", "tr", "li"], class_=re.compile(r'item|card|program|schedule|show|event', re.I))

tz_local = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")
indice_dia = datetime.now(tz_local).weekday()

programas_raw = []

for b in bloques:
    texto_art = b.get_text(" ", strip=True)
    matches_hora = re.findall(r'\b\d{1,2}:\d{2}\b', texto_art)
    if len(matches_hora) > 2 or not matches_hora:
        continue
        
    hora_ini = matches_hora[0]
    if len(hora_ini) == 4:
        hora_ini = "0" + hora_ini

    texto_sin_hora = re.sub(r'^\d{1,2}:\d{2}\s*', '', texto_art)
    programa_completo = limpiar_texto_programa(texto_sin_hora)

    if not programa_completo or len(programa_completo) < 2:
        continue

    programas_raw.append({
        "inicio": hora_ini,
        "programa": programa_completo
    })

# --- PROCESAMIENTO Y UNIFICACIÓN DE BLOQUES CONTINUOS ---
bloques_individuales = []

for i in range(len(programas_raw)):
    p_curr = programas_raw[i]
    
    if i > 0:
        hora_prev = programas_raw[i-1]["inicio"]
        hora_curr = p_curr["inicio"]
        if hora_prev >= "20:00" and hora_curr < "06:00":
            indice_dia = (indice_dia + 1) % 7

    dia_nombre = dias_mapa[indice_dia]

    if i < len(programas_raw) - 1:
        fin = programas_raw[i+1]["inicio"]
    else:
        fin = programas_raw[0]["inicio"]

    prog_norm = normalizar_nombre_programa(p_curr["programa"])

    bloques_individuales.append({
        "dia": dia_nombre,
        "inicio": p_curr["inicio"],
        "fin": fin,
        "programa": prog_norm
    })

# Unificar programas continuos
bloques_unificados = []
bloque_actual = None

for b in bloques_individuales:
    if bloque_actual is None:
        bloque_actual = b
    else:
        if b["programa"].lower() == bloque_actual["programa"].lower() and b["dia"] == bloque_actual["dia"]:
            bloque_actual["fin"] = b["fin"]
        else:
            bloques_unificados.append(bloque_actual)
            bloque_actual = b

if bloque_actual is not None:
    bloques_unificados.append(bloque_actual)

# Armado final con sinopsis
filas_epg = [
    ["Dia", "Inicio", "Fin", "Programa", "Descripcion"]
]

for b in bloques_unificados:
    sinopsis = obtener_sinopsis(b["programa"])
    filas_epg.append([b["dia"], b["inicio"], b["fin"], b["programa"], sinopsis])

# --- VOLCADO A GOOGLE SHEETS ---
sheet.clear()
sheet.update(range_name='A1', values=filas_epg)
print(f"¡Éxito! Se actualizaron {len(filas_epg)-1} registros en CNCITY.")
