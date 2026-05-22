// CatZap - ISOLATED world (content script)
const SERVER = 'http://127.0.0.1:51777';
const SEEN = new Set();
const KNOWN_AUDIO = new Set(); // blob URLs confirmed as audio by inject.js
const ROW_SELECTOR = '.message-in,.message-out,[role="row"],[data-id],[class*="message"]';
let balloonEl = null;

const log = (...args) => console.log('[CatZap]', ...args);
log('Iniciando...');

// Inject page script (MAIN world) for blob access
const s = document.createElement('script');
s.src = chrome.runtime.getURL('inject.js');
s.onload = () => { log('inject.js carregado'); s.remove(); };
s.onerror = () => log('ERRO ao carregar inject.js');
document.documentElement.appendChild(s);

// --- indicator (wait for body) ---
function addIndicator() {
    if (!document.body) { setTimeout(addIndicator, 100); return; }
    const ind = document.createElement('div');
    ind.textContent = '\u{1F431}';
    Object.assign(ind.style, {
        position: 'fixed', bottom: '12px', right: '12px',
        fontSize: '20px', zIndex: '9999999', opacity: '0.5',
        pointerEvents: 'none',
    });
    document.body.appendChild(ind);
    log('Indicador adicionado, pronto!');
}
addIndicator();

// --- fetch blob via inject.js (MAIN world) ---
function fetchBlobViaInject(url) {
    return new Promise((resolve, reject) => {
        const id = Date.now() + '_' + Math.random().toString(36).slice(2, 8);
        const handler = (e) => {
            if (e.source !== window) return;
            if (e.data.type === 'CATZAP_BLOB_DATA' && e.data.id === id) {
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
        }, 15000);
    });
}

async function getAudioBytes(blobUrl) {
    try {
        const r = await fetch(blobUrl);
        if (r.ok) return new Uint8Array(await r.arrayBuffer());
    } catch(e) {}
    return fetchBlobViaInject(blobUrl);
}

