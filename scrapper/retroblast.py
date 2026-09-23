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

# API Key de TMDb desde GitHub Secrets
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")

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

# --- BASE DE DATOS LOCAL CON SINOPSIS ENRIQUECIDAS ---
DATABASE_SINOPSIS = {
    "space ghost c2c": "Space Ghost, un superhero de los 60, conduce su propio talk show intergaláctico entrevistando a celebridades del mundo real junto a sus antiguos enemigos capturados.",
    "space ghost coast to coast": "Space Ghost, un superhéroe de los 60, conduce su propio talk show intergaláctico entrevistando a celebridades del mundo real junto a sus antiguos enemigos capturados.",
    "futurama": "Philip J. Fry, un repartidor de pizza congelado criogénicamente en 1999, despierta mil años después en un extravagante futuro repleto de aliens y tecnología disparatada.",
    "the boondocks": "Huey y Riley Freeman son dos hermanos afroamericanos que se mudan a un tranquilo suburbio blanco con su excéntrico abuelo, enfrentando choques culturales y sátira social.",
    "harvey birdman": "El antiguo superhéroe Harvey Birdman ejerce como abogado defendiendo a clásicos personajes de caricatura en absurdos casos judiciales y conflictos legales.",
    "sealab 2021": "Las desquiciadas aventuras de un grupo de investigadores que habitan una estación submarina experimental en el año 2021, donde el caos y el absurdo son la norma.",
    "metalocalypse": "Dethklok es la banda de heavy metal más famosa e influyente del planeta, desatando destrucción, caos y locura sin importar a dónde vayan.",
    "metalocypalpse": "Dethklok es la banda de heavy metal más famosa e influyente del planeta, desatando destrucción, caos y locura sin importar a dónde vayan.",
    "athf": "Un vaso de batido, una caja de papas fritas y una albóndiga de carne vivientes resuelven insólitos misterios mientras lidian con su molesto vecino Carl.",
    "aqua teen hunger force": "Un vaso de batido, una caja de papas fritas y una albóndiga de carne vivientes resuelven insólitos misterios mientras lidian con su molesto vecino Carl.",
    "robot chicken": "Sátira animada en stop-motion que parodia la cultura pop, juguetes, películas, cómics y programas de televisión con humor negro y ritmo desenfrenado.",
    "on cinema": "Tim Heidecker y Gregg Turkington analizan estrenos cinematográficos y discuten sobre el mundo del cine en un caótico programa de reseñas llenas de drama.",
    "check it out": "El Dr. Steve Brule presenta un desastroso programa de noticias de acceso público donde explora temas cotidianos de la forma más incómoda y torpe posible.",
    "eric andre": "Eric André conduce un talk show nocturno surrealista cargado de bromas pesadas, celebridades desconcertadas, destrucción del set y caos impredecible.",
    "home movies": "Brendon Small, un niño de ocho años, pasa su tiempo libre dirigiendo y protagonizando películas caseras con la ayuda de sus dos mejores amigos.",
    "king of the hill": "La vida cotidiana de Hank Hill, su familia y sus peculiares amigos en la ficticia ciudad de Arlen, Texas, con un humor sutil sobre el estilo de vida americano.",
    "animaniacs": "Los hermanos Warner, Yakko, Wakko y Dot, escapan del tanque de agua de los estudios para desatar travesuras, números musicales y pura locura animación.",
    "power rangers": "Un grupo de jóvenes es elegido para convertirse en guerreros capaces de pilotar robots gigantes y defender a la Tierra de amenazas alienígenas.",
    "batman tas": "El caballero de la noche patrulla las oscuras calles de Ciudad Gótica combatiendo a icónicos villanos en una aclamada obra maestra de la animación.",
    "totally spies": "Tres adolescentes de Beverly Hills equilibran su vida escolar con su trabajo como agentes secretas para una organización mundial de espionaje.",
    "code lyoko": "Un grupo de estudiantes descubre un superordenador que alberga un mundo virtual llamado Lyoko y luchan para evitar que un malvado virus destruya la realidad.",
    "tmnt (2003)": "Cuatro tortugas mutantes entrenadas en el arte del ninjutsu emergen de las alcantarillas de Nueva York para proteger a la ciudad del malvado Shredder.",
    "teen titans": "Cinco jóvenes superhéroes unen sus fuerzas para proteger Jump City de poderosos villanos mientras lidian con los altibajos de la adolescencia.",
    "pokemon advanced": "Ash Ketchum continúa su viaje hacia la región de Hoenn para convertirse en Maestro Pokémon, acompañado de nuevos amigos y desafiando nuevos gimnasios.",
    "pokémon advanced": "Ash Ketchum continúa su viaje hacia la región de Hoenn para convertirse en Maestro Pokémon, acompañado de nuevos amigos y desafiando nuevos gimnasios.",
    "yu-gi-oh! gx": "Jaden Yuki ingresa a la prestigiosa Academia de Duelos para perfeccionar sus habilidades como duelista de cartas mientras descubre oscuros secretos.",
    "the cartoon cartoon show": "Bloque clásico de cortometrajes animados originales de Cartoon Network que sirvió de cuna para grandes series de la historia de la animación.",
    "ben 10": "Ben Tennyson descubre el Omnitrix, un reloj alienígena que le permite transformarse en diez alienígenas diferentes con habilidades sobrehumanas.",
    "xiaolin showdown": "Cuatro jóvenes monjes entrenan duro en artes marciales para recolectar místicos artefactos conocidos como Shen Gong Wu antes de que caigan en manos del mal.",
    "knd": "Cinco niños superoperativos forman un equipo altamente entrenado que lucha desde su casa del árbol contra la tiranía de los adultos y los deberes.",
    "billy and mandy": "Dos niños ganan la custodia de la Muerte en un juego de limbo y la convierten en su mejor amiga eterna, viviendo aventuras oscuras y cómicas.",
    "ed edd n eddy": "Tres muchachos llamados Ed idean constantes y descabellados planes para estafar a los niños del vecindario y comprar sus caramelos gigantes favoritos.",
    "juniper lee": "Juniper Lee es una niña de 11 años que equilibra la escuela con su deber secreto como la protectora del equilibrio entre el mundo humano y el mágico.",
    "fosters": "Un hogar especial acoge a amigos imaginarios abandonados por sus creadores hasta que puedan ser adoptados por nuevos niños que los necesiten.",
    "samurai jack": "Un noble guerrero samurai es enviado a un futuro distópico controlado por el demonio Aku y busca incansablemente la forma de regresar al pasado.",
    "camp lazlo": "Un mono alegre y curioso llamado Lazlo provoca divertidos estragos junto a sus amigos en el campamento de verano de los Scouts.",
    "ppg": "Tres niñas con superpoderes creadas accidentalmente en un laboratorio defienden a la ciudad de Saltadilla de monstruos y mentes criminales.",
    "star wars the clone wars": "Los Caballeros Jedi luchan para mantener el orden y la paz en la galaxia contra los separatistas durante la devastadora Guerra de los Clones.",
    "hi hi puffy ami yumi": "Las aventuras animadas de las dos estrellas reales del pop japonés Puffy AmiYumi mientras viajan por el mundo en su autobús de gira.",
    "hihipuffyamiyumi": "Las aventuras animadas de las dos estrellas reales del pop japonés Puffy AmiYumi mientras viajan por el mundo en su autobús de gira.",
    "yu-gi-oh! dm": "Yugi Muto resuelve el Milenario Rompecabezas del Faraón y libera un espíritu antiguo, compitiendo en el juego de cartas de duelos de monstruos.",
    "sailor moon": "Usagi Tsukino descubre que es la reencarnación de una guerrera cósmica destinada a proteger la Tierra y buscar el Sagrado Cristal de Plata.",
    "yuyu": "Yusuke Urameshi muere al salvar a un niño y recibe una segunda oportunidad de vivir convirtiéndose en un detective del mundo espiritual.",
    "dragon ball": "Goku inicia una legendaria búsqueda a través del mundo en busca de las siete Esferas del Dragón junto a sus valientes amigos.",
    "bobobobobobobo": "En un futuro absurdo donde el Imperio Calvo busca despojar de su cabello a la gente, BoBoBo combate al ejército enemigo con las técnicas del pelo de la nariz.",
    "outlaw star": "Gene Starwind y su joven tripulación navegan por el espacio en una nave avanzada en busca de un tesoro galáctico de poder incalculable.",
    "dbz (run a)": "Goku y los Guerreros Z protegen la Tierra de despiadados saiyajins, tiranos intergalácticos y androides en batallas de poder colosal.",
    "dbz (run b)": "Goku y los Guerreros Z protegen la Tierra de despiadados saiyajins, tiranos intergalácticos y androides en batallas de poder colosal.",
    "one piece": "Luffy y su tripulación de Piratas de Sombrero de Paja navegan a través de peligrosos mares para encontrar el legendario tesoro One Piece.",
    "one piece (fun b)": "Luffy y su tripulación de Piratas de Sombrero de Paja navegan a través de peligrosos mares para encontrar el legendario tesoro One Piece.",
    "one piece (season 1)": "Luffy inicia su viaje en el East Blue reclutando a los primeros miembros de su tripulación para aventurarse al Grand Line.",
    "naruto": "Naruto Uzumaki, un joven ninja marginado que alberga en su interior al Zorro de Nueve Colas, sueña con convertirse en el líder de su aldea.",
    "naruto (run b)": "Naruto Uzumaki, un joven ninja marginado que alberga en su interior al Zorro de Nueve Colas, sueña con convertirse en el líder de su aldea.",
    "naruto (season 1)": "Naruto forma parte del Equipo 7 junto a Sasuke y Sakura, emprendiendo sus primeras misiones oficiales como ninja.",
    "naruto/shippuden": "Tras años de intenso entrenamiento, Naruto regresa a su aldea para hacer frente a la temible organización Akatsuki y salvar a su amigo.",
    "naruto'shippuden": "Tras años de intenso entrenamiento, Naruto regresa a su aldea para hacer frente a la temible organización Akatsuki y salvar a su amigo.",
    "naruto/ shippuden": "Tras años de intenso entrenamiento, Naruto regresa a su aldea para hacer frente a la temible organización Akatsuki y salvar a su amigo.",
    "family guy": "Las disparatadas vivencias de la familia Griffin en Quahog, encabezada por el descabellado Peter y su perro parlante Brian.",
    "bleach": "Ichigo Kurosaki obtiene accidentalmente los poderes de un Segador de Almas y asume el deber de proteger a los vivos y guiar a los espíritus.",
    "fma brotherhood": "Los hermanos Elric viajan por el mundo buscando la Piedra Filosofal para restaurar sus cuerpos tras un fallido ritual alquímico.",
    "death note": "Un estudiante de secundaria encuentra un cuaderno sobrenatural con la capacidad de matar a cualquiera cuyo nombre sea escrito en sus páginas.",
    "jojo's bizarre adventure": "Las épicas batallas intergeneracionales de la linaje Joestar contra fuerzas del mal utilizando habilidades místicas y Stands.",
    "inuyasha": "Kagome es transportada al Japón feudal donde se une al medio demonio Inuyasha para recolectar los fragmentos de la valiosa Perla de Shikon.",
    "lupin the third part ii": "El carismático ladrón internacional Arsène Lupin III planea atrevidos robos alrededor del mundo mientras esquiva al inspector Zenigata.",
    "case closed": "El brillante detective adolescente Shinichi Kudo es encogido al cuerpo de un niño de primaria y adopta la identidad del Detective Conan.",
    "tom and jerry": "La eterna y cómica rivalidad entre el gato Tom y el astuto ratón Jerry en desenfrenadas persecuciones llenas de humor físico.",
    "robotboy": "Un avanzado robot con forma de niño intenta vivir una vida normal mientras protege su tecnología del malvado Doctor Kamikazi.",
    "duck dodgers": "El incompetente capitán Duck Dodgers navega por la galaxia del siglo XXIV junto a su cadete espacial desatando cómicos desastres.",
    "johnny bravo": "Un musculoso pero ingenuo joven de tupé rubio intenta torpemente conquistar mujeres con resultados desastrosos.",
    "dexters lab": "Un niño prodigio realiza experimentos secretos en su gigantesco laboratorio personal mientras intenta evitar que su hermana Dee Dee los destruya.",
    "scooby-doo": "Un grupo de cuatro adolescentes y su perro parlante investigan misterios paranormales que suelen ocultar fraudes humanos.",
    "courage": "Un cobarde perro rosado debe reunir valor para proteger a sus ancianos dueños de aterradoras e insólitas amenazas en medio de la nada.",
    "gundam wing": "Cinco jóvenes pilotos de trajes gigantes de combate son enviados desde las colonias espaciales a la Tierra para luchar por la libertad.",
    "justice league": "Los superhéroes más poderosos del planeta unifican sus fuerzas para enfrentar invasiones alienígenas y supervillanos globales.",
    "zatch bell": "Un niño prodigio se alía con un pequeño demonio de otro mundo para participar en la batalla definitiva por la corona del mundo demoníaco.",
    "class of 3000": "Una superestrella de la música decide dejar su carrera para convertirse en profesor de música en una colorida escuela de artes.",
    "tim and eric": "Un show de variedad y sketches cargado de un característico humor absurdo, sátira televisiva y formatos surrealistas.",
    "shin chan": "Un irreverente y travieso niño de cinco años causa desternillantes situaciones cómicas en su familia, escuela y vecindario.",
    "boomerang": "Bloque de programación especial dedicado a clásicos atemporales y caricaturas retro que marcaron a generaciones.",
    "avatar tla": "Aang, el último Maestro del Aire y verdadero Avatar, debe dominar los cuatro elementos para traer la paz al mundo dividido por la guerra.",
    "cartoon theater*": "Espacio cinematográfico dedicado a la emisión de las películas animadas más destacadas de la historia del cine y la televisión.",
    "mucha lucha": "Un grupo de jóvenes estudiantes entrena en una academia dedicada por completo a dominar las artes de la Lucha Libre profesional.",
    "yu-gi-oh! 5d's": "En un futuro donde los duelos de cartas se juegan sobre motocicletas de alta velocidad, Yusei Fudo lucha por la justicia social.",
    "digimon adventure": "Siete niños son transportados a un mundo digital donde se alían con criaturas llamadas Digimon para salvar ambos mundos.",
    "static shock": "Virgil Hawkins adquiere poderes electromagnéticos tras un accidente químico y decide combatir el crimen en su ciudad.",
    "megas xlr": "Un joven fanático de los autos encuentra un robot gigante del futuro en un basurero y lo modifica con partes de coche para defender la Tierra.",
    "jackie chan adventures": "Jackie Chan y su familia recorren el globo recuperando talismanes mágicos antes de que caigan en manos de organizaciones criminales.",
    "the batman": "Un joven Bruce Wayne da sus primeros pasos como el vigilante de Ciudad Gótica mientras enfrenta la evolución de sus villanos.",
    "igpx": "En el año 2048, equipos de pilotos compiten en robots biomecánicos de alta velocidad en la liga más competitiva del planeta.",
    "ghost in the shell": "En un futuro cibernético, la mayor Motoko Kusanagi lidera una unidad policial de élite enfrentando crímenes tecnológicos y existenciales.",
    "paranoia agent": "Un misterioso agresor en patines aterroriza Tokio mientras un grupo de detectives intenta desentrañar la verdad detrás de los ataques.",
    "cowboy bebop": "Un grupo de cazadores de recompensas a bordo de la nave Bebop navega por el espacio enfrentando su oscuro pasado.",
    "late night movie*": "Espacio de cine nocturno que presenta largometrajes, clásicos de culto y producciones seleccionadas."
}

