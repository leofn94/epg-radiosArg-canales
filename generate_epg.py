import csv
import urllib.request
import gzip
import io
from datetime import datetime, timedelta
import pytz
import html
import xml.etree.ElementTree as ET

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

# Ajuste horario manual para canales específicos (Horas a sumar o restar)
OFFSET_CONFIG = {
    "464956": -8,  # Screenpix (epg.pw)
    "464775": -8,  # Screenpix Action (epg.pw)
    "0605": +1, #love nature (visor)
    "1604": +2, #ID (visor)
    "0629": -1, #canal luz (visor)
    "0222": -1, # A24(visor)
    "0915": -4, # El trece(visor)
    "0934": -4, # Crónica(visor)
    "0917": -4, # Canal 26(visor)
    "0904": -1, # Ln+(visor)
    "0935": -1, # América TV(visor)
    "0916": -4, # Canal 9(visor)
    "0905": -4, # TN(visor)
    "0932": -4, # C5N(visor)
    "0210": -4, # CNN esp(visor)
    "0215": -4, # CNN(visor)
    "0205": -4, # Dw(visor)
    "0636": -6, #TVE(visor)
    "0643": -1, # Hispantv(visor)
    "0533": -4, # Allegro(visor)
    "0920": -4, # Encuentro(visor)
    "0707": -4, # History 2(visor)
    "1610": -4, # El gourmet(visor)
    "0704": -4, # Discovery theater(visor)
    "0703": -4, # Discovery science(visor)
    "2701": -1, # Discovery chanel(visor)
    "0705": -3, # Animal Planet (visor)
    "0850": -4, # Adult swim(visor)
    "0318": -4, # Bitme(visor)
    "0302": -4, # Etc(visor)
    "0308": -1, # Tooncast(visor)
    "0812": -4, # Comedy central(visor) 4horas 
    "0821": -1, # Golden(visor)
    "0822": -4, # Golden plus(visor)
    "0823": -1, # Golden edge(visor)
    "0824": -4, # Golden premier(visor)
    "1824": -4, # Golden premier 2 (visor)
    "0621": -4, #EuroChannel (visor)
    "1813": -4, # HBO(visor)
    "2813": -4, # HBO oeste(visor)
    "0815": -4, # HBO +(visor)
    "1814": -4, # HBO 2(visor)
    "0820": -4, # HBO Xtreme(visor)
    "0818": -4, # HBO mundo(visor)
    "1806": -1, # Sony(visor)
    "1810": -4, # Sony movies(visor)
    "1832": -5, # Warner(visor)
    "0838": -4, # Multi premier(visor)
    "0839": -4, # Multi cinema(visor)
    "0851": -4, # Film & arts(visor)
    "0622": -4, # Europa Europa(visor)
    "0855": -4, # Pánico(visor)
    "0859": -4, # Mórbido(visor)
    "0807": -4, # TCM latam(visor)
    "1625": -4, #EWTN (visor)
    "1409": -1, #TYC (Visor)
    "1436 ": -1, #FOXSPOPRTS (Visor)    
    "1411": -4, #ESPN (Visor)
    "1412": -1, #ESPN2 (Visor)
    "2413": -1, #ESPN3 (Visor)
    "1418": -1, #ESPN Premium (Visor)
    "0856": -1, #antena3int (visor)
    "0927": -1, #Deportv (Visor)    
    "0431": -4, #Dsports (Visor)
    "1841": -7, #Universal Cinema (visor)
    "0844": -1, #universal premiere (visor)
    "0936": -4, #ciudad magazine (visor)
    "0845": -1 #universal comedy (visor)
   # "aztv.ar": -2, # AZTV (sheet) 
}

