#!/usr/bin/env python3
"""
WhatsApp Web Audio Transcriber v14.0
Captura audio via URL.createObjectURL e vincula ao clique.
"""

import json
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path

try:
    from faster_whisper import WhisperModel
    HAS_FASTER = True
except ImportError:
    HAS_FASTER = False

try:
    import whisper
except ImportError:
    whisper = None

from playwright.sync_api import sync_playwright


WHATSAPP_URL = "https://web.whatsapp.com"
TEMP_DIR = Path("temp_audio_files")
USER_DATA_DIR = Path("whatsapp_session")
WHISPER_MODEL = "small"
TRANSCRIPTION_LANG = os.environ.get("WHISPER_LANG", "pt")
EXPORT_FILE = Path("transcricoes.json")
MAX_SEEN = 10000


INJECT_SCRIPT = """
(() => {
    window.__waAudioCache = {};
    window.__waClickTranscribe = [];
    window.__waSeqCounter = 0;
    window.__waLastClick = 0;
    window.__waClickCount = 0;
    window.__waClickedBlobUrl = null;
    window.__waPlayedBlobUrl = null;
    window.__waPlayedTime = 0;

    function _findBlobUrl(row) {
        var els = row.querySelectorAll('[src*="blob:"]');
        for (var i = 0; i < els.length; i++)
            if (els[i].src && els[i].src.indexOf('blob:') === 0) return els[i].src;
        var all = row.querySelectorAll('*');
        for (var i = 0; i < all.length; i++) {
            var bg = (all[i].style && (all[i].style.backgroundImage || all[i].style.background)) || '';
            var m = bg.match(/blob:[^\\s"')]+/);
            if (m) return m[0];
        }
        return null;
    }

    function _queueTranscribe(url) {
        var c = window.__waAudioCache[url];
        if (c && !c._q) {
            c._q = true;
            c.blob.arrayBuffer().then(function(buf) {
                window.__waClickTranscribe.push({
                    d: Array.from(new Uint8Array(buf)),
                    seq: c.seq, url: url,
                    clickTime: window.__waLastClick || Date.now(),
                    t: Date.now()
                });
            }).catch(function(){});
        }
    }

    window.__waRowForUrl = {};

    // Clique: salva linha, escaneia por blob URL e enfileira transcricao
    document.addEventListener('pointerdown', function(e) {
        var row = e.target.closest('[role="row"]');
        if (row) {
            window.__waLastClickedRow = row;
            window.__waLastClick = Date.now();
            window.__waClickCount++;
            var url = _findBlobUrl(row);
            window.__waClickedBlobUrl = url;
            if (url) { window.__waRowForUrl[url] = row; _queueTranscribe(url); }
        }
    }, true);

    // Intercepta HTMLMediaElement.play
    (function() {
        var p = HTMLMediaElement.prototype.play;
        HTMLMediaElement.prototype.play = function() {
            var s = this.currentSrc || this.src;
            if (s && s.indexOf('blob:') === 0) {
                window.__waPlayedBlobUrl = s;
                window.__waPlayedTime = Date.now();
                _queueTranscribe(s);
            }
            return p.apply(this, arguments);
        };
    })();

    // URL.createObjectURL: apenas cacheia, nunca enfileira
    var _orig = URL.createObjectURL.bind(URL);
    URL.createObjectURL = function(b) {
        var url = _orig(b);
        if (b && b.type && b.type.includes('audio')) {
            window.__waSeqCounter += 1;
            window.__waAudioCache[url] = {
                blob: b, seq: window.__waSeqCounter,
                _q: false, clickTime: window.__waLastClick || 0
            };
        }
        return url;
    };
})();
"""

POLL_SCRIPT = """
(() => {
    var out = { audio: [], clickUrl: null, playedUrl: null };
    if (window.__waClickTranscribe && window.__waClickTranscribe.length) {
        out.audio = JSON.parse(JSON.stringify(window.__waClickTranscribe));
        window.__waClickTranscribe = [];
    }
    if (window.__waClickedBlobUrl) {
        out.clickUrl = window.__waClickedBlobUrl;
        window.__waClickedBlobUrl = null;
    }
    if (window.__waPlayedBlobUrl) {
        out.playedUrl = window.__waPlayedBlobUrl;
        out.playedTime = window.__waPlayedTime || 0;
        window.__waPlayedBlobUrl = null;
        window.__waPlayedTime = 0;
    }
    return out;
})()
"""

