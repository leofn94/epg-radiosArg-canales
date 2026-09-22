import os
import json
import time
import re
import urllib.parse
from datetime import datetime, timedelta
import pandas as pd
import requests
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

# --- CONFIGURACIÓN DE SHEETS ---
SHEET_ORIGEN_ID = "1GSqqTGAGtW32-n3XMFOaVs9bUEJSxgGfZe57yOqBS2o"  # Matriz origen
SHEET_DESTINO_ID = "1JKs0R5aFs4uWMBFDAuVtf2-hDDYd87ZkibTqFV600Rs" # Planilla principal
NOMBRE_PESTANA = "BLAST"

sheet_origen = abrir_sheet_con_reintento(SHEET_ORIGEN_ID)
sheet_destino = abrir_sheet_con_reintento(SHEET_DESTINO_ID, NOMBRE_PESTANA)

# 2. DICCIONARIO DE SINOPSIS LOCALES
SINOPSIS_DB = {
    "Duck Dodgers": "El torpe e inflado héroe galáctico Duck Dodgers navega por el espacio del siglo 24 y medio junto a su fiel Cadete, intentando defender la Tierra de los malévolos planes del marciano Marvin.",
    "Megas XLR": "Coop, un simpático chico amante de la comida chatarra, encuentra un robot gigante del futuro en un basurero. Tras modificarlo con controles de videojuegos, defenderá a la Tierra de letales amenazas alienígenas.",
    "Hi Hi Puffy AmiYumi": "Las superestrellas del pop japonés Ami y Yumi viajan por todo el mundo a bordo de su autobús, viviendo cómicas aventuras junto a su avaro representante Kaz.",
    "The Grim Adventures of Billy & Mandy": "Billy, un niño extremadamente despistado, y Mandy, una niña cínica y dominante, le ganan una apuesta a la Muerte (Puro Hueso), obligándolo a ser su mejor amigo para siempre entre situaciones absurdas y oscuras.",
    "Dexter's Laboratory": "El pequeño niño genio Dexter realiza increíbles experimentos en su laboratorio secreto oculto tras la biblioteca de su cuarto, batallando constantemente contra las travesuras de su hermana Dee Dee.",
    "Cow and Chicken": "Vaca y Pollito son dos hermanos biológicos muy peculiares que lidian con la vida escolar cotidiana mientras evitan los retorcidos planes del Trasero Rojo.",
    "The Marvelous Misadventures of Flapjack": "El ingenuo niño Flapjack y el veterano Capitán Nudillos exploran los peligrosos mares desde la Ciudad Marea Alta, buscando obsesivamente la mítica Isla Caramelizada.",
    "Johnny Bravo": "Con su copete perfecto, gafas de sol y desbordante confianza, Johnny Bravo busca incansablemente conquistar al amor de su vida, metiéndose continuamente en aprietos por su vanidad e ingenio torpe.",
    "Foster's Home for Imaginary Friends": "Cuando Mac debe despedirse de su amigo imaginario Bloo, lo lleva al hogar de adopción de la Sra. Foster, un lugar fantástico habitado por cientos de coloridas e insólitas criaturas.",
    "Courage the Cowardly Dog": "En medio del desolado poblado de Ningún Lugar, el miedoso perro Coraje debe reunir valor para proteger a sus amables dueños, Muriel y el cascarrabias Justo, de espeluznantes amenazas sobrenaturales.",
    "Robotboy": "Un androide altamente avanzado capaz de transformarse en una destructiva máquina de combate aprende a vivir como un niño normal bajo la custodia del joven Tommy Turnbull y sus amigos.",
    "Dragon Ball Z": "Goku y los Guerreros Z protegen a la Tierra y al universo de temibles amenazas como saiyajins, tiranos espaciales y androides en batallas de poder verdaderamente épicas.",
    "Codename: Kids Next Door": "Cinco intrépidos niños de diez años operan en una casa del árbol de alta tecnología como el Sector V, luchando contra la tiranía de los adultos para defender los derechos infantiles.",
    "What's New Scooby-Doo?": "Scooby-Doo y la pandilla de Misterio a la Orden regresan con tecnología moderna para resolver enigmas tenebrosos alrededor del mundo, desenmascarando a falsos monstruos.",
    "Ed, Edd n' Eddy": "Tres niños llamados Ed con personalidades completamente opuestas idean disparatados e ingeniados planes en el vecindario para conseguir dinero y comprar enormes caramelos.",
    "Totally Spies!": "Tres adolescentes de Beverly Hills —Sam, Clover y Alex— combinan sus vidas escolares cotidianas con misiones encubiertas como agentes secretas de la organización WOOHP.",
    "¡Mucha Lucha!": "Rikochet, Buena Niña y Pulga asisten a una prestigiosa academia de lucha libre donde aprenden a dominar el Honor, la Familia, la Tradición y sus movimientos especiales.",
    "The Life and Times of Juniper Lee": "Juniper Lee mantiene el equilibrio entre el mundo humano y el mágico en la ciudad de Orchid Bay, protegiendo a los civiles de monstruos sin descuidar sus deberes escolares.",
    "Ben 10": "El joven Ben Tennyson descubre el Omnitrix, un misterioso reloj alienígena que le permite transformarse en diez poderosos extraterrestres para combatir el mal.",
    "Naruto": "Naruto Uzumaki, un joven ninja marginado que lleva en su interior al Zorro de Nueve Colas, entrena sin descanso para convertirse en Hokage y ganar el respeto de su aldea.",
    "Teen Titans": "Robin, Cyborg, Raven, Starfire y Chico Bestia unen sus habilidades extraordinarias para proteger Jump City como un dinámico equipo de jóvenes superhéroes.",
    "Ben 10: Alien Force": "Cinco años después de quitarse el Omnitrix, Ben Tennyson, de 15 años, debe colocárselo de nuevo para reclutar a un equipo y salvar a la Tierra de la invasión Highbreed.",
    "Generator Rex": "Rex Salazar es un joven capaz de hacer crecer impresionantes máquinas de su cuerpo gracias a nanites. Trabaja para Providencia conteniendo a peligrosas criaturas mutantes.",
    "Justice League Unlimited": "Superman, Batman, Mujer Maravilla y docenas de superhéroes expanden su equipo en la Liga de la Justicia para defender al universo entero de amenazas cósmicas.",
    "Tom and Jerry": "El gato Tom y el astuto ratón Jerry se enfrascan en las persecuciones más divertidas y clásicas de la televisión, llenas de slapstick y comedia atemporal.",
    "Looney Tunes": "Bugs Bunny, el Pato Lucas, Porky y el icónico elenco de personajes de Warner Bros. protagonizan disparatados cortometrajes llenos de ingenio y humor inolvidable.",
    "Pokémon": "Ash Ketchum y su Pikachu recorren diversas regiones capturando criaturas Pokémon, ganando medallas de gimnasio y buscando cumplir el sueño de ser un Maestro Pokémon.",
    "The Powerpuff Girls": "Nacidas del azúcar, las especias, las cosas bonitas y la Sustancia X, las hermanas Bombón, Burbuja y Bellota protegen a Saltadilla de villanos como Mojo Jojo.",
    "Code Lyoko": "Un grupo de estudiantes descubre un superordenador que alberga el mundo virtual de Lyoko, luchando contra el malvado virus X.A.N.A. para proteger al mundo real.",
    "Samurai Jack": "Un noble guerrero samurái es enviado a un futuro distópico controlado por el demonio Aku, emprendiendo un viaje interminable para regresar al pasado y enmendar la historia.",
    "Xiaolin Showdown": "Cuatro jóvenes monjes entrenan para dominar las artes marciales y proteger los poderosos objetos místicos Shen Gong Wu de las fuerzas del mal.",
    "Atomic Betty": "Para sus amigos es una niña común y corriente, pero en secreto Betty Barrett es una Guardiana Galáctica que protege el cosmos de malévolos extraterrestres.",
    "One Piece": "Monkey D. Luffy y los Piratas de Sombrero de Paja navegan por la Gran Ruta buscando el tesoro legendario para convertirse en el próximo Rey de los Piratas.",
    "Saint Seiya": "Los Caballeros del Zodiaco visten sus armaduras sagradas para proteger a la reencarnación de la diosa Atenea librando intensas batallas cósmicas.",
    "Yu Yu Hakusho: Ghost Files": "Tras morir salvando a un niño, el joven rebelde Yusuke Urameshi es revivido como Detective Espiritual para investigar casos sobrenaturales en el mundo humano.",
    "Rurouni Kenshin": "Kenshin Himura, un legendario exasesino que ha jurado no volver a matar, viaja por el Japón de la era Meiji protegiendo a los inocentes con su espada de filo invertido.",
    "Aqua Teen Hunger Force": "Una caja de papas fritas, un batido de chocolate y una bola de carne picada viven como vecinos en Nueva Jersey, envueltos en las situaciones más absurdas.",
    "The Boondocks": "Huey y Riley Freeman son dos hermanos que se mudan con su abuelo a un suburbio predominantemente blanco, enfrentando temas culturales con una sátira social afilada.",
    "Robot Chicken": "Sketches veloces y parodias ácidas de la cultura pop, cómics y televisión realizadas completamente en animación stop-motion con muñecos y figuras de acción.",
    "Harvey Birdman, Attorney at Law": "El antiguo superhéroe ex-cohete opera ahora como abogado defensor representando a clásicos personajes de caricaturas en disparatados juicios legales.",
    "Sealab 2021": "La tripulación incompetente de una investigación submarina enfrenta absurdas crisis cotidianas bajo una disparatada convivencia sin sentido.",
    "Space Ghost Coast to Coast": "El héroe intergaláctico Fantasma del Espacio conduce su propio programa de entrevistas nocturno recibiendo a celebridades humanas en un ambiente surrealista.",
    "Clone High": "Clones genéticos de figuras históricas como Abraham Lincoln, Cleopatra y Gandhi asisten juntos a la escuela secundaria mientras atraviesan los dramas típicos de la adolescencia."
}

