#!/usr/bin/env python3
"""
CatZap v1.3 — Servidor de transcricao para extensao Chrome/Edge.
Executa em segundo plano (bandeja do sistema) e ouve em localhost:51777.
"""

import atexit
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

try:
    from faster_whisper import WhisperModel
    HAS_FASTER = True
except ImportError:
    HAS_FASTER = False

HAS_SPELL = False
model = None
model_lock = threading.Lock()
model_ready = threading.Event()
transcribe_lock = threading.Lock()
_SPELL_PT = None
_TEMP_FILES = []
_TEMP_LOCK = threading.Lock()
_MAX_PAYLOAD = 50 * 1024 * 1024
_splash_root = None
_splash_label = None
_splash_progress = None

# --- splash screen ---
def _create_splash():
    global _splash_root, _splash_label, _splash_progress
    try:
        import tkinter as tk
        from tkinter import ttk
        _splash_root = tk.Tk()
        _splash_root.title("CatZap")
        _splash_root.geometry("380x120")
        _splash_root.resizable(False, False)
        _splash_root.overrideredirect(True)
        _splash_root.configure(bg="#f0f0f0")
        _splash_root.wm_attributes("-topmost", True)
        # Center window
        x = (_splash_root.winfo_screenwidth() - 380) // 2
        y = (_splash_root.winfo_screenheight() - 120) // 2
        _splash_root.geometry(f"+{x}+{y}")
        # Icon
        try:
            _splash_root.iconbitmap(str(_BUNDLE_DIR / "cat_icon.ico"))
        except:
            pass
        # Content
        label = tk.Label(_splash_root, text="CatZap v1.3", font=("Segoe UI", 14, "bold"), bg="#f0f0f0")
        label.pack(pady=(15, 5))
        _splash_label = tk.Label(_splash_root, text="Iniciando servidor...", font=("Segoe UI", 10), bg="#f0f0f0")
        _splash_label.pack(pady=5)
        _splash_progress = ttk.Progressbar(_splash_root, mode="indeterminate")
        _splash_progress.pack(fill="x", padx=30, pady=10)
        _splash_progress.start(10)
    except Exception as e:
        print(f"[CatZap] Erro ao criar splash: {e}")

def _update_splash(text):
    global _splash_label, _splash_root
    if _splash_label and _splash_root:
        try:
            _splash_root.after(0, lambda: _splash_label.config(text=text))
        except:
            pass

def _close_splash():
    global _splash_root
    if _splash_root:
        try:
            _splash_root.after(0, _splash_root.quit)
        except:
            pass

def _splash_mainloop():
    global _splash_root
    if _splash_root:
        try:
            _splash_root.mainloop()
        except:
            pass

# --- diretorios ---
if getattr(sys, 'frozen', False):
    _APP_DIR = Path(sys.executable).parent
    _BUNDLE_DIR = Path(sys._MEIPASS)
else:
    _APP_DIR = Path(__file__).parent
    _BUNDLE_DIR = _APP_DIR

_APP_DATA = Path(os.environ['APPDATA']) / 'CatZap'
_EXT_SRC = _BUNDLE_DIR / 'cat_zap_extension'
_EXT_DST = _APP_DATA / 'extension'
_MODELS_DIR = _APP_DATA / 'models'
_BUNDLE_MODELS = _BUNDLE_DIR / 'models' / 'whisper'
_SETUP_MARKER = _APP_DATA / '.installed'

os.environ.setdefault('WHISPER_CACHE_DIR', str(_MODELS_DIR / 'whisper'))

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
TRANSCRIPTION_LANG = os.environ.get("WHISPER_LANG", "pt")
DB_PATH = _APP_DATA / "transcricoes.db"
PORT = 51777
MAX_PORT_TRIES = 10
MAX_SEEN = 10000

# --- banco SQLite ---
def _init_db():
    _APP_DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transcricoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            duration REAL DEFAULT 0,
            time TEXT NOT NULL,
            audio_hash TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_time ON transcricoes(time)")
    conn.commit()
    return conn

