#!/usr/bin/env python3
"""
CatZap v1.0 — Servidor de transcricao para extensao Chrome/Edge.
Executa em segundo plano (bandeja do sistema) e ouve em localhost:51777.
"""

import json
import os
import re
import sys
import threading
import time
import traceback
import unicodedata
import tempfile
import io
import webbrowser
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HAS_FASTER = False
HAS_SPELL = False
model = None
model_lock = threading.Lock()
model_ready = threading.Event()
transcribe_lock = threading.Lock()
_SPELL_PT = None

try:
    from faster_whisper import WhisperModel
    HAS_FASTER = True
except ImportError:
    HAS_FASTER = False

try:
    from spellchecker import SpellChecker
    _SPELL_PT = SpellChecker(language='pt')
    HAS_SPELL = True
except Exception:
    HAS_SPELL = False

# --- configuracoes ---
if getattr(sys, 'frozen', False):
    _APP_DIR = Path(sys.executable).parent
else:
    _APP_DIR = Path(__file__).parent

WHISPER_MODEL = "small"
TRANSCRIPTION_LANG = os.environ.get("WHISPER_LANG", "pt")
EXPORT_FILE = _APP_DIR / "transcricoes.json"
PORT = 51777
MAX_SEEN = 10000

# --- correcao ortografica ---
_FALSE_POSITIVES = {
    "concerto", "presento", "assistir", "desse", "sessão", "seção", "cessão",
    "espeto", "espectador", "expectativa", "espiar",
}

def _post_process(text):
    if not HAS_SPELL or not _SPELL_PT:
        return text
    def _fix(m):
        w = m.group(0)
        if w.lower() in _FALSE_POSITIVES:
            return w
        if w.isupper():
            fix = _SPELL_PT.correction(w.lower()) or w.lower()
            return fix.upper() if fix else w
        if w[0].isupper():
            fix = _SPELL_PT.correction(w.lower()) or w.lower()
            return fix.capitalize() if fix else w
        return _SPELL_PT.correction(w) or w
    return re.sub(r'\b[a-zA-Z\u00C0-\u024F]{3,}\b', _fix, text)

# --- modelo ---
def _get_model():
    global model
    if model is None and HAS_FASTER:
        with model_lock:
            if model is None:
                try:
                    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
                    print(f"[CatZap Server] Modelo '{WHISPER_MODEL}' carregado com sucesso")
                except Exception as e:
                    print(f"[CatZap Server] ERRO ao carregar modelo: {e}")
                    traceback.print_exc()
                    return None
    model_ready.set()
    return model

def _transcribe(audio_bytes, lang):
    m = _get_model()
    if m is None:
        return "[ERRO] Modelo nao carregado"
    if len(audio_bytes) < 100:
        return "[ERRO] Audio muito curto"
    print(f"[CatZap Server] Audio: {len(audio_bytes)} bytes, primeiros bytes: {audio_bytes[:16].hex()}")

    suf = f"catzap_{int(time.time()*1000)}_{os.urandom(2).hex()}"
    tmp = None
    for ext in (".ogg", ".opus", ".webm", ".mp3", ""):
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, prefix=suf, delete=False) as f:
                f.write(audio_bytes)
                tmp = Path(f.name)
            print(f"[CatZap Server] Tentando transcricao ({ext or 'sem ext'})...")
            with transcribe_lock:
                segments, info = m.transcribe(str(tmp), language=lang or TRANSCRIPTION_LANG, vad_filter=True)
                texts = []
                for s in segments:
                    texts.append(s.text)
            text = " ".join(texts)
            text = _post_process(text)
            dur = float(info.duration) if hasattr(info, 'duration') and info.duration else 0
            _save_transcription(text, dur)
            return text
        except Exception as e:
            print(f"[CatZap Server] Falha com extensao '{ext}': {e}")
            if tmp and tmp.exists():
                tmp.unlink(missing_ok=True)
            tmp = None
            continue
    return "[ERRO] Nao foi possivel decodificar o audio com nenhum formato"

