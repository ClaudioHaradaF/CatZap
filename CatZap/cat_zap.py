#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import atexit
import json
import threading
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sqlite3
import shutil
import tempfile
import re

# Paths - MUST be before any other code
if getattr(sys, 'frozen', False):
    _BUNDLE_DIR = Path(sys._MEIPASS)
else:
    _BUNDLE_DIR = Path(__file__).parent

_APP_DATA = Path(os.environ.get('APPDATA', Path.home())) / 'CatZap'
_MODELS_DIR = _APP_DATA / 'models'
_BUNDLE_MODELS = _BUNDLE_DIR / 'models' / 'whisper'
_FALLBACK_BUNDLE_MODELS = _BUNDLE_DIR / '_internal' / 'models' / 'whisper'

if 'WHISPER_CACHE_DIR' in os.environ:
    _BUNDLE_MODELS = Path(os.environ['WHISPER_CACHE_DIR'])
elif _BUNDLE_MODELS.exists():
    pass
elif _FALLBACK_BUNDLE_MODELS.exists():
    _BUNDLE_MODELS = _FALLBACK_BUNDLE_MODELS
else:
    _BUNDLE_MODELS = None

PORT = 51777
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
TRANSCRIPTION_LANG = os.environ.get("WHISPER_LANG", "pt")
_MAX_PAYLOAD = 50 * 1024 * 1024

# Imports
try:
    from faster_whisper import WhisperModel
    HAS_FASTER = True
except ImportError:
    HAS_FASTER = False

try:
    from spellchecker import SpellChecker
    _SPELL_PT = SpellChecker(language='pt')
    HAS_SPELL = True
except:
    HAS_SPELL = False
    _SPELL_PT = None

model = None
model_lock = threading.Lock()
model_ready = threading.Event()
_TEMP_FILES = []
_TEMP_LOCK = threading.Lock()

_FALSE_POSITIVES = {"concerto", "presento", "assistir", "desse", "sessao", "secao", "cessao", "espeto", "espectador", "expectativa", "espiar"}

def _init_db():
    _APP_DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_APP_DATA / "transcricoes.db"), check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS transcricoes (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, duration REAL DEFAULT 0, time TEXT NOT NULL, audio_hash TEXT)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_time ON transcricoes(time)")
    conn.commit()
    return conn

def _save_transcription(text, duration, audio_hash=''):
    try:
        conn = _init_db()
        conn.execute("INSERT INTO transcricoes (text, duration, time, audio_hash) VALUES (?, ?, ?, ?)", (text, round(duration, 1), time.strftime("%Y-%m-%d %H:%M:%S"), audio_hash))
        conn.commit()
        conn.close()
    except:
        pass

def _post_process(text):
    if not HAS_SPELL or not _SPELL_PT or len(text) > 10000:
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

def _get_model():
    global model
    if model is None and HAS_FASTER:
        with model_lock:
            if model is None:
                models_to_try = ["small", "tiny"]
                for mod_name in models_to_try:
                    try:
                        _MODELS_DIR.mkdir(parents=True, exist_ok=True)
                        download_dir = str(_BUNDLE_MODELS) if _BUNDLE_MODELS else str(_MODELS_DIR)
                        print(f"[CatZap] Loading model {mod_name}...")
                        model = WhisperModel(mod_name, device="cpu", compute_type="int8", download_root=download_dir)
                        print(f"[CatZap] Model loaded: {mod_name}")
                        break
                    except Exception as e:
                        print(f"[CatZap] Model error: {e}")
                        model = None
                        continue
                if model is None:
                    model_ready.set()
                    return None
    model_ready.set()
    return model

def _cleanup_temp():
    with _TEMP_LOCK:
        for p in _TEMP_FILES:
            try:
                p.unlink(missing_ok=True)
            except:
                pass
        _TEMP_FILES.clear()
atexit.register(_cleanup_temp)

class CatZapHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok", "version": "CatZap v1.3", "model_loaded": model is not None, "model_ready": model_ready.is_set(), "faster_whisper": HAS_FASTER})
        elif self.path == "/model-status":
            err = ""
            if model is None and HAS_FASTER:
                err = "baixando modelo... (primeira vez leva alguns minutos)"
                if model_ready.is_set():
                    err = "falha ao carregar modelo"
            self._send_json({"ready": model is not None, "error": err, "model_name": WHISPER_MODEL if HAS_FASTER else ""})
        elif self.path == "/":
            self._send_html("<html><body style='font-family:sans-serif'><h1>CatZap v1.3</h1><p>Servidor rodando!</p><p><a href='/health'>health</a></p></body></html>")
        elif self.path == "/history":
            conn = _init_db()
            rows = conn.execute("SELECT text, duration, time, audio_hash FROM transcricoes ORDER BY id DESC LIMIT 100").fetchall()
            conn.close()
            self._send_json({"history": [{"text": r[0], "duration_secs": r[1] or 0, "timestamp": r[2], "audio_hash": r[3]} for r in rows]})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/log":
            length = int(self.headers.get("Content-Length", 0))
            if 0 < length < 10000:
                print(f"[CatZap Log] {self.rfile.read(length).decode()}")
            self._send_json({"ok": True})
            return
        if not self.path.startswith("/transcribe"):
            self.send_response(404)
            self.end_headers()
            return
        qs = parse_qs(urlparse(self.path).query)
        lang = qs.get("lang", [TRANSCRIPTION_LANG])[0]
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        print(f"[CatZap] Transcribe: {length} bytes lang={lang}")
        t0 = time.time()
        if model is not None:
            text, dur = "", 0
            tmp = None
            vad_params = [{"vad_filter": True}, {"vad_filter": False}]
            for ext in (".ogg", ".opus", ".webm", ".mp3", ""):
                for vp in vad_params:
                    try:
                        f = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                        f.write(raw)
                        tmp = Path(f.name)
                        f.close()
                        with _TEMP_LOCK:
                            _TEMP_FILES.append(tmp)
                        segments, info = model.transcribe(str(tmp), language=lang, **vp)
                        text = _post_process(" ".join(s.text for s in segments))
                        dur = getattr(info, 'duration', 0) or 0
                        break
                    except Exception as e:
                        print(f"[CatZap] Transcribe error ({ext}, VAD={vp['vad_filter']}): {e}")
                        tmp = None
                        continue
                else:
                    continue
                break
            self._send_json({"text": text, "duration_secs": dur})
        else:
            self._send_json({"text": "[ERRO] Modelo nao carregado", "duration_secs": 0})

    def do_DELETE(self):
        if self.path == "/history":
            conn = _init_db()
            conn.execute("DELETE FROM transcricoes")
            conn.commit()
            conn.close()
            self._send_json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, *a): pass

def _start_tray():
    _APP_DATA.mkdir(parents=True, exist_ok=True)
    def on_quit():
        _cleanup_temp()
        os._exit(0)
    for _ in range(3):
        try:
            import pystray
            from PIL import Image
            icon = pystray.Icon("CatZap", Image.new("RGBA", (16, 16), (0, 0, 0, 0)), f"CatZap v1.3 :{PORT}", 
                menu=pystray.Menu(pystray.MenuItem("Sair", on_quit)))
            icon.run(setup=None)
            return
        except Exception as e:
            print(f"[CatZap] Tray error: {e}")
            time.sleep(2)
    print("[CatZap] No tray, background mode")
    while True:
        time.sleep(3600)

def main():
    print(f"[CatZap] Starting (frozen={getattr(sys, 'frozen', False)})")
    _APP_DATA.mkdir(parents=True, exist_ok=True)
    
    server = HTTPServer(("127.0.0.1", PORT), CatZapHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[CatZap] Server on port {PORT}")
    
    if HAS_FASTER:
        threading.Thread(target=lambda: (_get_model(), print("[CatZap] Model ready")), daemon=True).start()
        for _ in range(300):
            if model_ready.is_set():
                break
            time.sleep(1)
        time.sleep(2)
    
    _start_tray()

if __name__ == "__main__" or getattr(sys, 'frozen', False):
    main()