# Cache en memoria para evitar consultas duplicadas a Wikipedia dentro de la misma ejecución
CACHE_WIKI = {}

def buscar_en_wikipedia(titulo):
    """Consulta la API de Wikipedia en español para obtener una sinopsis real."""
    if titulo in CACHE_WIKI:
        return CACHE_WIKI[titulo]
        
    try:
        titulo_clean = re.sub(r'\b(EN VIVO|ESPECIAL|BLOQUE)\b', '', titulo, flags=re.I).strip()
        query = urllib.parse.quote(titulo_clean)
        url_wiki = f"https://es.wikipedia.org/api/rest_v1/page/summary/{query}"
        
        headers = {"User-Agent": "EPGScraperScript/1.0 (https://github.com)"}
        res = requests.get(url_wiki, headers=headers, timeout=4)
        
        if res.status_code == 200:
            data = res.json()
            if "extract" in data and len(data["extract"]) > 30:
                extracto = data["extract"]
                # Cortar hasta el primer o segundo punto para mantener brevedad estilo EPG
                puntos = [m.start() for m in re.finditer(r'\.', extracto)]
                if len(puntos) >= 2 and puntos[1] < 260:
                    extracto = extracto[:puntos[1] + 1]
                elif len(puntos) >= 1:
                    extracto = extracto[:puntos[0] + 1]
                    
                CACHE_WIKI[titulo] = extracto
                return extracto
    except Exception as e:
        print(f"Error consultando Wikipedia para '{titulo}':", e)
        
    CACHE_WIKI[titulo] = None
    return None

