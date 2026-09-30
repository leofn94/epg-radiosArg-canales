import os
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pytz
import requests
import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# ==========================================
# 1. CONFIGURACIÓN Y GOOGLE SHEETS
# ==========================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

gcp_key = os.environ.get("GCP_SA_KEY")
if not gcp_key:
    raise ValueError("No se encontró GCP_SA_KEY en las variables de entorno.")

credentials_info = json.loads(gcp_key)
credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
client = gspread.authorize(credentials)

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
SPREADSHEET_ID = "1JKs0R5aFs4uWMBFDAuVtf2-hDDYd87ZkibTqFV600Rs"
NOMBRE_PESTANA = "TLMAS"

DIAS_SEMANA_ES = {
    "monday": "Lunes",
    "tuesday": "Martes",
    "wednesday": "Miércoles",
    "thursday": "Jueves",
    "friday": "Viernes",
    "saturday": "Sábado",
    "sunday": "Domingo"
}

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
                print(f"Error {code} en Google API. Reintentando en {espera}s...")
                time.sleep(espera)
            else:
                raise e

sheet = abrir_sheet_con_reintento(SPREADSHEET_ID, NOMBRE_PESTANA)

# ==========================================
# 2. INTERCEPTAR FETCH/XHR DEL XML ACTIVO
# ==========================================

