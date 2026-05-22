// CatZap - ISOLATED world (content script)
const SERVER = 'http://127.0.0.1:51777';
const SEEN = new Set();
const KNOWN_AUDIO = new Set();
const PENDING_TX = new Set();
const BALLOON_MAP = {};
let INJECT_READY = false;
const PENDING_QUEUE = [];
let _lastScan = 0;
let _lastAudioPlayRow = null;
let _lastAudioPlayDataId = '';
let BALLOON_MODE = 'keep';
const ROW_SELECTOR = '.message-in,.message-out,[data-id]';

const cacheRow = (row) => {
    if (!row) return;
    _lastAudioPlayRow = row;
    _lastAudioPlayDataId = row.getAttribute('data-id') || '';
};

const resolveRow = (row) => {
    if (row && document.body.contains(row)) return row;
    if (_lastAudioPlayDataId) {
        const fresh = document.querySelector(`[data-id="${_lastAudioPlayDataId}"]`);
        if (fresh) return fresh;
    }
    if (_lastAudioPlayRow && document.body.contains(_lastAudioPlayRow)) return _lastAudioPlayRow;
    return null;
};

// --- debug panel ---
let LOG_BUFFER = [];
const MAX_LOG = 100;

const logToServer = (msg) => {
    try { fetch(`${SERVER}/log`, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: msg, signal: AbortSignal.timeout(1000) }).catch(() => {}); } catch {}
};

const log = (...args) => {
    const text = args.map(a => typeof a === 'string' ? a : (() => { try { return JSON.stringify(a); } catch { return String(a); } })()).join(' ');
    const time = new Date().toLocaleTimeString();
    const entry = `[${time}] ${text}`;
    console.log('[CatZap]', ...args);
    logToServer(entry);
    LOG_BUFFER.push(entry);
    if (LOG_BUFFER.length > MAX_LOG) LOG_BUFFER.shift();
    const el = document.getElementById('catZapDebug');
    if (el && el.style.display !== 'none') {
        const body = el.querySelector('.cd-body');
        if (body) {
            const line = document.createElement('div');
            line.textContent = entry;
            body.appendChild(line);
            body.scrollTop = body.scrollHeight;
        }
    }
};

const createDebugPanel = () => {
    if (document.getElementById('catZapDebug')) return;
    const el = document.createElement('div');
    el.id = 'catZapDebug';
    el.style.cssText = 'display:none;position:fixed;bottom:40px;right:12px;width:520px;height:320px;background:rgba(0,0,0,0.85);border:1px solid #555;border-radius:8px;z-index:999999999;font-family:Consolas,monospace;font-size:11px;color:#eee;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.5)';
    el.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;background:#333;border-bottom:1px solid #555;font-size:12px;user-select:none"><span>\u{1F431} CatZap Debug</span><div><button class="cd-copy" style="background:#555;color:#fff;border:none;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:11px">\u{1F4CB} Copiar</button><button class="cd-clear" style="background:#555;color:#fff;border:none;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:11px">\u{1F5D1}</button><button class="cd-close" style="background:#555;color:#fff;border:none;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:11px">\u2715</button></div></div><div class="cd-body" style="padding:4px 8px;overflow-y:auto;height:calc(100% - 30px);white-space:pre-wrap;word-break:break-all"></div>';
    el.querySelector('.cd-copy').onclick = () => {
        navigator.clipboard.writeText(LOG_BUFFER.join('\n')).catch(() => {});
    };
    el.querySelector('.cd-clear').onclick = () => {
        LOG_BUFFER.length = 0;
        const body = el.querySelector('.cd-body');
        if (body) body.innerHTML = '';
    };
    el.querySelector('.cd-close').onclick = () => {
        el.style.display = 'none';
    };
    document.body.appendChild(el);
};