def obtener_o_generar_sinopsis(nombre_programa):
    """1. Base de Datos Local -> 2. Wikipedia Español -> 3. Generación por Palabras Clave"""
    clean = re.sub(r'\bEN VIVO\b', '', nombre_programa, flags=re.I).strip()
    
    # Nivel 1: Diccionario Local
    if clean in SINOPSIS_DB:
        return SINOPSIS_DB[clean]
        
    for clave, sinopsis in SINOPSIS_DB.items():
        if clave.lower() in clean.lower() or clean.lower() in clave.lower():
            return sinopsis

    # Nivel 2: Wikipedia en Español
    sinopsis_wiki = buscar_en_wikipedia(clean)
    if sinopsis_wiki:
        return sinopsis_wiki

    # Nivel 3: Fallback Dinámico Inteligente
    if re.search(r'Horror|Terror|Miedo|Dark|Misterio', clean, re.I):
        return f"Prepárate para momentos de tensión y suspenso con {clean}, una propuesta repleta de historias oscuras y escalofriantes."
    elif re.search(r'Dragon Ball|Naruto|Piece|Seiya|Kenshin|Anime', clean, re.I):
        return f"Sumérgete en la acción de {clean}, con batallas memorables, poderes sorprendentes y grandes desafíos junto a sus emblemáticos protagonistas."
    
    return f"Acompaña a los protagonistas de {clean} en esta emocionante entrega repleta de diversión, aventuras inolvidables y gran entretenimiento."