CACHE_SINOPSIS = {}

def normalizar_nombre_programa(nombre_programa):
    """
    Limpia etiquetas como 'x2', 'x 2', 'EN VIVO', etc., para poder
    encontrar el programa base tanto en la BD como al unificar bloques.
    """
    clean = re.sub(r'\bEN VIVO\b', '', nombre_programa, flags=re.I)
    # Elimina sufijos como 'x2', 'x 2', 'x 3' al final o de forma aislada
    clean = re.sub(r'\bx\s*\d+\b', '', clean, flags=re.I)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def buscar_en_tmdb_espanol(titulo):
    """Consulta la API de TMDb pidiendo explícitamente el resumen en español (es-MX)."""
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
    Obtiene la sinopsis normalizando primero el título (eliminando 'x2', etc.).
    """
    clean = normalizar_nombre_programa(nombre_programa)
    
    if clean in CACHE_SINOPSIS:
        return CACHE_SINOPSIS[clean]

    key_normalizada = clean.lower()
    
    sinopsis_encontrada = ""
    if key_normalizada in DATABASE_SINOPSIS and DATABASE_SINOPSIS[key_normalizada]:
        sinopsis_encontrada = DATABASE_SINOPSIS[key_normalizada]
    else:
        sinopsis_encontrada = buscar_en_tmdb_espanol(clean)

    CACHE_SINOPSIS[clean] = sinopsis_encontrada
    return sinopsis_encontrada

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
    "Thursday": "Viernes",
    "Friday": "Viernes", # Corrección segura si hay duplicados
    "Saturday": "Sábado",
    "Sunday": "Domingo"
}

# Corregir clave Friday
DIAS_MAPA["Friday"] = "Viernes"
DIAS_MAPA["Thursday"] = "Jueves"

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

# 5. Ordenar, calcular horas de fin, unificar bloques continuos y asignar Sinopsis
filas_epg = [
    ["Dia", "Inicio", "Fin", "Programa", "Descripcion"]
]

for dia_nombre in DIAS_ORDEN:
    progs_dia = [p for p in programas_procesados if p["dia"] == dia_nombre]
    progs_dia.sort(key=lambda x: x["inicio"])

    if not progs_dia:
        continue

    # Primero construimos la lista con sus horas de inicio y fin individuales
    bloques_individuales = []
    for i in range(len(progs_dia)):
        p_curr = progs_dia[i]
        fin = progs_dia[i+1]["inicio"] if i < len(progs_dia) - 1 else progs_dia[0]["inicio"]
        
        bloques_individuales.append({
            "dia": p_curr["dia"],
            "inicio": p_curr["inicio"],
            "fin": fin,
            "programa": p_curr["programa"],
            "programa_norm": normalizar_nombre_programa(p_curr["programa"])
        })

    # Unificación de bloques continuos consecutivos del mismo programa
    bloques_unificados = []
    bloque_actual = None

    for b in bloques_individuales:
        if bloque_actual is None:
            bloque_actual = b
        else:
            # Si el programa normalizado es igual al anterior, extendemos la hora de fin
            if b["programa_norm"].lower() == bloque_actual["programa_norm"].lower():
                bloque_actual["fin"] = b["fin"]
            else:
                bloques_unificados.append(bloque_actual)
                bloque_actual = b
    
    if bloque_actual is not None:
        bloques_unificados.append(bloque_actual)

    # Construir filas para la EPG con la sinopsis correspondiente
    for b in bloques_unificados:
        # Se guarda el nombre del programa sin la coletilla 'x2' si corresponde
        prog_limpio = b["programa_norm"]
        sinopsis = obtener_sinopsis(prog_limpio)
        filas_epg.append([b["dia"], b["inicio"], b["fin"], prog_limpio, sinopsis])

# 6. Volcar en la pestaña 'BLAST'
sheet_destino.clear()
sheet_destino.update(range_name='A1', values=filas_epg)
print(f"¡Éxito! Se cargaron {len(filas_epg)-1} registros en BLAST.")