const toggleDebug = () => {
    let el = document.getElementById('catZapDebug');
    if (!el) {
        createDebugPanel();
        el = document.getElementById('catZapDebug');
    }
    if (el.style.display === 'none') {
        el.style.display = 'block';
        const body = el.querySelector('.cd-body');
        if (body) {
            body.innerHTML = '';
            for (const entry of LOG_BUFFER) {
                const line = document.createElement('div');
                line.textContent = entry;
                body.appendChild(line);
            }
            body.scrollTop = body.scrollHeight;
        }
    } else {
        el.style.display = 'none';
    }
};

document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.shiftKey && (e.key === 'Z' || e.key === 'z')) {
        e.preventDefault();
        toggleDebug();
    }
});

log('v1.1 debug panel iniciando...');

// --- model status polling ---
let _modelReady = false;
let _modelError = '';
const _MODEL_CHECKED = { ready: false };

const checkModelStatus = async () => {
    try {
        const r = await fetch(`${SERVER}/model-status`, { signal: AbortSignal.timeout(5000) });
        const data = await r.json();
        _MODEL_CHECKED.ready = data.ready;
        _modelReady = data.ready;
        _modelError = data.error || '';
    } catch {
        _MODEL_CHECKED.ready = false;
        _modelError = 'Servidor offline';
    }
};
// Check immediately and every 10s
checkModelStatus();
setInterval(checkModelStatus, 10000);

// --- inject MAIN world script ---
const s = document.createElement('script');
s.src = chrome.runtime.getURL('inject.js');
s.onload = () => { log('inject.js carregado'); s.remove(); };
s.onerror = () => log('ERRO ao carregar inject.js');
document.documentElement.appendChild(s);

// --- balloon mode toggle ---
const saveBalloonMode = (mode) => {
    try { chrome.storage.local.set({ catzap_balloon_mode: mode }); } catch {}
};

const loadBalloonMode = () => {
    try {
        chrome.storage.local.get('catzap_balloon_mode', (r) => {
            if (r.catzap_balloon_mode) BALLOON_MODE = r.catzap_balloon_mode;
            updateToggleBtn();
        });
    } catch {}
};

const toggleBalloonMode = () => {
    BALLOON_MODE = BALLOON_MODE === 'keep' ? 'auto' : 'keep';
    saveBalloonMode(BALLOON_MODE);
    updateToggleBtn();
    if (BALLOON_MODE === 'auto') clearAllBalloons();
    log('Modo balao:', BALLOON_MODE === 'keep' ? 'Manter' : 'Auto-limpar');
};

const clearAllBalloons = () => {
    for (const key in BALLOON_MAP) {
        BALLOON_MAP[key].remove();
    }
    for (const key in BALLOON_MAP) {
        delete BALLOON_MAP[key];
    }
};

let _toggleBtn = null;
const updateToggleBtn = () => {
    if (!_toggleBtn) return;
    const isKeep = BALLOON_MODE === 'keep';
    _toggleBtn.textContent = isKeep ? '\u{1F4CC} Manter' : '\u{1F504} Auto';
    _toggleBtn.title = isKeep ? 'Balões fixos (clique para auto-limpar)' : 'Auto-limpar balões (clique para manter)';
};

// --- indicator ---
const addIndicator = () => {
    if (!document.body) { setTimeout(addIndicator, 100); return; }
    const container = document.createElement('div');
    Object.assign(container.style, {
        position: 'fixed', bottom: '12px', right: '12px',
        zIndex: '9999999', display: 'flex', gap: '6px', alignItems: 'center',
    });
    const ind = document.createElement('div');
    ind.textContent = '\u{1F431}';
    Object.assign(ind.style, {
        fontSize: '20px', opacity: '0.5',
        pointerEvents: 'auto', cursor: 'pointer',
    });
    ind.title = 'CatZap Debug (Ctrl+Shift+Z)';
    ind.onclick = toggleDebug;
    container.appendChild(ind);
    _toggleBtn = document.createElement('button');
    Object.assign(_toggleBtn.style, {
        background: 'rgba(0,0,0,0.6)', color: '#eee', border: '1px solid #555',
        borderRadius: '4px', padding: '2px 6px', fontSize: '11px',
        cursor: 'pointer', fontFamily: 'Segoe UI, sans-serif',
        whiteSpace: 'nowrap',
    });
    _toggleBtn.onclick = toggleBalloonMode;
    container.appendChild(_toggleBtn);
    document.body.appendChild(container);
    updateToggleBtn();
    loadBalloonMode();
    log('Indicador adicionado');
};
addIndicator();