// --- get ALL blob URLs in a row (not just the first) ---
function findAllBlobUrls(row) {
    if (!row || !row.querySelectorAll) return [];
    const urls = [];
    try {
        const audio = row.querySelector('audio');
        if (audio) {
            const s2 = audio.currentSrc || audio.src || '';
            if (s2.startsWith('blob:') && !urls.includes(s2)) urls.push(s2);
        }
        for (const el of row.querySelectorAll('[style*="blob:"]')) {
            const allM = [...el.getAttribute('style').matchAll(/blob:[^\s"')]+/g)];
            for (const m of allM) {
                if (!urls.includes(m[0])) urls.push(m[0]);
            }
        }
        for (const el of row.querySelectorAll('[src*="blob:"]')) {
            const s2 = el.getAttribute('src');
            if (s2 && s2.startsWith('blob:') && !urls.includes(s2)) urls.push(s2);
        }
        for (const el of row.querySelectorAll('div,span')) {
            const bg = getComputedStyle(el).backgroundImage || '';
            const allM = [...bg.matchAll(/url\(["']?(blob:[^\s"')]+)/g)];
            for (const m of allM) {
                if (!urls.includes(m[1])) urls.push(m[1]);
            }
        }
    } catch(e) {}
    return urls;
}

function isAudio(row) {
    return !!(
        row.querySelector('[data-icon="audio-play"], [data-icon="audio-pause"], audio')
        || row.querySelector('[aria-label*="audio"], [aria-label*="áudio"]')
    );
}

// --- transcrever ---
async function doTranscribe(blobUrl, row) {
    const key = blobUrl.slice(0, 50);
    if (SEEN.has(key)) { log('Ja transcrito:', key); return; }
    SEEN.add(key);
    log('doTranscribe chamado. blobUrl:', blobUrl);
    log('Row tem body.contains:', document.body.contains(row));
    try {
        log('getAudioBytes...');
        const bytes = await getAudioBytes(blobUrl);
        log('getAudioBytes retornou:', bytes ? bytes.byteLength + ' bytes' : 'null');
        if (!bytes || bytes.length === 0) { log('Audio vazio'); return; }
        log('Fetch p/ servidor...');
        const tx = await fetch(SERVER + '/transcribe', {
            method: 'POST',
            headers: {'Content-Type': 'audio/ogg', 'X-Lang': 'pt'},
            body: bytes,
            signal: AbortSignal.timeout(180000),
        });
        log('Resposta servidor status:', tx.status);
        const data = await tx.json();
        log('Resposta servidor data:', data);
        if (data.text && !data.text.startsWith('[ERRO]')) {
            log('Transcricao OK:', data.text);
            showBalloon(row, data.text);
        } else {
            log('Erro na transcricao:', data.text);
            showBalloon(row, data.text || '');
        }
    } catch (e) {
        log('Excecao em doTranscribe:', e.name, e.message);
        if (e.name === 'TimeoutError')
            showBalloon(row, '\u23F3 Transcricao demorou demais');
        else if ((e.message || '').includes('Failed to fetch'))
            showBalloon(row, '\u{1F63F} Servidor CatZap offline?');
        else
            showBalloon(row, '\u{1F63F} ' + (e.message || ''));
    }
}

// --- balloon ---
function showBalloon(row, text) {
    if (balloonEl) { balloonEl.remove(); balloonEl = null; }
    balloonEl = document.createElement('div');
    balloonEl._row = row;
    const st = balloonEl.style;
    st.position = 'fixed'; st.zIndex = '99999999';
    st.background = '#fff5f7'; st.border = '2px solid #e8a0b0';
    st.borderRadius = '12px'; st.padding = '10px 14px';
    st.fontSize = '13px'; st.color = '#333';
    st.boxShadow = '0 2px 12px rgba(0,0,0,0.12)';
    st.maxWidth = '360px'; st.fontFamily = 'Segoe UI, sans-serif';
    st.whiteSpace = 'pre-wrap'; st.wordBreak = 'break-word';
    st.pointerEvents = 'auto';
    balloonEl.innerHTML = '\u{1F431} ' + text.replace(/</g, '&lt;');
    const closeBtn = document.createElement('span');
    closeBtn.textContent = ' \u2715';
    Object.assign(closeBtn.style, {
        cursor: 'pointer', fontSize: '12px', color: '#c08090',
        marginLeft: '6px', pointerEvents: 'auto',
    });
    closeBtn.onclick = () => { balloonEl.remove(); balloonEl = null; };
    balloonEl.appendChild(closeBtn);
    document.body.appendChild(balloonEl);
    positionBalloon(row);
}

function positionBalloon(row) {
    if (!balloonEl || !row || !document.body.contains(row)) return;
    const rect = row.getBoundingClientRect();
    if (rect.width === 0) return;
    const bH = balloonEl.offsetHeight || 60;
    let top = rect.top - bH - 6;
    if (top < 4) top = rect.bottom + 6;
    let left = rect.left;
    if (left + balloonEl.offsetWidth > window.innerWidth - 10)
        left = window.innerWidth - balloonEl.offsetWidth - 10;
    if (left < 4) left = 4;
    balloonEl.style.top = top + 'px';
    balloonEl.style.left = left + 'px';
}

// --- listen for NEW audio blobs from inject.js ---
window.addEventListener('message', (e) => {
    if (e.source !== window) return;
    if (e.data.type === 'CATZAP_NEW_BLOB') {
        const url = e.data.url;
        if (KNOWN_AUDIO.has(url)) return;
        KNOWN_AUDIO.add(url);
        log('Audio blob registrado:', url.slice(0, 60));
    }
});

// --- scan (fallback — audio blobs usually not in DOM) ---
let _lastScan = 0;

function scanRows() {
    const now = Date.now();
    if (now - _lastScan < 800) return;
    _lastScan = now;
    const rows = document.querySelectorAll(ROW_SELECTOR);
    for (const row of rows) {
        if (!isAudio(row)) continue;
        const urls = findAllBlobUrls(row);
        const audioUrl = urls.find(u => KNOWN_AUDIO.has(u));
        if (!audioUrl) continue;
        const key = audioUrl.slice(0, 50);
        if (SEEN.has(key)) continue;
        log('Scan: audio KNOWN detectado');
        doTranscribe(audioUrl, row);
    }
}

// --- click handler (debug only) ---
document.addEventListener('click', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    const targetDesc = tag + (e.target.id ? '#' + e.target.id : '') + (e.target.className ? '.' + (typeof e.target.className === 'string' ? e.target.className.slice(0, 20) : '') : '');
    log('CLICK', targetDesc);
}, true);

// --- MutationObserver ---
// --- detect audio play via data-icon change (MAIN detection mechanism) ---
new MutationObserver((mutations) => {
    for (const m of mutations) {
        if (m.type === 'attributes' && m.attributeName === 'data-icon') {
            const icon = m.target.getAttribute('data-icon');
            if (icon === 'audio-pause') {
                const row = m.target.closest(ROW_SELECTOR);
                if (!row) { log('MO: data-icon row not found'); continue; }
                if (!isAudio(row)) { log('MO: data-icon row not audio'); continue; }
                const audioEl = row.querySelector('audio');
                const src = audioEl ? (audioEl.currentSrc || audioEl.src || '') : '';
                if (!src.startsWith('blob:')) {
                    setTimeout(() => {
                        const a2 = row.querySelector('audio');
                        const s2 = a2 ? (a2.currentSrc || a2.src || '') : '';
                        if (s2.startsWith('blob:') && KNOWN_AUDIO.has(s2)) {
                            log('MO: data-icon blob on retry');
                            doTranscribe(s2, row);
                        }
                    }, 300);
                    continue;
                }
                if (KNOWN_AUDIO.has(src)) {
                    log('MO: data-icon play');
                    doTranscribe(src, row);
                }
            }
        }
    }
}).observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ['data-icon'] });

// --- fallback observers (audio added, src/style changes) ---
new MutationObserver((mutations) => {
    for (const m of mutations) {
        for (const node of m.addedNodes) {
            if (node.tagName === 'AUDIO' || node.tagName === 'VIDEO') {
                const src = node.currentSrc || node.src || '';
                if (src.startsWith('blob:')) {
                    if (!KNOWN_AUDIO.has(src)) continue;
                    const row = node.closest(ROW_SELECTOR);
                    if (row) { log('MO: audio element added'); doTranscribe(src, row); }
                }
            }
        }
        if (m.type === 'attributes' && m.attributeName === 'src') {
            const src = m.target.getAttribute('src') || '';
            if (src.startsWith('blob:') && KNOWN_AUDIO.has(src)) {
                const row = m.target.closest(ROW_SELECTOR);
                if (row) { log('MO: src blob'); doTranscribe(src, row); }
            }
        }
        if (m.type === 'attributes' && m.attributeName === 'style') {
            const style = m.target.getAttribute('style') || '';
            const blobInStyle = [...style.matchAll(/blob:[^\s"')]+/g)];
            for (const bm of blobInStyle) {
                if (KNOWN_AUDIO.has(bm[0])) {
                    const row = m.target.closest(ROW_SELECTOR);
                    if (row) { log('MO: style blob'); doTranscribe(bm[0], row); }
                    break;
                }
            }
        }
    }
}).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['src', 'style'] });

// --- periodic scan ---
setInterval(scanRows, 2000);

// --- scroll ---
document.addEventListener('scroll', () => {
    if (balloonEl && balloonEl._row && document.body.contains(balloonEl._row))
        positionBalloon(balloonEl._row);
}, true);
