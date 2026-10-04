import urllib.parse
from flask import Flask, Response, request
import requests

app = Flask(__name__)

BASE_URL = "https://tv.japanmotion.com"
STREAM_URL = f"{BASE_URL}/iptv/session/1/hls.m3u8"
HEADERS = {
    "Referer": "https://japanmotion.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

@app.route('/')
@app.route('/japanmotion.m3u8')
def proxy_m3u8():
    res = requests.get(STREAM_URL, headers=HEADERS)
    if res.status_code != 200:
        return Response("Error al obtener manifiesto", status=res.status_code)
    
    lines = res.text.splitlines()
    new_lines = []
    
    # Reescribir cada línea que contenga una URL de segmento o sub-lista para que pase por el proxy
    for line in lines:
        line_strip = line.strip()
        if line_strip and not line_strip.startswith('#'):
            # Si es una URL relativa o absoluta, la redirigimos a nuestro proxy
            if not line_strip.startswith('http'):
                full_target = urllib.parse.urljoin("https://tv.japanmotion.com/iptv/session/1/", line_strip)
            else:
                full_target = line_strip
            
            # Generar URL proxy para este recurso
            proxy_segment_url = request.host_url.rstrip('/') + "/segment?url=" + urllib.parse.quote(full_target)
            new_lines.append(proxy_segment_url)
        else:
            new_lines.append(line)
            
    modified_m3u8 = "\n".join(new_lines)
    return Response(modified_m3u8, content_type='application/vnd.apple.mpegurl')

@app.route('/segment')
def proxy_segment():
    target_url = request.args.get('url')
    if not target_url:
        return Response("URL no proporcionada", status=400)
    
    # Hacer la petición con las cabeceras requeridas por Cloudflare
    req = requests.get(target_url, headers=HEADERS, stream=True)
    
    # Retransmitir la respuesta del segmento al reproductor
    return Response(
        req.iter_content(chunk_size=1024*64),
        content_type=req.headers.get('Content-Type', 'video/MP2T')
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
