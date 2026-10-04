from flask import Flask, Response
import requests

app = Flask(__name__)

STREAM_URL = "https://tv.japanmotion.com/iptv/session/1/hls.m3u8"
HEADERS = {
    "Referer": "https://japanmotion.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

@app.route('/')
@app.route('/japanmotion.m3u8')
def proxy_m3u8():
    res = requests.get(STREAM_URL, headers=HEADERS)
    return Response(res.content, content_type='application/vnd.apple.mpegurl')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