# 1. CANALES DESDE GOOGLE SHEETS
CHANNELS = [
    {"id": "radio10.ar", "name": "Radio 10 AM 710", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?output=csv"},
    {"id": "rivadavia.ar", "name": "Radio Rivadavia AM 630", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=1982230184&single=true&output=csv"},
    {"id": "mitre.ar", "name": "Radio Mitre AM 590", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=753334140&single=true&output=csv"},
    {"id": "nacionalclasica.ar", "name": "Radio Nacional clasica FM 96.7", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=1242936527&single=true&output=csv"},
    {"id": "clasica.ar", "name": "Radio clasica", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=1953325678&single=true&output=csv"},
    {"id": "ciudadmagica.ar", "name": "Ciudad Magica", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=314883977&single=true&output=csv"},
    {"id": "retromagico.ar", "name": "Retro Magico", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=1067661478&single=true&output=csv"},
    {"id": "magickids.ar", "name": "Magic Kids", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=1797674806&single=true&output=csv"},
   # {"id": "locomotion1.ar", "name": "Locomotion 1", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=309534154&single=true&output=csv"},
   # {"id": "aztv.ar", "name": "AZTV", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=955136670&single=true&output=csv"},
    {"id": "mitv.ar", "name": "MiTV 1", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=1227571137&single=true&output=csv"},
    {"id": "animestation.ar", "name": "Animestation", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=446220036&single=true&output=csv"},
    {"id": "retroblast", "name": "retroblast", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=441139638&single=true&output=csv"},
    {"id": "cncity", "name": "cncity", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=1501419241&single=true&output=csv"},
    {"id": "telered.ar", "name": "Telered", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=763195247&single=true&output=csv"},
    {"id": "telesistema.ar", "name": "telesistema", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=503971923&single=true&output=csv"},
    {"id": "doble.c.tv", "name": "doble c", "url": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ1YPyXdfmd2n7W6tAEnS_7aPb1r9j8fmdF_XP-jxi5cYdcZwkx_4t5OEIqYpGzr98wcF4nHUzhbval/pub?gid=937272524&single=true&output=csv"}
]

# 2. FUENTES XML EXTERNAS
EXTERNAL_SOURCES = [
    {
        "url": "https://raw.githubusercontent.com/Puticastillo/EPGCL/refs/heads/main/vilma/guia-de-programacion.xml",
        "ids": ["0204", "0205", "0206", "0209", "0210", "0215", "0222", "0318", "0431", "0432", "0433", "0528", "0533", "0621", "0629", "0302", "0308", "0705",
                "0636", "0643", "0707", "0808", "0821", "0822", "0823", "0824", "0838", "0839", "0842", "0851", "0855", "0859", "0812", "1604", "0621",
                "0903", "0904", "0905", "0909", "0915", "0916", "0917", "0920", "0927", "0934", "0935", "1806", "1810", "1814", "2701", "1832", 
                "2813", "XXX8", "0818", "0820", "0815", "1813", "0622", "0850", "0807", "1409", "1610", "0704", "0703", "1841",
                "0605", "1436", "0401", "0429", "1824", "0845", "0844", "0805", "0625", "0619", "0936"]
    },
    {
        "url": "https://epg.programadorx.cl/mdiaz/gratis.xml",
        "ids": ["531", "532", "536", "537", "538", "539", "567", "568", "569", "581", "663", "664", "633"]
    },
   # {
   #     "url": "https://i.mjh.nz/PlutoTV/mx.xml",
   #     "ids": ["66a11a21a79dea0008aa90ca", "5de5758e1a30dc00094fcd6c", "63a084934734f30007457b2c", "6894fc3f66f164e402f4fd14", "6894febddbd49c964f3b66c8", "5dcde17bf6591d0009839e02", "6870072ca9d5c45c3e9466f1", 
   #             "645952687cb4b100084ed52e","6824cda00101510f9eeaa011", "6254598f5083f800076d8563", "609ae5cd48d3200007b0a98e","65df731cec9fda0008b7aa8d", "65df7272ec9fda0008b7a970", "65df73520d4561000817c29b",
   #             "65df72db18036500081a8292", "5dcde1317578340009b751d0", "65662f8a2c46f300088a84cc","6479ff1c17f5e10008ad2797", "655f62ff954b020008c91ec6", "5de802659167b10009e7deba","5ff608e60e2996000768c366", 
   #             "5f2817d3d7573a00080f9175","5dcde437229eff00091b6c30", "5e972a21ad709d00074195ba", "5dcb62e63d4d8f0009f36881","5ddc4e8bcbb9010009b4e84f", "5dcddf1ed95e740009fef7ab","66997d18a1b69e00082ee85f"]
   # },
    {
        "url": "https://i.mjh.nz/SamsungTVPlus/es.xml.gz",
        "ids": ["ES3400004SS", "ESBC1700004PX", "ESBC2700003T8", "ESBC40000248", "ESBC2700002LO"]
    },
    {
        "url": "https://i.mjh.nz/SamsungTVPlus/us.xml.gz",
        "ids": ["USBD3500008IJ","USBD35000149S", "USBD35000180U", "US2600019IC","USBD1200009JI", "US2200001IY", "US5000053YV", "USAJ3504502A", "US1900002QK", "US1800014CG", "USBD12000255B",
               "USAK3508705A", "US700012OU", "USBA3800004EL"]
    },
    {
        "url": "https://i.mjh.nz/SamsungTVPlus/gb.xml.gz",
        "ids": ["GB2300005ML", "GBBD4900001RG", "GBBD1900009UD", "GBBC2100002HP", "GB500007VM"]
    },
    {
        "url": "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/master/Plex/us.xml.gz",
        "ids": ["6a1610bebdf296985fd95603-6478acb5c83f56da796f166c", "6a1610bebdf296985fd95603-6571f43a1d2aae780d597196", "6a1610bebdf296985fd95603-5fc70600dd53a6002d8f93ca",
                "6a1610bebdf296985fd95603-646fab0e43d6d6838db81a6a", "6a1610bebdf296985fd95603-68fafc6e558214386ab7ca3a", "6a1610bebdf296985fd95603-688006e7015fe7e375a1a0ac",
                "6a1610bebdf296985fd95603-6889430a3b7708975e7c07e3", "6a1610bebdf296985fd95603-6876fa82e50e77c59c8940c2"
                "6a1610bebdf296985fd95603-64b710b44612b1f48e9ad31a", "6a1610bebdf296985fd95603-5eea605574085f0040ddc791", "6a1610bebdf296985fd95603-5f5132e362fe160040f26c15"
                "6a1610bebdf296985fd95603-5ef4e1b40d9ad000423c442a", "6a1610bebdf296985fd95603-63dea56a2a2abb171ff6dadf", "6a1610bebdf296985fd95603-62d1efa6c33948ea4ceedbcf", 
                "6a1610bebdf296985fd95603-66a2e7fe94b6a49cb5054d7b", "6a1610bebdf296985fd95603-5eea605674085f0040ddc7a6", "6a1610bebdf296985fd95603-689fb7110a486aeba3c7917c"]
    },
     {
         "url": "https://epgshare01.online/epgshare01/epg_ripper_PLEX1.xml.gz",
         "ids": ["plex.tv.Deal.Or.No.Deal.plex", "plex.tv.Family.Feud.plex"]
     },
    {
        "url": "https://i.mjh.nz/Plex/mx.xml",
        "ids": ["608049aefa2b8ae93c2c3a63-67642f277c5e3b38af72dcdb", "608049aefa2b8ae93c2c3a63-6684374320f405b792a3b6b3", "608049aefa2b8ae93c2c3a63-66843a1f20f405b792a3b6b5", 
                "608049aefa2b8ae93c2c3a63-6685abbe59703916799193a7", "608049aefa2b8ae93c2c3a63-668434f6a017b7e51aeb28d3"]
    },
    {
        "url": "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/refs/heads/master/Plex/es.xml",
        "ids": ["643054b1fc3be59477853717-66840a26cd6f1d3940941155", "643054b1fc3be59477853717-66841b30702b9db9f18177258",
               "643054b1fc3be59477853717-692235265cbe620c1f9b6bc7","643054b1fc3be59477853717-692234015028288613484a8a","643054b1fc3be59477853717-6922322350fe592fd6d5b7e6",
                "643054b1fc3be59477853717-66840253cd6f1d394094114f","643054b1fc3be59477853717-6490e17c18a55242eea95991","643054b1fc3be59477853717-668420c2cd6f1d3940941157",
               "643054b1fc3be59477853717-6922338150fe592fd6d5b7e8", "643054b1fc3be59477853717-6683fcdf702b9db9f8177252", 
               "643054b1fc3be59477853717-64d79408e5f67b0fab47ff24", "643054b1fc3be59477853717-666e23e4d91d13cb4c8cbb79", "643054b1fc3be59477853717-65e9d0ad8fe4ef7053c3c872",
               "643054b1fc3be59477853717-6662984e346b86608532dbdf", "643054b1fc3be59477853717-66ea174c9502c5778b828d47", "643054b1fc3be59477853717-69a1fe1b0f8d297b3f6ac0f0",
               "643054b1fc3be59477853717-62fbf36c1567211fdb82e920", "643054b1fc3be59477853717-5f170d61b898490041b49369"]
    }, 
    {
        "url": "https://raw.githubusercontent.com/luisms123/tdt/refs/heads/master/guiacanales.xml",
        "ids": ["Magic Kids Tv", "Ani Retro", "El Chavo", "Cine Sony"]
    },
    {
        "url": "https://epg.pw/xmltv/epg_US.xml.gz",
        "ids": ["464956", "464775"]
    },
    {
        "url": "https://epgshare01.online/epgshare01/epg_ripper_ES1.xml.gz",
        "ids": ["TCM.es", "M+.Clásicos.es", "Canal.24.h.es"]
    },
    {
        "url": "https://epgshare01.online/epgshare01/epg_ripper_RAKUTEN1.xml.gz",
        "ids": ["ES:.That`s.80s.be", "ES:.That`s.90s00s.be", "ES:.That`s.ROCK.be", "ES:.Sci-Fi.-.Rakuten.TV.be", "ES:.Películas.de.Acción.-.Rakuten.TV.be", 
                "ES:.Thrillers.-.Rakuten.TV.be", "ES:.Stingray:.Remember.the.80’s.be", "ES:.Pelis.Top.-.Rakuten.TV.be", "ES:.AnimeVisión.be", "ES:.AnimeVisión.Classics.be"]
    }
]

TIMEZONE = "America/Argentina/Buenos_Aires"
OUTPUT_FILE = "epg.xml"



# ─── FUNCIONES DE APOYO ──────────────────────────────────────────────────────

def fetch_url(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Encoding': 'gzip'})
        with urllib.request.urlopen(req) as r:
            content = r.read()
            if content.startswith(b'\x1f\x8b'):
                with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                    return gz.read()
            return content
    except Exception as e:
        print(f"  ❌ Error de conexión con {url} → {e}")
        return None

def parse_time(t):
    if not t: raise ValueError("Hora vacía")
    t = t.strip().lower().replace("hs", "").replace(".", ":").replace("·", "").replace(" ", "")
    if len(t) >= 5: t = t[:5]
    return datetime.strptime(t, "%H:%M").time()

def xmltv_ts(dt):
    return dt.strftime("%Y%m%d%H%M%S %z")

def get_monday():
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()
    return today - timedelta(days=today.weekday())

def get_days_from_type(tipo):
    tipo = tipo.lower()
    days_map = {
        "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
        "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
    }
    if tipo == "weekdays": return [0, 1, 2, 3, 4]
    elif tipo == "weekend": return [5, 6]
    elif tipo == "madr_esp": return [1, 2, 3, 4, 5]
    elif tipo in days_map: return [days_map[tipo]]
    return []

# ─── PROCESAMIENTO EPG EXTERNA ───────────────────────────────────────────────
def process_external_sources(sources):
    data = []
    tz_arg = pytz.timezone(TIMEZONE)
    now = datetime.now(tz_arg)
    limit_time = now + timedelta(hours=55) # FILTRO 55 HORAS
    
    for source in sources:
        url = source["url"]
        target_ids = source["ids"]
        print(f"\nDescargando EPG externa de {url}...")
        raw_xml = fetch_url(url)
        if not raw_xml: continue
        
        try:
            root = ET.fromstring(raw_xml)
            
            # 1. Mapear canales ignorando por completo los namespaces del XML
            channel_names = {}
            for channel in root.iter():
                if channel.tag.endswith('channel'):
                    ch_id = channel.get('id')
                    if ch_id in target_ids:
                        disp_name = channel.find('.//{*}display-name')
                        channel_names[ch_id] = disp_name.text if disp_name is not None else f"Extra {ch_id}"

            # 2. Agrupar los programas por ID de canal de forma eficiente e inmune a namespaces
            programmes_by_ch = {ch_id: [] for ch_id in target_ids}
            
            for prog in root.iter():
                if prog.tag.endswith('programme'):
                    ch_id = prog.get('channel')
                    if ch_id in programmes_by_ch:
                        try:
                            start_str = prog.get("start").strip()
                            stop_str = prog.get("stop").strip()
                            
                            # Manejo flexible de formatos de fecha con/sin espacios
                            fmt = "%Y%m%d%H%M%S %z" if " " in start_str else "%Y%m%d%H%M%S%z"
                            
                            s_dt = datetime.strptime(start_str, fmt).astimezone(tz_arg)
                            e_dt = datetime.strptime(stop_str, fmt).astimezone(tz_arg)
                            
                            # Aplicar desfase convirtiendo a float para soportar minutos (ej: -3.5)
                            hour_offset = OFFSET_CONFIG.get(ch_id, 0)
                            if hour_offset != 0:
                                s_dt += timedelta(hours=float(hour_offset))
                                e_dt += timedelta(hours=float(hour_offset))
                            
                            # FILTRO TOLERANTE: Ahora permite programas que terminaron hace hasta 24hs
                            if e_dt > (now - timedelta(hours=24)) and s_dt < limit_time:
                                title_node = prog.find('.//{*}title')
                                desc_node = prog.find('.//{*}desc')
                                
                                title = title_node.text if title_node is not None else "Sin título"
                                desc = desc_node.text if desc_node is not None else ""
                                
                                programmes_by_ch[ch_id].append((s_dt, e_dt, title, desc, ch_id))
                        except:
                            continue

            # 3. Empaquetar los datos para el retorno conservando tus prints
            for ch_id in target_ids:
                programmes = programmes_by_ch[ch_id]
                if programmes:
                    ch_name = channel_names.get(ch_id, f"Extra {ch_id}")
                    hour_offset = OFFSET_CONFIG.get(ch_id, 0)
                    offset_msg = f" [Ajuste: {hour_offset}hs]" if hour_offset != 0 else ""
                    print(f"  ✅ Canal Externo: {ch_name} [{ch_id}] → {len(programmes)} programas{offset_msg}")
                    data.append({"id": ch_id, "name": ch_name, "programmes": programmes})
                    
        except Exception as e:
            print(f"  ❌ Error procesando XML: {e}")
            
    return data
    
# ─── CONSTRUCCIÓN EPG DESDE SHEETS ──────────────────────────────────────────

def build_epg_from_sheets(rows, channel_id):
    tz = pytz.timezone(TIMEZONE)
    monday = get_monday()
    programmes = []
    now = datetime.now(tz)
    limit_time = now + timedelta(hours=55) # FILTRO 55 HORAS

    sheet_offset = OFFSET_CONFIG.get(channel_id, 0)

    for row in rows:
        if len(row) < 4: continue
        row = [col.strip() for col in row]
        tipo, start_raw, end_raw, title = row[0], row[1], row[2], row[3]
        desc = row[4] if len(row) > 4 else ""
        days_to_apply = get_days_from_type(tipo)

        for day_offset in days_to_apply:
            target_date = monday + timedelta(days=day_offset)
            try:
                s_t, e_t = parse_time(start_raw), parse_time(end_raw)
                s_dt = tz.localize(datetime.combine(target_date, s_t))
                e_dt = tz.localize(datetime.combine(target_date, e_t))
                
                if e_dt <= s_dt:
                    e_dt += timedelta(days=1)
                
                if sheet_offset != 0:
                    s_dt += timedelta(hours=sheet_offset)
                    e_dt += timedelta(hours=sheet_offset)

                # FILTRO CRÍTICO: Entre ahora y +55 horas
                if e_dt > now and s_dt < limit_time:
                    programmes.append((s_dt, e_dt, title, desc, channel_id))
            except: continue
    
    programmes.sort(key=lambda x: x[0])
    return programmes

# ─── GENERADOR XML ───────────────────────────────────────────────────────────

def write_final_xml(channels_data):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE tv SYSTEM "xmltv.dtd">',
        '<tv generator-info-name="radios-epg-custom">'
    ]

    for ch in channels_data:
        name = ch.get("name") or "Canal sin nombre"
        lines.append(f'  <channel id="{ch["id"]}"><display-name>{html.escape(str(name))}</display-name></channel>')

    total_prog_count = 0
    for ch in channels_data:
        for start, end, title, desc, channel_id in ch["programmes"]:
            safe_title = html.escape(str(title)) if title is not None else "Sin título"
            safe_desc = html.escape(str(desc)) if desc is not None else ""
            lines.append(f'  <programme start="{xmltv_ts(start)}" stop="{xmltv_ts(end)}" channel="{channel_id}">')
            lines.append(f'    <title lang="es">{safe_title}</title>')
            if safe_desc: lines.append(f'    <desc lang="es">{safe_desc}</desc>')
            lines.append('  </programme>')
            total_prog_count += 1

    lines.append('</tv>')
    return "\n".join(lines), total_prog_count

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    final_data = []
    print("🚀 Iniciando generación de EPG (Límite: 55 horas)...\n")

    for ch in CHANNELS:
        content = fetch_url(ch["url"])
        if not content: continue
        try:
            csv_lines = content.decode("utf-8").splitlines()
            rows = list(csv.reader(csv_lines))[1:]
            progs = build_epg_from_sheets(rows, ch["id"])
            if progs:
                print(f"  📁 Sheet: {ch['name']} → {len(progs)} programas")
                final_data.append({"id": ch["id"], "name": ch["name"], "programmes": progs})
        except Exception as e:
            print(f"  ❌ Error en sheet {ch['name']}: {e}")

    external_channels = process_external_sources(EXTERNAL_SOURCES)
    final_data.extend(external_channels)

    if not final_data:
        print("⚠️ No hay datos para generar el archivo.")
        return

    xml_output, total_programs = write_final_xml(final_data)
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig") as f:
        f.write(xml_output)

    print("\n✨ PROCESO FINALIZADO CON ÉXITO")
    print(f"📺 Total Canales: {len(final_data)} | 📅 Total Programas: {total_programs}")
    print(f"💾 Guardado en: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