SHOW_TEXT_SCRIPT = """
(arg) => {
    try {
        var text = arg.text;
        var url = arg.url;

        var old = document.getElementById('wa-popup');
        if (old) old.remove();

        var row = (url && window.__waRowForUrl && window.__waRowForUrl[url]) || window.__waLastClickedRow;
        if (!row || !row.isConnected) return 'no_row';

        var p = document.createElement('div');
        p.id = 'wa-popup';

        // Fechar
        var closeBtn = document.createElement('span');
        closeBtn.id = 'wa-close';
        closeBtn.textContent = 'x';
        closeBtn.style.cssText = 'position:absolute;top:-9px;right:-9px;cursor:pointer;background:#333;color:#fff;width:20px;height:20px;border-radius:50%;text-align:center;line-height:18px;font-size:13px;font-weight:bold;z-index:10;border:1px solid #555;box-shadow:0 1px 4px rgba(0,0,0,0.5);';
        closeBtn.onclick = function(){p.remove();window.__waPopupOpen=false;};
        p.appendChild(closeBtn);

        // Corpo
        var body = document.createElement('div');
        body.textContent = text;
        body.style.cssText = 'white-space:pre-wrap;word-wrap:break-word;';
        p.appendChild(body);

        // Rabeta
        var style = document.createElement('style');
        style.textContent = '#wa-popup::after{content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);border:7px solid transparent;border-top-color:#1f2c33;}';
        p.appendChild(style);

        p.style.cssText = 'position:absolute;bottom:calc(100% + 10px);left:50%;transform:translateX(-50%);max-width:380px;min-width:140px;white-space:pre-wrap;word-wrap:break-word;background:#1f2c33;color:#e9edef;padding:10px 14px;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,0.5);z-index:999;font-family:Segoe UI,sans-serif;font-size:12px;line-height:1.5;border:1px solid #333;pointer-events:auto;';

        if (window.getComputedStyle(row).position === 'static') row.style.position = 'relative';
        row.appendChild(p);
        window.__waPopupOpen = true;
        return 'ok';
    } catch(e) { return 'err:'+String(e); }
}
"""

HIDE_POPUP_SCRIPT = """
(() => {
    try {
        var p = document.getElementById('wa-popup');
        if (p) p.remove();
        window.__waPopupOpen = false;
        return 'ok';
    } catch(e) { return 'err:'+String(e); }
})();
"""