def obtener_xml_activo_por_intercepcion():
    xml_url_encontrada = []

    def manejar_peticion(request):
        url = request.url
        if ".xml" in url.lower() and "m3u8" not in url.lower():
            print(f"Petición de red XML capturada: {url}")
            xml_url_encontrada.append(url)

    print("Iniciando navegador invisible para capturar peticiones Fetch/XHR...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("request", manejar_peticion)
        
        try:
            page.goto("https://tlmas.kift.live/inicio/", timeout=15000, wait_until="networkidle")
        except Exception as e:
            print("Página cargada o interrupción de tiempo de espera recibida.")
        
        browser.close()

    if xml_url_encontrada:
        return xml_url_encontrada[0]
    
    print("⚠️ No se interceptó ningún .xml en las peticiones. Usando URL fallback.")
    return "https://tlmas.kift.live/assets/xml/epg/Telemas/Semana/14.09.26.12.00.xml"

# ==========================================
# 3. BASE DE DATOS LOCAL Y BÚSQUEDA SINOPSIS
# ==========================================

SINOPSIS_DB = {
    "inuyasha": "Kagome Higurashi es una joven moderna que cae en un pozo sagrado y viaja al Japón feudal, donde libera al semidemonio Inuyasha para recolectar los fragmentos de la Joya de las Cuatro Almas.",
    "hitoribocchi no seikatsu": "Hitori Bocchi sufre de extrema ansiedad social. Al entrar a la secundaria, intenta cumplir la promesa a su única amiga de la infancia: hacerse amiga de todos sus compañeros de clase.",
    "yuru camp": "Rin es una chica que disfruta acampando sola en el monte Fuji, pero su vida cambia cuando conoce a Nadeshiko, una entusiasta joven que ama acampar en grupo.",
    "kono subarashii sekai ni shukufuku wo!": "Kazuma Satou muere de forma ridícula y renace en un mundo de fantasía junto a una diosa inútil llamada Aqua, formando un grupo de aventureros muy peculiar.",
    "my deer friend nokotan": "Torako Koshi es una estudiante perfecta de preparatoria cuya vida cambia drásticamente cuando rescata a Nokotan, una extraña chica con astas de ciervo.",
    "one piece": "Monkey D. Luffy se embarca en un viaje por el mar junto a su tripulación de Piratas de Sombrero de Paja para encontrar el tesoro legendario One Piece y convertirse en el Rey de los Piratas.",
    "naruto": "Naruto Uzumaki es un joven ninja hiperactivo que busca el reconocimiento de su aldea y sueña con convertirse en el Hokage, el líder de su comunidad.",
    "lucky star": "Sigue las divertidas e ingeniosas vivencias cotidianas de un grupo de cuatro chicas de secundaria encabezadas por Konata Izumi, una chica otaku y perezosa.",
    "city the animation": "Una comedia disparatada ambientada en una ciudad común y corriente pero llena de habitantes excéntricos cuyas vidas se entrelazan en situaciones cómicas.",
    "nichijou": "La vida diaria de un grupo de estudiantes de secundaria e inusuales residentes, desde una robot hasta un gato parlante, enfrentando situaciones absurdas y exageradas.",
    "girls' last tour": "Chito y Yuuri viajan sobre su vehículo Kettenkrad a través de las ruinas desoladas de una civilización futurista colapsada, buscando comida y combustible día a día.",
    "frieren: más allá del final del viaje": "Décadas después de derrotar al Rey Demonio, la elfa Frieren emprende un viaje de autodescubrimiento para comprender mejor los sentimientos humanos tras la muerte de un viejo compañero.",
    "shijou saikyou no deshi kenichi": "Kenichi Shirahama sufre acoso escolar, pero decide entrenar en un dojo donde se concentran maestros legendarios de diversas artes marciales.",
    "jujutsu kaisen": "Yuji Itadori se traga un amuleto maldito con la fuerza de un poderoso demonio y se une a la Academia de Hechicería para eliminar maldiciones de este mundo.",
    "kirakira☆pretty cure": "Un grupo de chicas pastelera de secundaria se transforma en las legendarias guerreras Precure para proteger los dulces y el poder del 'KiraKiraru'.",
    "las quintillizas": "Futaro Uesugi es contratado como tutor académico privado para cinco hermanas idénticas que odian estudiar pero deben aprobar la preparatoria.",
    "heartcatch precure": "Tsubomi Hanasaki y Erika Kurumi se transforman en las legendarias guerreras Pretty Cure para proteger el Árbol del Corazón y los sueños de la gente de los Apóstoles del Desierto.",
    "initial d": "Takumi Fujiwara es un joven repartidor de tofu que demuestra un talento innato conduciendo su Toyota AE86 por las carreteras de montaña de Akina.",
    "full metal alchemists": "Los hermanos Edward y Alphonse Elric utilizan la alquimia prohibida para intentar resucitar a su madre, pagando un alto precio que intentarán reparar buscando la Piedra Filosofal.",
    "kiteretsu: el primo mas listo de debita": "Kiteretsu es un niño genio inventor que usa el libro de sus antepasados para construir inventos increíbles junto a su robot Korosuke.",
    "kiteretsu: el primo mas listo de nobita": "Kiteretsu es un niño genio inventor que usa el libro de sus antepasados para construir inventos increíbles junto a su robot Korosuke.",
    "k-on!": "Cuatro chicas de preparatoria se unen al club de música ligera de su escuela para salvarlo de ser desmantelado, formando la banda Ho-kago Tea Time.",
    "adachi to shimamura": "Adachi y Shimamura se conocen en el segundo piso del gimnasio escolar y desarrollan una amistad muy cercana que lentamente evoluciona.",
    "los justicieros": "Lina Inverse, una poderosa y codiciosa hechicera, viaja por el mundo enfrentándose a monstruos, bandidos y fuerzas oscuras con poderosos hechizos mágicos.",
    "re:zero kara hajimeru isekai seikatsu": "Subaru Natsuki es transportado repentinamente a un mundo fantástico donde descubre que tiene la habilidad de 'Regreso por Muerte' cada vez que fallece.",
    "evangelion": "Shinji Ikari es reclutado por su padre para pilotar un bio-meca gigante llamado Evangelion y defender a la humanidad del ataque de misteriosos seres conocidos como Ángeles.",
    "amagami-san chi no enmusubi": "Uryu Kamiki intenta ingresar a la facultad de medicina mientras vive en un templo con tres hermanas sacerdotisas.",
    "komi-san no puede comunicarse": "Komi-san padece un severo trastorno de comunicación, pero junto a Tadano intentará cumplir su sueño de hacer 100 amigos.",
    "bocchi the rock!": "Hitori Gotou es una chica introvertida que sueña con tocar en una banda de rock, enfrentando sus miedos sociales con su guitarra.",
    "umamusume: pretty derby": "Chicas caballo con habilidades de carrera sobrehumanas entrenan para convertirse en las mejores atletas de la nación.",
    "bleach": "Ichigo Kurosaki obtiene los poderes de un Shinigami para proteger a los inocentes de los espíritus malignos llamados Hollows.",
    "love live": "Un grupo de estudiantes decide convertirse en idols escolares para evitar el cierre de su escuela.",
    "love live!": "Un grupo de estudiantes decide convertirse en idols escolares para evitar el cierre de su escuela.",
    "onimai: i'm now your sister!": "Mahiro Oyama es un otaku encerrado en su casa cuya vida cambia cuando su hermana menor Mahiro lo transforma experimentalmente en una chica.",
    "puella magi madoka magica": "Madoka Kaname y Sayaka Miki reciben la oferta de convertirse en chicas mágicas a cambio de concederles un deseo, pero descubren la oscura realidad detrás de ese contrato.",
    "kao ni denai kashiwada-san": "Kashiwada-san es una chica con una expresión totalmente inexpresiva, mientras que Oota intenta constantemente sacarle una reacción.",
    "devil may cry": "Dante regenta una agencia que acepta trabajos relacionados con cazas de demonios y misterios sobrenaturales.",
    "alya sometimes hides her feelings in russian": "Alya es una estudiante transferida ruso-japonesa que suele hacer comentarios cariñosos en ruso a su compañero Kuze pensando que no le entiende.",
    "black lagoon": "Rokuro Okajima es secuestrado por un grupo de mercenarios piratas modernos en Tailandia y decide unirse a ellos adoptando el apodo 'Rock'.",
    "monster": "El Dr. Kenzo Tenma salva la vida de un niño herido en lugar de un político relevante, desencadenando una cadena de eventos macabros al descubrir que el niño creció para convertirse en un sociópata.",
    "91 days": "Angelo Lagusa regresa a su ciudad natal bajo el nombre de Avilio Bruno para vengarse de la familia de la mafia que asesinó a sus padres y a su hermano.",
    "ajin": "Kei Nagai descubre que es un 'Ajin', un ser inmortal perseguido por los gobiernos del mundo para experimentar con sus poderes.",
    "planetes": "Sigue a un grupo de recolectores de basura espacial que trabajan a bordo de la nave DS-12 recopilando desechos orbitales para proteger las naves espaciales.",
    "death note": "Light Yagami encuentra un cuaderno sobrenatural que permite matar a cualquiera cuyo nombre sea escrito en él, comenzando una cruzada para purgar el crimen.",
    "mononoke": "Un misterioso boticario viaja por el Japón feudal resolviendo casos sobrenaturales y exorcizando espíritus malignos conocidos como Mononoke.",
    "another": "Kouichi Sakakibara se traslada a la escuela de Yomiyama y descubre una extraña maldición en la clase 3-3 relacionada con una misteriosa chica con un parche.",
    "phantom: requiem for the phantom": "Un turista estadounidense es secuestrado por una organización criminal llamada Inferno y entrenado para convertirse en un asesino a sueldo implacable llamado 'Two'.",
    "rahxephon": "Ayato Kamina vive en un Tokio aislado del mundo exterior hasta que descubre la verdad detrás de las barreras y despierta al gigante RahXephon.",
    "berserk": "Guts, conocido como el Espadachín Negro, viaja por un oscuro mundo medieval buscando venganza contra su antiguo comandante Griffith.",
    "my home hero": "Tetsuo Tosu descubre que su hija es víctima de violencia doméstica por parte de un miembro de la yakuza y toma medidas drásticas para proteger a su familia."
}

CACHE_SINOPSIS = {}

def normalizar_nombre(nombre):
    clean = re.sub(r'\bEN VIVO\b', '', nombre, flags=re.I)
    clean = re.sub(r'\bx\s*\d+\b', '', clean, flags=re.I)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def buscar_en_tmdb_espanol(titulo):
    if not TMDB_API_KEY:
        return ""
    try:
        titulo_clean = re.sub(r'\b(BLOQUE|RUN A|RUN B|SEASON \d+|EPISODIO \d+)\b', '', titulo, flags=re.I).strip()
        query = urllib.parse.quote(titulo_clean)
        
        url_tv = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&language=es-MX"
        res = requests.get(url_tv, timeout=4)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results and results[0].get("overview"):
                return results[0]["overview"].strip()

        url_movie = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=es-MX"
        res_movie = requests.get(url_movie, timeout=4)
        if res_movie.status_code == 200:
            results = res_movie.json().get("results", [])
            if results and results[0].get("overview"):
                return results[0]["overview"].strip()
    except Exception as e:
        print(f"Error en TMDb para '{titulo}':", e)
    return ""

def obtener_sinopsis(nombre_programa):
    clean = normalizar_nombre(nombre_programa)
    if clean in CACHE_SINOPSIS:
        return CACHE_SINOPSIS[clean]

    key_norm = clean.lower()
    sinopsis = SINOPSIS_DB.get(key_norm, "")
    
    if not sinopsis:
        for k, v in SINOPSIS_DB.items():
            if k in key_norm or key_norm in k:
                sinopsis = v
                break

    if not sinopsis:
        sinopsis = buscar_en_tmdb_espanol(clean)

    CACHE_SINOPSIS[clean] = sinopsis
    return sinopsis

# ==========================================
# 4. PARSEO DEL XML CON ZONA HORARIA Y DÍA
# ==========================================

tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")

url_xml_activo = obtener_xml_activo_por_intercepcion()
print(f"Descargando programación activa desde: {url_xml_activo}")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

programas_raw = []
res = requests.get(url_xml_activo, headers=headers, timeout=10)

if res.status_code == 200:
    try:
        root = ET.fromstring(res.content)
        
        for elem in root.findall('.//programme'):
            start_attr = elem.attrib.get('start', '') # Ej: "20260901060000 -0600"
            
            title_elem = elem.find('title')
            nombre_prog = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

            if start_attr and nombre_prog:
                raw_time = start_attr.split()[0]
                
                if len(raw_time) >= 12:
                    dt_orig = datetime.strptime(raw_time[:14], "%Y%m%d%H%M%S")
                    
                    tz_sv = pytz.timezone("America/El_Salvador")
                    dt_sv = tz_sv.localize(dt_orig)
                    
                    dt_ar = dt_sv.astimezone(tz_ar)
                    
                    # Extraer el día de la semana en español
                    dia_semana_eng = dt_ar.strftime("%A").lower()
                    dia_semana_es = DIAS_SEMANA_ES.get(dia_semana_eng, dt_ar.strftime("%A"))
                    
                    hora_ar = dt_ar.strftime("%H:%M")
                    nombre_clean = normalizar_nombre(nombre_prog)
                    
                    if nombre_clean:
                        if not programas_raw or programas_raw[-1]["inicio"] != hora_ar or programas_raw[-1]["programa"] != nombre_clean:
                            programas_raw.append({
                                "dia": dia_semana_es,
                                "inicio": hora_ar,
                                "programa": nombre_clean
                            })

    except Exception as e:
        print(f"Error procesando el contenido XML: {e}")

# ==========================================
# 5. UNIFICACIÓN DE BLOQUES Y CARGA A SHEETS
# ==========================================

if not programas_raw:
    print("⚠️ No se pudieron procesar programas del XML interceptado.")
else:
    bloques_individuales = []
    for i in range(len(programas_raw)):
        p_curr = programas_raw[i]
        fin = programas_raw[i+1]["inicio"] if i < len(programas_raw) - 1 else programas_raw[0]["inicio"]
        bloques_individuales.append({
            "dia": p_curr["dia"],
            "inicio": p_curr["inicio"],
            "fin": fin,
            "programa": p_curr["programa"]
        })

    # Unificar episodios o bloques consecutivos de la misma serie
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
    if bloque_actual:
        bloques_unificados.append(bloque_actual)

    # Confeccionar filas para Google Sheets
    filas_epg = [["Dia", "Inicio", "Fin", "Programa", "Descripcion"]]
    for b in bloques_unificados:
        sinopsis = obtener_sinopsis(b["programa"])
        filas_epg.append([b["dia"], b["inicio"], b["fin"], b["programa"], sinopsis])

    sheet.clear()
    sheet.update(range_name='A1', values=filas_epg)
    print(f" ¡Éxito! Se actualizaron {len(filas_epg) - 1} filas en Google Sheets con la columna 'Dia'.")