// --- handshake with inject.js ---
window.addEventListener('message', (e) => {
    if (e.source !== window) return;
    if (e.data?.type === 'CATZAP_READY') {
        INJECT_READY = true;
        log('Handshake: inject.js pronto');
        for (const item of PENDING_QUEUE) {
            doTranscribe(item.blobUrl, item.row);
        }
        PENDING_QUEUE.length = 0;
    }
});

// --- blob requests via inject.js (MAIN world) ---
const fetchBlobViaInject = (url) => new Promise((resolve, reject) => {
    const id = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const handler = (e) => {
        if (e.source !== window) return;
        if (e.data?.type === 'CATZAP_BLOB_DATA' && e.data.id === id) {
            window.removeEventListener('message', handler);
            if (e.data.data) resolve(new Uint8Array(e.data.data));
            else reject(new Error('blob vazio'));
        }
    };
    window.addEventListener('message', handler);
    window.postMessage({ type: 'CATZAP_GET_BLOB', url, id }, '*');
    setTimeout(() => {
        window.removeEventListener('message', handler);
        reject(new Error('timeout'));
    }, 8000);
});

const getAudioBytes = async (blobUrl) => {
    if (INJECT_READY) {
        try {
            const bytes = await fetchBlobViaInject(blobUrl);
            if (bytes?.length > 0) return bytes;
        } catch (e) {
            log('Inject blob fallback:', e.message);
        }
    }
    try {
        const r = await fetch(blobUrl);
        if (r.ok) return new Uint8Array(await r.arrayBuffer());
    } catch {}
    return null;
};

