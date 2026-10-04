import os
import json
import re
import time
import urllib.parse
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
    "horimiya": "Aunque admirada en la escuela por su amabilidad y destreza académica, Hori oculta su faceta de ama de casa. Miyamura, un chico tranquilo con piercings y tatuajes secretos, comparte un vínculo inesperado al descubrir sus verdaderos ser.",
    "na nare hana nare": "Seis chicas de preparatoria con diversos pasatiempos, habilidades y personalidades se unen para formar un grupo de animación y apoyo mutuo.",
    "hibike! euphonium": "Kumiko Oumae decide unirse al club de banda de música de la preparatoria Kitauji, enfrentando exigencias y desafíos para clasificar en el torneo nacional.",
    "blend s": "Maika Sakuranomiya es una chica que busca trabajo pero suele dar una impresión aterradora involuntariamente. Es contratada en una cafetería temática donde interpreta un papel sádico.",
    "spy x family": "El espía Loid Forger debe formar una familia falsa para cumplir una misión crucial, sin saber que su esposa es una asesina a sueldo y su hija adoptiva tiene poderes telepáticos.",
    "make heroine ga oosugiru!": "Kazuhiko Nukumizu observa cómo las chicas populares de su clase terminan siendo rechazadas sentimentalmente por sus amigos de la infancia, involucrándose en sus vidas de formas cómicas.",
    "hidamari sketch": "Yuno es una joven que ingresa al bachillerato de artes de Yamabuki y vive en el complejo de apartamentos Hidamari, compartiendo experiencias con sus amigas creativas.",
    "kemono friends": "Japari Park es un enorme zoológico donde los animales se transforman en chicas antropomórficas tras el contacto con una misteriosa sustancia llamada Sandstar.",
    "bloque chronicstereo": "Bloque especial de programación musical y temática de animación continua.",
    "toradora!": "Ryuuji Takasu y Taiga Aisaka deciden ayudarse mutuamente para conquistar a sus respectivos mejores amigos, creando una relación tan tensa como entrañable.",
    "new game!": "Aoba Suzukaze se gradúa de la preparatoria y entra a trabajar como diseñadora de personajes en Eagle Jump, la empresa desarrolladora de sus videojuegos favoritos.",
    "gamers!": "Keita Amano es un estudiante amante de los videojuegos que se ve envuelto en un enredo de relaciones malinterpretadas junto a otros compañeros de preparatoria.",
    "school rumble": "Tenma Tsukamoto intenta declarar su amor a Karasuma, mientras que el delincuente Kenji Harima intenta infructuosamente declarar sus sentimientos por Tenma.",
    "bang dream": "Kasumi Toyama busca un sonido brillante y conmovedor que escuchó de niña, lo que la lleva a fundar la banda escolar Poppin'Party.",
    "tonari no kaibutsu-kun": "Shizuku Mizutani solo se preocupa por sus calificaciones, pero su perspectiva cambia cuando conoce a Haru Yoshida, un chico problemático e impredecible.",
    "engage kiss": "Shu opera una pequeña empresa privada para exterminar demonios en Veyron City con la ayuda de Kisara, un demonio femenino con quien mantiene un contrato especial.",
    "kaichou wa maid-sama!": "Misaki Ayuzawa es la estricta presidenta del consejo estudiantil que oculta un trabajo secreto a tiempo parcial en un Maid Café, descubierto por el chico más popular del colegio, Takumi Usui.",
    "suzumiya haruhi no yūutsu": "Kyon conoce a la excéntrica Haruhi Suzumiya, quien crea la Brigada SOS para investigar fenómenos sobrenaturales, sin saber que ella posee el poder de alterar el universo.",
    "gekkan shoujo nozaki-kun": "Chiyo Sakura intenta confesarse al chico que le gusta, Umetaro Nozaki, solo para descubrir que es un famoso creador de manga shoujo y terminar siendo su asistente.",
    "assassination classroom": "Los estudiantes de la clase 3-E tienen la tarea de asesinar a su nuevo profesor, un ser alienígena con tentáculos capaz de destruir la Tierra si no es derrotado.",
    "slam dunk": "Hanamichi Sakuragi ingresa al equipo de baloncesto de la preparatoria Shohoku para impresionar a una chica, descubriendo gradualmente una verdadera pasión por el deporte.",
    "absolute duo": "Toru Kokonoe se inscribe en la Academia Koryo, donde los estudiantes luchan usando sus almas manifestadas como armas llamadas Blaze.",
    "honzuki no gekokujō": "Una joven bibliotecaria muere y renace en un mundo medieval con poco acceso a libros, por lo que decide fabricarlos ella misma.",
    "jojo no kimyou na bouken": "La saga épica de la familia Joestar en su lucha contra fuerzas sobrenaturales a lo largo de diversas generaciones.",
    "hikikomari kyuuketsuki no monmon": "Terakomari Gandesblood es una vampira recluida que es nombrada comandante del ejército a pesar de no poder beber sangre ni usar magia.",
    "suki na ko ga megane wo wasureta": "Mie-san suele olvidar sus anteojos, por lo que su compañero de clase Komura siempre intenta ayudarla mientras lidia con sus sentimientos por ella.",
    "flcl": "Naota Nandaba ve su vida alterada cuando Haruko Haruhara aparece en un motoneta, lo golpea con un bajo eléctrico y hace que le salgan robots de la cabeza.",
    "my dress-up darling": "Wakana Gojo fabrica muñecas Hina y conoce a Marin Kitagawa, una chica alegre que le pide ayuda para confeccionar sus trajes de cosplay.",
    "seitokai yakuindomo": "Takatoshi Tsuda se une al consejo estudiantil de una antigua escuela de chicas que recién se volvió mixta, rodeado de compañeras con un humor particular.",
    "ao haru ride": "Futaba Yoshioka se reencuentra en la preparatoria con su primer amor Kou Tanaka, descubriendo que ambos han cambiado sustancialmente desde la secundaria.",
    "masamune-kun no revenge": "Masamune Makabe entrena físicamente durante años para vengarse de Aki Adagaki, la chica rica que lo rechazó e insultó cuando era niño.",
    "sakura-sou no pet na kanojo": "Sorata Kanda vive en el dormitorio Sakurasou para estudiantes problemáticos y debe cuidar de Mashiro Shiina, una brillante pintora sin habilidades cotidianas.",
    "3d kanojo: real girl": "Hikaru Tsutsui es un otaku que prefiere las chicas 2D hasta que termina saliendo con Iroha Igarashi, una chica real e impactante.",
    "toaru kagaku no railgun s": "Mikoto Misaka investiga el oscuro experimento del proyecto 'Sisters' que involucra la creación de miles de sus clones en Ciudad Academia.",
    "ore no kanojo to osananajimi ga shuraba sugiru": "Eita Kidou finge ser el novio de Masuzu Natsukawa para evitar llamados de atención, generando un enredo con su amiga de la infancia.",
    "renai boukun": "Guri posee una libreta mágica que obliga a cualquier pareja a besarse para convertirse en novios, involucrando al estudiante Seiji Aino.",
    "urasekai picnic": "Sorawo y Toriko exploran un mundo paralelo lleno de monstruos del folclore de internet a través de puertas misteriosas.",
    "niehime to kemono no ou": "Saliphie es enviada como sacrificio para el Rey de las Bestias, pero descubre la bondad del rey y decide convertirse en su reina.",
    "ao no orchestra": "Hajime Aono es un prodigio del violín que dejó de tocar tras un problema familiar, recuperando su pasión al unirse al club de orquesta de la escuela.",
    "keroro gunsou": "El sargento Keroro es un alienígena con forma de rana enviada a conquistar la Tierra, pero termina viviendo con la familia Hinata realizando tareas domésticas.",
    "sasameki koto": "Sumika Murasame está enamorada en secreto de su mejor amiga Ushio Kazama, a quien solo le gustan las chicas 'lindas y frágiles'.",
    "yahari ore no seishun love comedy wa machigatteiru. zoku": "Hachiman Hikigaya continúa navegando las complejas dinámicas del Club de Servicio mientras intenta mantener sus ideales desilusionados.",
    "youkoso jitsuryoku shijou shugi no kyoushitsu e": "Kiyotaka Ayanokouji ingresa a una escuela de élite donde los estudiantes compiten mediante un sistema de puntos que define su estatus social.",
    "sewayaki kitsune no senko-san": "Senko-san, una zorro espiritual de 800 años, llega a la vida del estresado oficinista Kuroto Nakano para cuidar de él y aliviar su agotamiento.",
    "tensei shitara ken deshita": "Un joven renace en otro mundo transformado en una espada mágica consciente y se convierte en la herramienta protectora de Fran, una chica gato."
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
# 4. PARSEO ROBUSTO DE XML MALFORMADO
# ==========================================

tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")
ahora_ar = datetime.now(tz_ar)

url_xml_activo = obtener_xml_activo_por_intercepcion()
print(f"Descargando programación activa desde: {url_xml_activo}")

# Mapeo del día real actual en Argentina
dia_hoy_eng = ahora_ar.strftime("%A").lower()
dia_hoy_es = DIAS_SEMANA_ES.get(dia_hoy_eng, "Lunes")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

programas_raw = []
res = requests.get(url_xml_activo, headers=headers, timeout=10)

if res.status_code == 200:
    xml_text = res.text
    
    # Extraer bloques <programme ...> ... </title> tolerante a errores sintácticos
    patron_programa = re.compile(
        r'<programme\s+start=["\'](\d{14})\s*[-+]\d{4}["\'][^>]*>\s*<title>([^<]+)</title>',
        re.DOTALL | re.IGNORECASE
    )
    
    coincidencias = patron_programa.findall(xml_text)
    
    for raw_time, nombre_prog in coincidencias:
        if raw_time and nombre_prog:
            try:
                # Convertir HH:MM desde la estampa de tiempo
                dt_orig = datetime.strptime(raw_time, "%Y%m%d%H%M%S")
                
                # Asignar huso horario UTC-6 (El Salvador)
                tz_sv = pytz.timezone("America/El_Salvador")
                dt_sv = tz_sv.localize(dt_orig)
                
                # Convertir a hora de Argentina (UTC-3)
                dt_ar = dt_sv.astimezone(tz_ar)
                
                hora_ar = dt_ar.strftime("%H:%M")
                nombre_clean = normalizar_nombre(nombre_prog)
                
                if nombre_clean:
                    if not programas_raw or programas_raw[-1]["inicio"] != hora_ar or programas_raw[-1]["programa"] != nombre_clean:
                        programas_raw.append({
                            "dia": dia_hoy_es,
                            "inicio": hora_ar,
                            "programa": nombre_clean
                        })
            except Exception as ex:
                continue

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

    # Unificar episodios o bloques consecutivos
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
    print(f" ¡Éxito! Se actualizaron {len(filas_epg) - 1} filas en Google Sheets correctamente para el día {dia_hoy_es}.")