# 3. Descargar datos de la matriz
datos_matriz = sheet_origen.get_all_values()

if not datos_matriz:
    raise ValueError("No se encontraron datos en la hoja de origen.")

headers = datos_matriz[0]
df = pd.DataFrame(datos_matriz[1:], columns=headers)

DIAS_MAPA = {
    "Monday": "Lunes",
    "Tuesday": "Martes",
    "Wednesday": "Miércoles",
    "Thursday": "Jueves",
    "Friday": "Viernes",
    "Saturday": "Sábado",
    "Sunday": "Domingo"
}

DIAS_ORDEN = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

programas_procesados = []

# 4. Procesar matriz
col_hora = headers[0]

for col_dia in headers[1:]:
    dia_encontrado = None
    for k_eng, v_esp in DIAS_MAPA.items():
        if k_eng.lower() in col_dia.lower():
            dia_encontrado = v_esp
            break

    if not dia_encontrado:
        continue

    for idx, row in df.iterrows():
        hora_raw = str(row[col_hora]).strip()
        nombre_prog = str(row[col_dia]).strip()

        if not hora_raw or not nombre_prog or nombre_prog.lower() in ["nan", "none", ""]:
            continue

        try:
            if "AM" in hora_raw.upper() or "PM" in hora_raw.upper():
                dt_est = datetime.strptime(hora_raw.upper(), "%I:%M %p")
            elif len(hora_raw.split(":")) == 3:
                dt_est = datetime.strptime(hora_raw, "%H:%M:%S")
            else:
                dt_est = datetime.strptime(hora_raw, "%H:%M")
        except Exception:
            continue

        # SUMA DE 1 HORA (EST -> ART)
        dt_art = dt_est + timedelta(hours=1)
        hora_art_str = dt_art.strftime("%H:%M")

        if dt_est.hour == 23 and dt_art.hour == 0:
            idx_dia_sig = (DIAS_ORDEN.index(dia_encontrado) + 1) % 7
            dia_efectivo = DIAS_ORDEN[idx_dia_sig]
        else:
            dia_efectivo = dia_encontrado

        programas_procesados.append({
            "dia": dia_efectivo,
            "inicio": hora_art_str,
            "programa": nombre_prog
        })

# 5. Ordenar, calcular horas de fin y asignar Sinopsis
filas_epg = [
    ["Dia", "Inicio", "Fin", "Programa", "Descripcion"]
]

for dia_nombre in DIAS_ORDEN:
    progs_dia = [p for p in programas_procesados if p["dia"] == dia_nombre]
    progs_dia.sort(key=lambda x: x["inicio"])

    for i in range(len(progs_dia)):
        p_curr = progs_dia[i]
        
        if i < len(progs_dia) - 1:
            fin = progs_dia[i+1]["inicio"]
        else:
            fin = progs_dia[0]["inicio"]

        # Se obtiene o consulta la sinopsis usando el nuevo flujo
        sinopsis = obtener_o_generar_sinopsis(p_curr["programa"])

        filas_epg.append([p_curr["dia"], p_curr["inicio"], fin, p_curr["programa"], sinopsis])

# 6. Volcar en la pestaña 'BLAST'
sheet_destino.clear()
sheet_destino.update(range_name='A1', values=filas_epg)
print(f"¡Éxito! Se procesó la matriz y se cargaron {len(filas_epg)-1} registros en BLAST con sus descripciones.")