// --- blob URLs in a row (lightweight) ---
const findAllBlobUrls = (row) => {
    if (!row?.querySelectorAll) return [];
    const urls = [];
    const seen = {};
    try {
        const audio = row.querySelector('audio');
        if (audio) {
            const s = audio.currentSrc || audio.src || '';
            if (s.startsWith('blob:') && !seen[s]) { seen[s] = true; urls.push(s); }
        }
        let els = row.querySelectorAll('[style*="blob:"]');
        for (const el of els) {
            const st = el.getAttribute('style');
            if (!st) continue;
            const matches = st.match(/blob:[^\s"')]+/g);
            if (!matches) continue;
            for (const m of matches) {
                if (!seen[m]) { seen[m] = true; urls.push(m); }
            }
        }
        els = row.querySelectorAll('[src*="blob:"]');
        for (const el of els) {
            const src = el.getAttribute('src');
            if (src?.startsWith('blob:') && !seen[src]) { seen[src] = true; urls.push(src); }
        }
    } catch {}
    return urls;
};

// --- is audio message? ---
const isAudio = (row) => {
    if (row.querySelector('audio')) return true;
    if (row.querySelector('[data-icon="audio-play"], [data-icon="audio-pause"]')) return true;
    if (row.querySelector('[data-testid="audio-play"], [data-testid="audio-pause"]')) return true;
    // Check if row contains any known blob URL (audio waveform image, etc.)
    try {
        const all = row.querySelectorAll('[style*="blob:"], [src*="blob:"]');
        for (const el of all) {
            const attr = el.getAttribute('style') || el.getAttribute('src') || '';
            const blobs = attr.match(/blob:[^\s"')]+/g);
            if (blobs && blobs.some(b => KNOWN_AUDIO.has(b))) return true;
        }
    } catch {}
    return false;
};

// --- transcribe ---
const doTranscribe = async (blobUrl, row) => {
    const key = blobUrl.slice(0, 50);
    if (SEEN.has(key)) { log('Ja transcrito:', key); return; }

    if (PENDING_TX.has(key)) return;
    PENDING_TX.add(key);

    if (!INJECT_READY) {
        PENDING_QUEUE.push({ blobUrl, row });
        return;
    }

    // Check if model is ready
    if (!_modelReady) {
        const msg = _modelError ? `\u{1F63F} ${_modelError}` : '\u23F3 Baixando modelo Whisper... (primeira vez leva minutos)';
        log('Modelo nao pronto:', msg);
        showBalloon(row, msg);
        PENDING_TX.delete(key);
        // Retry in 15s
        setTimeout(() => {
            if (!SEEN.has(key)) doTranscribe(blobUrl, row);
        }, 15000);
        return;
    }

    SEEN.add(key);

    log('Transcrevendo:', key);
    try {
        const bytes = await getAudioBytes(blobUrl);
        if (!bytes?.length) { log('Audio vazio'); return; }
        const tx = await fetch(`${SERVER}/transcribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/octet-stream', 'X-Lang': 'pt' },
            body: bytes,
            signal: AbortSignal.timeout(60000),
        });
        const data = await tx.json();
        if (data.text && !data.text.startsWith('[ERRO]')) {
            log('OK:', data.text);
            showBalloon(row, data.text);
        } else {
            log('Erro no servidor:', data.text);
            let display = data.text || '';
            if (display.includes('Modelo nao carregado')) display = '\u{1F63F} Modelo Whisper nao carregou. Verifique o servidor.';
            showBalloon(row, display);
        }
    } catch (e) {
        log('Excecao:', e.name, e.message);
        let msg = `\u{1F63F} ${e.message || ''}`;
        if (e.name === 'TimeoutError') msg = '\u23F3 Transcricao demorou demais';
        else if ((e.message || '').includes('Failed to fetch')) msg = '\u{1F63F} Servidor CatZap offline?';
        showBalloon(row, msg);
    } finally {
        PENDING_TX.delete(key);
    }
};

// --- balloons (one per row) ---
const balloonKey = (row) => row.getAttribute('data-id') || `row_${Math.random().toString(36).slice(2, 8)}`;

const showBalloon = (row, text) => {
    row = resolveRow(row);
    if (BALLOON_MODE === 'auto') clearAllBalloons();
    const key = balloonKey(row);
    const old = BALLOON_MAP[key];
    if (old) { old.remove(); delete BALLOON_MAP[key]; }

    const el = document.createElement('div');
    el._row = row;
    el._key = key;
    const st = el.style;
    st.position = 'fixed'; st.zIndex = '99999999';
    st.background = '#fff5f7'; st.border = '2px solid #e8a0b0';
    st.borderRadius = '12px'; st.padding = '10px 14px';
    st.fontSize = '13px'; st.color = '#333';
    st.boxShadow = '0 2px 12px rgba(0,0,0,0.12)';
    st.maxWidth = '360px'; st.fontFamily = 'Segoe UI, sans-serif';
    st.whiteSpace = 'pre-wrap'; st.wordBreak = 'break-word';
    st.pointerEvents = 'auto';
    el.innerHTML = `\u{1F431} ${text.replace(/</g, '&lt;')}`;

    const closeBtn = document.createElement('span');
    closeBtn.textContent = ' \u2715';
    Object.assign(closeBtn.style, {
        cursor: 'pointer', fontSize: '12px', color: '#c08090',
        marginLeft: '6px', pointerEvents: 'auto',
    });
    closeBtn.onclick = () => { el.remove(); delete BALLOON_MAP[el._key]; };
    el.appendChild(closeBtn);

    document.body.appendChild(el);
    positionBalloon(el, row);
    BALLOON_MAP[key] = el;
};

const positionBalloon = (el, row) => {
    if (!el) return;
    if (!row || !document.body.contains(row)) {
        el.style.top = `${Math.max(4, window.innerHeight - (el.offsetHeight || 80) - 20)}px`;
        el.style.left = `${Math.max(4, (window.innerWidth - (el.offsetWidth || 360)) / 2)}px`;
        return;
    }
    const rect = row.getBoundingClientRect();
    if (rect.width === 0) return;
    const bH = el.offsetHeight || 60;
    let top = rect.top - bH - 6;
    if (top < 4) top = rect.bottom + 6;
    let left = rect.left;
    if (left + el.offsetWidth > window.innerWidth - 10)
        left = window.innerWidth - el.offsetWidth - 10;
    if (left < 4) left = 4;
    el.style.top = `${top}px`;
    el.style.left = `${left}px`;
};

// --- listen for messages from inject.js ---
window.addEventListener('message', (e) => {
    if (e.source !== window) return;
    const { type, url } = e.data || {};

    if (type === 'CATZAP_NEW_BLOB') {
        if (KNOWN_AUDIO.has(url)) return;
        KNOWN_AUDIO.add(url);
        log('Blob registrado:', url.slice(0, 60));
        return;
    }

    if (type === 'CATZAP_AUDIO_PLAY') {
        const dataId = e.data.dataId;
        log('Audio.play detectado:', url.slice(0, 60), dataId ? `row=${dataId.slice(0, 30)}` : '(sem row)');
        if (!KNOWN_AUDIO.has(url)) {
            KNOWN_AUDIO.add(url);
        }
        if (dataId) {
            const row = document.querySelector(`[data-id="${dataId}"]`);
            if (row) {
                doTranscribe(url, row);
                return;
            }
        }
        // Fallback: scan all rows for this blob
        const rows = document.querySelectorAll(ROW_SELECTOR);
        const prefix = url.slice(0, 50);
        for (const row of rows) {
            const urls = findAllBlobUrls(row);
            if (urls.includes(url)) {
                doTranscribe(url, row);
                return;
            }
        }
        // Fallback 2: scan rows by innerHTML prefix match
        for (const row of rows) {
            if (row.innerHTML.includes(prefix)) {
                log('Fallback: innerHTML match');
                doTranscribe(url, row);
                return;
            }
        }
        // Final fallback: use last row from data-icon mutation observer
        if (_lastAudioPlayRow && document.body.contains(_lastAudioPlayRow)) {
            log('Fallback: usando row cacheada do MO');
            doTranscribe(url, _lastAudioPlayRow);
            _lastAudioPlayRow = null;
            return;
        }
        log('Fallback: sem row disponivel');
    }
});

// --- scan ---
const scanRows = () => {
    const now = Date.now();
    if (now - _lastScan < 800) return;
    _lastScan = now;
    const rows = document.querySelectorAll(ROW_SELECTOR);
    for (const row of rows) {
        if (!isAudio(row)) continue;
        const urls = findAllBlobUrls(row);
        const audioUrl = urls.find((u) => KNOWN_AUDIO.has(u));
        if (!audioUrl) continue;
        if (SEEN.has(audioUrl.slice(0, 50))) continue;
        log('Scan: audio detectado');
        doTranscribe(audioUrl, row);
    }
};

// --- click (debug + row fallback) ---
document.addEventListener('click', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    const cls = typeof e.target.className === 'string' ? e.target.className.slice(0, 30) : '';
    log('CLICK', `${tag}${e.target.id ? '#' + e.target.id : ''}${cls ? '.' + cls : ''}`);
    // DIAG: full DOM path of the click target
    const path = (e.composedPath ? e.composedPath().slice(0, 15).map(el => {
        if (el === document) return 'document';
        if (el === window) return 'window';
        const t = (el.tagName || '').toLowerCase();
        const c = typeof el.className === 'string' ? el.className.slice(0, 50) : '';
        const id = el.getAttribute ? (el.getAttribute('data-id') || '') : '';
        const icon = el.getAttribute ? (el.getAttribute('data-icon') || '') : '';
        const testid = el.getAttribute ? (el.getAttribute('data-testid') || '') : '';
        const extras = [];
        if (id) extras.push(`data-id="${id.slice(0, 25)}"`);
        if (icon) extras.push(`data-icon="${icon}"`);
        if (testid) extras.push(`data-testid="${testid}"`);
        return `${t}${c ? '.' + c.replace(/\s+/g, '.').slice(0, 80) : ''}${extras.length ? '[' + extras.join(' ') + ']' : ''}`;
    }).join(' > ') : 'SEM PATH');
    log('PATH:', path.substring(0, 500));
    // Try to find the row
    const row = e.target.closest(ROW_SELECTOR);
    log('ROW:', row ? `row[data-id="${(row.getAttribute('data-id') || '').slice(0, 25)}"]` : 'null');
    if (row) {
        cacheRow(row);
    }
}, true);

// --- try transcribe a row given a blob URL ---
const tryTranscribe = (blobUrl, row) => {
    if (!KNOWN_AUDIO.has(blobUrl)) return false;
    if (SEEN.has(blobUrl.slice(0, 50))) return true;
    log('transcrevendo:', blobUrl.slice(0, 50));
    doTranscribe(blobUrl, row);
    return true;
};

// --- scan a row for ANY blob URL known ---
const scanRowForKnownBlob = (row) => {
    const urls = findAllBlobUrls(row);
    for (const u of urls) {
        if (KNOWN_AUDIO.has(u)) {
            tryTranscribe(u, row);
            return true;
        }
    }
    return false;
};

// --- MAIN detection: watch ALL attribute changes for blob URLs ---
new MutationObserver((mutations) => {
    for (const m of mutations) {
        if (m.type !== 'attributes') continue;
        const t = m.target;
        const val = t.getAttribute(m.attributeName) || '';
        // Check if the changed attribute contains a known blob URL
        if (val.includes('blob:') || m.attributeName === 'src' || m.attributeName === 'currentSrc') {
            const blobUrls = val.match(/blob:[^\s"')]+/g);
            if (blobUrls) {
                for (const bu of blobUrls) {
                    if (KNOWN_AUDIO.has(bu)) {
                        const row = t.closest(ROW_SELECTOR) || t;
                        log('MO attr:', m.attributeName, '=' + val.slice(0, 50));
                        doTranscribe(bu, row);
                    }
                }
            }
        }
        // Also detect data-icon / data-testid audio patterns
        const icon = m.attributeName === 'data-icon' ? val : '';
        const testid = m.attributeName === 'data-testid' ? val : '';
        if ((icon === 'audio-play' || icon === 'audio-pause' || testid === 'audio-play' || testid === 'audio-pause')) {
            const row = t.closest(ROW_SELECTOR);
            if (!row) { log('MO: row not found for', m.attributeName, val); return; }
            cacheRow(row);
            if (!scanRowForKnownBlob(row)) {
                setTimeout(() => scanRowForKnownBlob(row), 500);
            }
        }
    }
}).observe(document.documentElement, { subtree: true, attributes: true });

// --- fallback: detect new audio elements in DOM ---
new MutationObserver((mutations) => {
    for (const m of mutations) {
        if (m.type !== 'childList') continue;
        for (const node of m.addedNodes) {
            if (node.nodeType !== 1) continue;
            const audio = node.tagName === 'AUDIO' ? node : node.querySelector('audio');
            if (!audio) continue;
            const src = audio.currentSrc || audio.src || '';
            if (!src.startsWith('blob:')) continue;
            if (!KNOWN_AUDIO.has(src)) continue;
            const row = audio.closest(ROW_SELECTOR);
            if (!row) continue;
            log('MO: audio element added');
            doTranscribe(src, row);
        }
    }
}).observe(document.documentElement, { childList: true, subtree: true });

// --- periodic scan ---
setInterval(scanRows, 2000);

// --- scroll reposition ---
document.addEventListener('scroll', () => {
    for (const key in BALLOON_MAP) {
        const el = BALLOON_MAP[key];
        const row = resolveRow(el?._row);
        if (row) positionBalloon(el, row);
    }
}, true);

// --- clear balloons on conversation switch ---
let _lastConvTitle = document.title;

const clearBalloonsOnNav = () => {
    const t = document.title;
    if (t && t !== _lastConvTitle) {
        _lastConvTitle = t;
        clearAllBalloons();
        log('Conversa trocada, baloes limpos');
    }
};

setInterval(clearBalloonsOnNav, 800);
// Also detect URL changes (hash or pushState)
window.addEventListener('hashchange', clearBalloonsOnNav);
window.addEventListener('popstate', clearBalloonsOnNav);