def _save_transcription(text, duration, audio_hash=''):
    try:
        conn = _init_db()
        conn.execute(
            "INSERT INTO transcricoes (text, duration, time, audio_hash) VALUES (?, ?, ?, ?)",
            (text, round(duration, 1), time.strftime("%Y-%m-%d %H:%M:%S"), audio_hash)
        )
        if MAX_SEEN:
            conn.execute(
                f"DELETE FROM transcricoes WHERE id <= (SELECT id FROM transcricoes ORDER BY id DESC LIMIT 1 OFFSET {MAX_SEEN})"
            )
        conn.commit()
        conn.close()
    except Exception:
        pass

# --- esconder console ---
def _hide_console():
    try:
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception:
        pass

# --- cleanup temporarios ---
def _cleanup_temp():
    with _TEMP_LOCK:
        for p in _TEMP_FILES:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
        _TEMP_FILES.clear()

atexit.register(_cleanup_temp)

# --- correcao ortografica ---
_FALSE_POSITIVES = {
    "concerto", "presento", "assistir", "desse", "sessao", "secao", "cessao",
    "espeto", "espectador", "expectativa", "espiar",
}

def _post_process(text):
    if not HAS_SPELL or not _SPELL_PT:
        return text
    if len(text) > 10000:
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

def _write_log(path, content):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception:
        pass

def _get_model():
    global model
    if model is None and HAS_FASTER:
        with model_lock:
            if model is None:
                models_to_try = [WHISPER_MODEL]
                if WHISPER_MODEL != "tiny":
                    models_to_try.append("tiny")
                for mod_name in models_to_try:
                    try:
                        _MODELS_DIR.mkdir(parents=True, exist_ok=True)
                        # Check if model is bundled
                        download_dir = str(_MODELS_DIR / 'whisper')
                        if getattr(sys, 'frozen', False) and _BUNDLE_MODELS.exists():
                            download_dir = str(_BUNDLE_MODELS)
                            _update_splash(f"Carregando modelo '{mod_name}' embutido...")
                        else:
                            _update_splash(f"Baixando modelo '{mod_name}' (pode levar alguns minutos)...")
                        model = WhisperModel(mod_name, device="cpu", compute_type="int8",
                                         download_root=download_dir)
                        _update_splash(f"Modelo '{mod_name}' carregado!")
                        print(f"[CatZap Server] Modelo '{mod_name}' carregado com sucesso")
                        break
                    except Exception as e:
                        tb = traceback.format_exc()
                        log_path = str(_APP_DATA / 'erro_modelo.log')
                        _write_log(log_path,
                            f"[{time.ctime()}] Falha ao carregar modelo '{mod_name}'\n"
                            f"Erro: {e}\n\n{tb}")
                        print(f"[CatZap Server] ERRO ao carregar modelo '{mod_name}': {e}")
                        traceback.print_exc()
                        model = None
                if model is None:
                    model_ready.set()
                    return None
    model_ready.set()
    return model

def _compute_hash(audio_bytes):
    return str(hash(audio_bytes[:4096]))

def _do_transcribe(audio_bytes, lang):
    m = _get_model()
    if m is None:
        return "[ERRO] Modelo nao carregado", 0
    if len(audio_bytes) < 100:
        return "[ERRO] Audio muito curto", 0
    print(f"[CatZap Server] Audio: {len(audio_bytes)} bytes")

    audio_hash = _compute_hash(audio_bytes)
    suf = f"catzap_{int(time.time()*1000)}_{os.urandom(2).hex()}"
    tmp = None
    for ext in (".ogg", ".opus", ".webm", ".mp3", ""):
        try:
            f = tempfile.NamedTemporaryFile(suffix=ext, prefix=suf, delete=False)
            f.write(audio_bytes)
            tmp = Path(f.name)
            f.close()
            with _TEMP_LOCK:
                _TEMP_FILES.append(tmp)
            print(f"[CatZap Server] Tentando transcricao ({ext or 'sem ext'})...")
            with transcribe_lock:
                segments, info = m.transcribe(str(tmp), language=lang or TRANSCRIPTION_LANG, vad_filter=True)
            texts = [s.text for s in segments]
            text = " ".join(texts)
            text = _post_process(text)
            dur = float(info.duration) if hasattr(info, 'duration') and info.duration else 0
            _save_transcription(text, dur, audio_hash)
            return text, dur
        except Exception as e:
            print(f"[CatZap Server] Falha com extensao '{ext}': {e}")
            if tmp and tmp.exists():
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
                with _TEMP_LOCK:
                    if tmp in _TEMP_FILES:
                        _TEMP_FILES.remove(tmp)
            tmp = None
            continue
    return "[ERRO] Nao foi possivel decodificar o audio com nenhum formato", 0