def _save_transcription(text, duration):
    entry = {"text": text, "duration": round(duration, 1), "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        if EXPORT_FILE.exists():
            data = json.loads(EXPORT_FILE.read_text(encoding="utf-8"))
        else:
            data = []
        data.append(entry)
        if len(data) > MAX_SEEN:
            data = data[-MAX_SEEN:]
        EXPORT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

# --- servidor HTTP ---
class CatZapHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._send_json({
                "status": "ok", "version": "CatZap v1.0",
                "model_loaded": model is not None,
                "model_ready": model_ready.is_set(),
                "faster_whisper": HAS_FASTER,
            })
        elif self.path == "/":
            self._send_html("""
            <html><body style="font-family:sans-serif;text-align:center;padding:40px">
            <h1>🐱 CatZap v1.0</h1>
            <p>Servidor de transcricao rodando!</p>
            <p><a href="/health">health check</a></p>
            </body></html>
            """)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/transcribe":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        lang = self.headers.get("X-Lang", TRANSCRIPTION_LANG)
        print(f"[CatZap Server] POST /transcribe {length} bytes lang={lang}")
        if not raw:
            self._send_json({"error": "Sem dados de audio"})
            return
        t0 = time.time()
        text = _transcribe(raw, lang)
        dt = time.time() - t0
        print(f"[CatZap Server] Transcrito em {dt:.1f}s: {text[:80]}")
        self._send_json({"text": text})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Lang")
        self.end_headers()

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass  # silencioso

# --- tray icon ---
def _start_tray():
    try:
        import pystray
        from PIL import Image
        icon_img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        px = icon_img.load()
        B,W,Y = (60,55,70,255),(252,250,255,255),(255,235,140,255)
        for (x,y),c in [((3,2),B),((4,2),B),((11,2),B),((12,2),B),
                         ((2,3),B),((12,3),B),((2,4),B),((12,4),B),
                         ((4,5),Y),((5,5),Y),((9,5),Y),((10,5),Y),
                         ((4,6),B),((5,6),B),((9,6),B),((10,6),B),
                         ((5,9),B),((6,9),B),((8,9),B),((9,9),B),
                         ((6,10),B),((7,10),B),((8,10),B),
                         ((4,11),B),((5,11),B),((9,11),B),((10,11),B),
                         ((6,12),B),((7,12),B),((8,12),B)]:
            if 0<=x<16 and 0<=y<16: px[x,y]=c
        def on_quit():
            os._exit(0)
        icon = pystray.Icon("CatZap", icon_img, "CatZap v1.0", menu=pystray.Menu(
            pystray.MenuItem("Abrir health check", lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/health")),
            pystray.MenuItem("Sair", on_quit),
        ))
        icon.run()
    except ImportError:
        try:
            while True: time.sleep(3600)
        except KeyboardInterrupt:
            os._exit(0)

# --- main ---
def main():
    print(r"  /\_/\  ")
    print(r" ( o.o ) ")
    print(r"  > ^ <  ")
    print("CatZap v1.0 — Servidor de transcricao")
    print(f"Ouvindo em http://127.0.0.1:{PORT}")
    print("Instale a extensao no Chrome/Edge e acesse web.whatsapp.com")
    print()

    # Load model (in foreground so it's ready before requests)
    if HAS_FASTER:
        print("[CatZap Server] Carregando modelo Whisper... (pode levar alguns segundos)")
        sys.stdout.flush()
        _get_model()
    else:
        model_ready.set()

    # Start server
    server = ThreadingHTTPServer(("127.0.0.1", PORT), CatZapHandler)
    st = threading.Thread(target=server.serve_forever, daemon=True)
    st.start()

    # Start tray (blocking)
    _start_tray()

if __name__ == "__main__":
    main()
