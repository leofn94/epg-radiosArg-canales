import urllib.parse
from flask import Flask, Response, request
from curl_cffi import requests

app = Flask(__name__)

STREAM_URL = "https://tv.japanmotion.com/iptv/session/1/hls.m3u8"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Origin": "https://japanmotion.com",
    "Referer": "https://japanmotion.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site"
}

@app.route('/')
@app.route('/japanmotion.m3u8')
def proxy_m3u8():
    try:
        # impersonate="chrome" emula la huella TLS/JA3 exacta de un navegador Chrome real
        res = requests.get(STREAM_URL, headers=HEADERS, impersonate="chrome", timeout=10)
        
        if res.status_code != 200:
            return Response(f"Error desde el origen: {res.status_code}", status=res.status_code)

        lines = res.text.splitlines()
        new_lines = []
        
        for line in lines:
            line_strip = line.strip()
            if line_strip and not line_strip.startswith('#'):
                if not line_strip.startswith('http'):
                    full_target = urllib.parse.urljoin("https://tv.japanmotion.com/iptv/session/1/", line_strip)
                else:
                    full_target = line_strip
                
                proxy_segment_url = request.host_url.rstrip('/') + "/segment?url=" + urllib.parse.quote(full_target)
                new_lines.append(proxy_segment_url)
            else:
                new_lines.append(line)
                
        modified_m3u8 = "\n".join(new_lines)
        return Response(modified_m3u8, content_type='application/vnd.apple.mpegurl')
        
    except Exception as e:
        return Response(f"Error de conexión: {str(e)}", status=500)

@app.route('/segment')
def proxy_segment():
    target_url = request.args.get('url')
    if not target_url:
        return Response("URL no proporcionada", status=400)
    
    try:
        # Petición emulando Chrome para descargar cada segmento .ts
        req = requests.get(target_url, headers=HEADERS, impersonate="chrome", stream=True, timeout=10)
        
        return Response(
            req.content,
            content_type=req.headers.get('Content-Type', 'video/MP2T')
        )
    except Exception as e:
        return Response(f"Error cargando segmento: {str(e)}", status=500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