# --- servidor HTTP ---
class CatZapHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._send_json({
                "status": "ok", "version": "CatZap v1.3",
                "model_loaded": model is not None,
                "model_ready": model_ready.is_set(),
                "faster_whisper": HAS_FASTER,
            })
        elif self.path == "/model-status":
            err = ""
            if model is None and HAS_FASTER:
                err = "baixando modelo Whisper... (primeira vez leva alguns minutos)"
                if model_ready.is_set():
                    err = "falha ao carregar modelo. Verifique internet e disco."
            self._send_json({
                "ready": model is not None,
                "error": err,
                "model_name": WHISPER_MODEL if HAS_FASTER else "",
            })
        elif self.path == "/":
            self._send_html(f"""<html><body style="font-family:sans-serif;text-align:center;padding:40px">
            <h1>\U0001f431 CatZap v1.3</h1>
            <p>Servidor de transcricao rodando!</p>
            <p><a href="/health">health check</a></p>
            </body></html>
            """)
        elif self.path == "/history":
            conn = _init_db()
            rows = conn.execute(
                "SELECT text, duration, time, audio_hash FROM transcricoes ORDER BY id DESC LIMIT 100"
            ).fetchall()
            conn.close()
            history = [
                {"text": r[0], "duration_secs": r[1] or 0, "timestamp": r[2], "audio_hash": r[3]}
                for r in rows
            ]
            self._send_json({"history": history})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/log":
            length = int(self.headers.get("Content-Length", 0))
            if 0 < length < 10000:
                msg = self.rfile.read(length).decode("utf-8", errors="replace")
                print(f"[CatZap Log] {msg}")
            self._send_json({"ok": True})
            return
        if self.path != "/transcribe":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        if length > _MAX_PAYLOAD:
            self.send_response(413)
            self.end_headers()
            return
        raw = self.rfile.read(length)
        lang = self.headers.get("X-Lang", TRANSCRIPTION_LANG)
        print(f"[CatZap Server] POST /transcribe {length} bytes lang={lang}")
        if not raw:
            self._send_json({"error": "Sem dados de audio"})
            return
        t0 = time.time()
        text, dur = _do_transcribe(raw, lang)
        dt = time.time() - t0
        print(f"[CatZap Server] Transcrito em {dt:.1f}s: {text[:80]}")
        self._send_json({"text": text, "duration_secs": dur})

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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Lang, X-Log")
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
        pass

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
            _cleanup_temp()
            os._exit(0)
        icon = pystray.Icon("CatZap", icon_img, f"CatZap v1.3 :{PORT}", menu=pystray.Menu(
            pystray.MenuItem("Abrir health check", lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/health")),
            pystray.MenuItem("Abrir pasta da extensao", lambda: os.startfile(str(_EXT_DST))),
            pystray.MenuItem("Sair", on_quit),
        ))
        icon.run()
    except ImportError:
        try:
            while True: time.sleep(3600)
        except KeyboardInterrupt:
            _cleanup_temp()
            os._exit(0)

# --- setup primeira execucao ---
def _copy_extension():
    if _EXT_DST.exists():
        shutil.rmtree(_EXT_DST)
    _EXT_DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(_EXT_SRC), str(_EXT_DST))
    return _EXT_DST

