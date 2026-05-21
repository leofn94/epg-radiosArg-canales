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
]

# 2. FUENTES XML EXTERNAS
EXTERNAL_SOURCES = [
    {
        "url": "https://raw.githubusercontent.com/Puticastillo/EPGCL/refs/heads/main/vilma/guia-de-programacion.xml",
        "ids": ["0204", "0205", "0206", "0209", "0210", "0215", "0222", "0318", "0431", "0432", "0433", "0528", "0533", "0604", "0621", "0629", "0302", "0308",
                "0636", "0643", "0707", "0808", "0821", "0822", "0823", "0824", "0827", "0838", "0839", "0842", "0851", "0855", "0856", "0859", "0860", "0812",
                "0903", "0904", "0905", "0909", "0915", "0916", "0917", "0920", "0927", "0932", "0934", "0935", "1806", "1810", "1814", "2701", "1625", "1832",
                "2813", "XXX8", "0831", "0818", "0820", "0815", "1813", "0622", "0850", "0807", "1409", "1418", "1411", "1412", "2413", "1610", "0704", "0703",
                "0605", "1436"]
    },
    {
        "url": "https://epg.programadorx.cl/mdiaz/gratis.xml",
        "ids": ["504", "531", "532", "536", "537", "538", "539", "567", "568", "569", "581", "663", "664", "609", "633"]
    },
    {
        "url": "https://i.mjh.nz/PlutoTV/mx.xml",
        "ids": ["66a11a21a79dea0008aa90ca", "5de5758e1a30dc00094fcd6c", "63a084934734f30007457b2c", "6894fc3f66f164e402f4fd14", "6894febddbd49c964f3b66c8", "5dcde17bf6591d0009839e02", "6870072ca9d5c45c3e9466f1", 
                "645952687cb4b100084ed52e","6824cda00101510f9eeaa011", "6254598f5083f800076d8563", "609ae5cd48d3200007b0a98e","65df731cec9fda0008b7aa8d", "65df7272ec9fda0008b7a970", "65df73520d4561000817c29b",
                "65df72db18036500081a8292", "5dcde1317578340009b751d0", "65662f8a2c46f300088a84cc","6479ff1c17f5e10008ad2797", "655f62ff954b020008c91ec6", "5de802659167b10009e7deba","5ff608e60e2996000768c366", 
                "5f2817d3d7573a00080f9175","5dcde437229eff00091b6c30", "5e972a21ad709d00074195ba", "5dcb62e63d4d8f0009f36881","5ddc4e8bcbb9010009b4e84f", "5dcddf1ed95e740009fef7ab","66997d18a1b69e00082ee85f"]
    },
    {
        "url": "https://raw.github.com/matthuisman/i.mjh.nz/master/SamsungTVPlus/es.xml",
        "ids": ["ES3400004SS", "ES300029LP", "ES3000288I", "ESBC1700004PX", "ESBC2700003T8", "ESBC40000248", "ESBC2700002LO"]
    },
    {
        "url": "https://raw.github.com/matthuisman/i.mjh.nz/master/SamsungTVPlus/us.xml",
        "ids": ["USBD3500008IJ","USBD35000149S", "USBD35000180U", "US2600019IC","USBD1200009JI", "US2200001IY", "US5000053YV", "USAJ3504502A", "US1900002QK", "US1800014CG", "USBD12000255B",
               "USAK3508705A", "US700012OU", "USBA3800004EL"]
    },
    {
        "url": "https://raw.github.com/matthuisman/i.mjh.nz/master/SamsungTVPlus/gb.xml",
        "ids": ["GB2300005ML", "GBBD4900001RG", "GBBD1900009UD", "GBBC2100002HP", "GB500007VM"]
    },
    {
        "url": "https://i.mjh.nz/Plex/us.xml",
        "ids": ["5e20b730f2f8d5003d739db7-64b710b44612b1f48e9ad31a", "5e20b730f2f8d5003d739db7-6876f76054325376973fd314", "5e20b730f2f8d5003d739db7-69727a4631b12b32a91db6b3",
                "5e20b730f2f8d5003d739db7-689fb7110a486aeba3c7917c", "5e20b730f2f8d5003d739db7-5ef4e1b40d9ad000423c442a", "5e20b730f2f8d5003d739db7-66a2d1390b91165254efdb3e",
                "5e20b730f2f8d5003d739db7-688006e7015fe7e375a1a0ac", "5e20b730f2f8d5003d739db7-6889430a3b7708975e7c07e3", "5e20b730f2f8d5003d739db7-63dea56a2a2abb171ff6dadf",
                "5e20b730f2f8d5003d739db7-62d1efa6c33948ea4ceedbcf", "5e20b730f2f8d5003d739db7-5eea605574085f0040ddc791", "5e20b730f2f8d5003d739db7-671a924b79fce6628115432c",
                "5e20b730f2f8d5003d739db7-5fc70600dd53a6002d8f93ca", "5e20b730f2f8d5003d739db7-6478acb5c83f56da796f166c", "5e20b730f2f8d5003d739db7-6571f43a1d2aae780d597196",
                "5e20b730f2f8d5003d739db7-646fab0e43d6d6838db81a6a", "5e20b730f2f8d5003d739db7-68fafc6e558214386ab7ca3a", "5e20b730f2f8d5003d739db7-62d7f68fb19cbf65dc7bef7d",
                "5e20b730f2f8d5003d739db7-5f170d61b898490041b49369"]
    },
    {
        "url": "https://i.mjh.nz/Plex/gb.xml",
        "ids": ["64305451fc3be5947773c339-66855a2a714fe577eb7db920"]
    },
    {
        "url": "https://i.mjh.nz/Plex/mx.xml",
        "ids": ["608049aefa2b8ae93c2c3a63-67642f277c5e3b38af72dcdb", "608049aefa2b8ae93c2c3a63-6684374320f405b792a3b6b3", "608049aefa2b8ae93c2c3a63-66843a1f20f405b792a3b6b5", 
                "608049aefa2b8ae93c2c3a63-6685abbe59703916799193a7", "608049aefa2b8ae93c2c3a63-668434f6a017b7e51aeb28d3"]
    },
    {
        "url": "https://raw.githubusercontent.com/matthuisman/i.mjh.nz/refs/heads/master/Plex/es.xml",
        "ids": ["643054b1fc3be59477853717-66840a26cd6f1d3940941155", "643054b1fc3be59477853717-6683fcdf702b9db9f8177252", "643054b1fc3be59477853717-66841b30702b9db9f8177258",
               "643054b1fc3be59477853717-692235265cbe620c1f9b6bc7","643054b1fc3be59477853717-692234015028288613484a8a","643054b1fc3be59477853717-6922322350fe592fd6d5b7e6",
                "643054b1fc3be59477853717-66840253cd6f1d394094114f","643054b1fc3be59477853717-6490e17c18a55242eea95991","643054b1fc3be59477853717-668420c2cd6f1d3940941157",
               "643054b1fc3be59477853717-6922338150fe592fd6d5b7e8"]
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
        "ids": ["Dark.es", "TCM.es", "M+.Clásicos.es", "Canal.24.h.es"]
    },
    {
        "url": "https://github.com/HelmerLuzo/RakutenTV_HL/raw/refs/heads/main/epg/RakutenTV.xml.gz",
        "ids": ["that-s-80s", "that-s-90s00s", "that-s-rock", "filmrise-sci-fi-es", "sci-fi-rakuten-tv", "action-rakuten-tv", "thriller-rakuten-tv", "fifa-plus-es-new", "cine-western-es",
               "stingray-remember-the-80-s", "top-movies-rakuten-tv"]
    },
    {
        "url": "https://helmerluzo.github.io/RuntimeTV_HL/epg/RuntimeTV.xml.gz",
        "ids": ["sangre-fria"]
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
            for ch_id in target_ids:
                ch_node = root.find(f"./channel[@id='{ch_id}']")
                ch_name = ch_node.find("display-name").text if ch_node is not None else f"Extra {ch_id}"
                
                hour_offset = OFFSET_CONFIG.get(ch_id, 0)
                programmes = []
                for prog in root.findall(f"./programme[@channel='{ch_id}']"):
                    fmt = "%Y%m%d%H%M%S %z"
                    try:
                        s_dt = datetime.strptime(prog.get("start"), fmt).astimezone(tz_arg)
                        e_dt = datetime.strptime(prog.get("stop"), fmt).astimezone(tz_arg)
                        
                        if hour_offset != 0:
                            s_dt += timedelta(hours=hour_offset)
                            e_dt += timedelta(hours=hour_offset)
                        
                        # FILTRO CRÍTICO: Entre ahora y +55 horas
                        if e_dt > now and s_dt < limit_time:
                            title = prog.find("title").text if prog.find("title") is not None else "Sin título"
                            desc = prog.find("desc").text if prog.find("desc") is not None else ""
                            programmes.append((s_dt, e_dt, title, desc, ch_id))
                    except: continue
                
                if programmes:
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