class WaTranscriber:
    def __init__(self, lang=TRANSCRIPTION_LANG):
        self.page = None
        self.playwright = None
        self.context = None
        self.model = None
        self._running = True
        self._current_chat = ""
        self._seen = set()
        self._seen_order = []
        self._audio_queue = queue.Queue()
        self._result_queue = queue.Queue()
        self._device = "cpu"
        self._seq = 0
        self._lang = lang
        self._transcriptions = []
        self._popup_showing = False
        self._url_results = {}

        TEMP_DIR.mkdir(exist_ok=True)
        if not HAS_FASTER and whisper is None:
            print("[ERRO] pip install faster-whisper")
            sys.exit(1)

    def _log(self, *args):
        print(*args)

    def _detect(self):
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda", "float16", torch.cuda.get_device_name(0)
        except Exception:
            pass
        return "cpu", "int8", None

    def load_model(self):
        dev, comp, gpu = self._detect()
        self._device = dev
        label = gpu or f"CPU {os.cpu_count()}c"
        self._log(f"[APP] Modelo {WHISPER_MODEL} | {label}")
        if HAS_FASTER:
            os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
            kw = dict(model_size_or_path=WHISPER_MODEL, device=dev, compute_type=comp)
            if dev == "cpu":
                kw["cpu_threads"] = os.cpu_count() or 4
                kw["num_workers"] = os.cpu_count() or 4
            self.model = WhisperModel(**kw)
            self._log("[APP] faster-whisper ativo")
        else:
            self.model = whisper.load_model(WHISPER_MODEL)
            self._log("[APP] openai-whisper ativo (fallback)")
        self._log("[APP] Modelo pronto!")

    def fmt_dur(self, sec):
        if sec is None:
            return ""
        s = int(sec)
        return f"{s // 60}:{s % 60:02d}"

    def _exec(self, js, arg=None):
        try:
            return self.page.evaluate(js, arg)
        except Exception:
            return None

    def start(self):
        self._log("[APP] Chrome ...")
        self.playwright = sync_playwright().start()
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR.resolve()),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True,
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.add_init_script(INJECT_SCRIPT)
        self.page.goto(WHATSAPP_URL)
        self.page.wait_for_load_state("networkidle", timeout=30000)
        try:
            self.page.wait_for_selector("canvas", timeout=10000)
            self._log("[APP] QR Code - escaneie")
        except Exception:
            pass
        try:
            self.page.wait_for_function(
                "document.querySelectorAll('canvas').length===0||"
                "document.querySelectorAll('[data-testid=\"chat-list\"]').length>0",
                timeout=120000,
            )
        except Exception:
            pass
        for p in self.context.pages:
            if 'whatsapp.com' in p.url:
                self.page = p
                break
        self._log("[APP] Conectado!")

    def transcribe(self, data):
        t0 = time.time()
        try:
            path = TEMP_DIR / f"a_{int(t0 * 1000)}.ogg"
            path.write_bytes(data)
            if HAS_FASTER:
                segs, info = self.model.transcribe(
                    str(path), language=self._lang,
                    beam_size=5, best_of=1,
                    vad_filter=(self._device == "cpu"),
                )
                text = " ".join(s.text.strip() for s in segs)
                dur = info.duration
            else:
                r = self.model.transcribe(
                    str(path), language=self._lang, fp16=False,
                    temperature=0.0, beam_size=5,
                )
                text = r["text"].strip()
                dur = r["segments"][-1]["end"] if r.get("segments") else None
            path.unlink(missing_ok=True)
            return (text or None, dur, time.time() - t0)
        except Exception as e:
            self._log(f"[ERRO] transcricao: {e}")
            return (None, None, 0)

    def _worker(self):
        while self._running:
            try:
                item = self._audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            audio, chat, seq, js_seq, blob_url = item
            text, dur, secs = self.transcribe(audio)
            dur_str = self.fmt_dur(dur)
            if text:
                self._result_queue.put((seq, chat, text, dur_str, js_seq, blob_url))
                self._log(f"[OK] #{seq} {chat[:30]}: {text[:60]}... ({secs:.1f}s)")
            else:
                self._log(f"[FALHA] #{seq} ({secs:.1f}s)")

    def _add_seen(self, key):
        if len(self._seen) >= MAX_SEEN:
            oldest = self._seen_order.pop(0)
            self._seen.discard(oldest)
        self._seen.add(key)
        self._seen_order.append(key)

    def _show_popup(self, text, blob_url=None):
        result = self._exec(SHOW_TEXT_SCRIPT, {"text": text, "url": blob_url})
        self._popup_showing = (result == 'ok')
        return self._popup_showing

    def _hide_popup(self):
        self._exec(HIDE_POPUP_SCRIPT)
        self._popup_showing = False

    def _save_transcriptions(self):
        if not self._transcriptions:
            return
        try:
            with open(EXPORT_FILE, "w", encoding="utf-8") as f:
                json.dump(self._transcriptions, f, ensure_ascii=False, indent=2)
            self._log(f"[APP] {len(self._transcriptions)} transcricoes salvas em {EXPORT_FILE}")
        except Exception as e:
            self._log(f"[ERRO] ao salvar transcricoes: {e}")

    def run(self):
        self.start()
        self.load_model()

        threading.Thread(target=self._worker, daemon=True).start()

        self._export_t = time.time()
        self._last_shown = ""

        while self._running:
            try:
                now = time.time()

                chat = self._exec(
                    "()=>{var e=document.querySelector("
                    "'header span[dir=\"auto\"],"
                    "[data-testid=\"conversation-info-header\"] span[dir=\"auto\"]');"
                    "return e?e.textContent.trim():'';}"
                )
                if chat and chat != self._current_chat:
                    self._current_chat = chat
                    self._seen.clear()
                    self._seen_order.clear()
                    self._url_results.clear()
                    self._last_shown = ""
                    self._exec("(() => { window.__waRowForUrl = {}; window.__waLastClickedRow = null; return 1; })()")
                    self._hide_popup()
                    self._log(f"[APP] Chat atual: {chat[:40]}")

                if not chat:
                    time.sleep(0.8)
                    continue

                poll_data = self._exec(POLL_SCRIPT) or {"audio": [], "clickUrl": None, "playedUrl": None}
                entries = poll_data.get("audio", [])
                click_url = poll_data.get("clickUrl")
                played_url = poll_data.get("playedUrl")

                for e in entries:
                    raw = bytes(e["d"])
                    js_seq = e.get("seq")
                    blob_url = e.get("url", "")
                    key = f"{chat}_{len(raw)}_{e.get('t',0)}"
                    if key in self._seen:
                        continue
                    self._add_seen(key)
                    self._seq += 1
                    self._audio_queue.put((raw, chat, self._seq, js_seq, blob_url))
                    self._log(f"[CLICK_CAPTURE] #{self._seq} url={blob_url[:45] if blob_url else 'sem-url'}...")

                while not self._result_queue.empty():
                    seq, chat_r, text, dur_str, js_seq, blob_url = self._result_queue.get_nowait()
                    if chat_r != self._current_chat:
                        continue
                    label = f"[{dur_str}] " if dur_str else ""
                    full_text = label + text
                    if blob_url:
                        self._url_results[blob_url] = full_text
                    entry = {
                        "seq": seq,
                        "chat": chat_r,
                        "text": text,
                        "duration": dur_str,
                        "time": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self._transcriptions.append(entry)
                    self._show_popup(full_text, blob_url)
                    self._last_shown = full_text
                    self._log(f"[POPUP] #{seq}: {text[:60]}...")

                # Replay: matching por blob URL do clique ou play()
                target_url = click_url or played_url
                if target_url and target_url in self._url_results:
                    txt = self._url_results[target_url]
                    self._show_popup(txt, target_url)
                    self._last_shown = txt
                    self._log(f"[POPUP] url-match: {txt[:60]}...")

                if now - self._export_t > 30:
                    self._export_t = now
                    self._save_transcriptions()

            except Exception as ex:
                self._log(f"[ERRO] {ex}")
                traceback.print_exc()
            time.sleep(0.75)

    def stop(self):
        self._running = False
        self._save_transcriptions()
        self._audio_queue.put(None)
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        self._log("[APP] Encerrado")


def main():
    print("WhatsApp Audio Transcriber v14.0")
    print("=" * 36)
    app = WaTranscriber()
    try:
        app.run()
    except KeyboardInterrupt:
        app.stop()


if __name__ == "__main__":
    main()