def _create_shortcut():
    desktop = Path(os.environ['USERPROFILE']) / 'Desktop'
    lnk = desktop / 'CatZap.lnk'
    if lnk.exists():
        return
    ps = f'''
    $WS = New-Object -ComObject WScript.Shell
    $SC = $WS.CreateShortcut("{lnk}")
    $SC.TargetPath = "{sys.executable}"
    $SC.WorkingDirectory = "{_APP_DATA}"
    $SC.Description = "CatZap - Transcricao de audios do WhatsApp"
    $SC.IconLocation = "{sys.executable}, 0"
    $SC.Save()
    '''
    try:
        subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                       shell=True, capture_output=True, timeout=15)
    except Exception:
        pass

def _ensure_extension():
    """Sempre extrai/atualiza a extensao. Returns o path destino."""
    if not _EXT_SRC.exists():
        if getattr(sys, 'frozen', False):
            print("[CatZap] Bundle corrompido — extensao ausente. Reinstale.")
            sys.exit(1)
        return _EXT_SRC
    dst = _copy_extension()
    return dst

def _setup_first_run():
    """Setup silencioso — copia extensao, atalho, marca .installed."""
    primeiro = not _SETUP_MARKER.exists()
    _ensure_extension()
    if primeiro:
        _create_shortcut()
        _APP_DATA.mkdir(parents=True, exist_ok=True)
        _SETUP_MARKER.touch()
    return primeiro

def _show_model_error():
    log_path = str(_APP_DATA / 'erro_modelo.log')
    tb_text = ""
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            tb_text = f.read()
    except Exception:
        pass
    msg = (
        "CatZap não conseguiu carregar o modelo Whisper.\n\n"
        "Detalhes salvos em:\n"
        f"  {log_path}\n\n"
        "Possíveis causas:\n"
        "• Sem acesso à internet (precisa baixar o modelo na primeira vez)\n"
        "• Disco sem espaço livre suficiente\n"
        "• Antivírus bloqueando o download\n"
        "• DLL/componente faltando\n\n"
        "Após resolver, reinicie o CatZap."
    )
    if tb_text:
        msg += f"\n\n--- LOG DO ERRO ---\n{tb_text[:2000]}"
    print(f"[CatZap Server] {msg}")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "CatZap - Erro no Modelo", 0x10 | 0x1000)
    except Exception:
        pass

# --- uninstall ---
def _do_uninstall():
    print("[CatZap] Desinstalando...")
    try:
        subprocess.run(['reg', 'delete', r'HKCU\Software\Microsoft\Windows\CurrentVersion\Run',
                        '/v', 'CatZap', '/f'], capture_output=True, timeout=10)
    except Exception:
        pass
    try:
        _SETUP_MARKER.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        subprocess.run(['taskkill', '/f', '/im', 'CatZap.exe'], capture_output=True, timeout=10)
    except Exception:
        pass
    os._exit(0)

# --- main ---
def main():
    if '--uninstall' in sys.argv[1:]:
        _do_uninstall()

    _create_splash()
    threading.Thread(target=_splash_mainloop, daemon=True).start()
    _update_splash("Configurando...")

    _setup_first_run()

    port = PORT
    server = None
    for attempt in range(MAX_PORT_TRIES):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), CatZapHandler)
            break
        except OSError:
            port += 1
    if server is None:
        _close_splash()
        sys.exit(1)

    threading.Thread(target=server.serve_forever, daemon=True).start()
    _update_splash("Servidor iniciado. Carregando modelo...")

    if HAS_FASTER:
        def _load_and_notify():
            _get_model()
            if model is None:
                _close_splash()
                _show_model_error()
            else:
                _update_splash("Modelo carregado! Pronto para uso.")
        threading.Thread(target=_load_and_notify, daemon=True).start()
        # Wait for model to load (up to 5 min for first time download)
        for _ in range(300):
            if model_ready.is_set():
                break
            time.sleep(1)
        time.sleep(2)  # Show "Pronto" message briefly
    else:
        _update_splash("Servidor rodando!")
        model_ready.set()
        time.sleep(1)

    _close_splash()
    _start_tray()

if __name__ == "__main__" or getattr(sys, 'frozen', False):
    main()
