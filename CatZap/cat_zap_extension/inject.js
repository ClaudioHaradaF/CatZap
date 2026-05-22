(() => {
    if (window.__catZapLoaded) return;
    window.__catZapLoaded = true;

    const BLOB_MAX = 50;
    const blobMap = {};
    const blobKeys = [];

    const blobMapSet = (url, blob) => {
        if (blobMap[url]) return;
        blobMap[url] = blob;
        blobKeys.push(url);
        if (blobKeys.length > BLOB_MAX) {
            const old = blobKeys.shift();
            delete blobMap[old];
        }
    };

    const blobMapRemove = (url) => {
        delete blobMap[url];
        const idx = blobKeys.indexOf(url);
        if (idx >= 0) blobKeys.splice(idx, 1);
    };

    const origCreate = URL.createObjectURL;
    URL.createObjectURL = (blob) => {
        const url = origCreate.call(this, blob);
        const t = blob.type || '';
        if (t.startsWith('audio/') || t === 'application/octet-stream' || t === '') {
            blobMapSet(url, blob);
            window.postMessage({ type: 'CATZAP_NEW_BLOB', url, id: url }, '*');
        }
        return url;
    };

    const origRevoke = URL.revokeObjectURL;
    URL.revokeObjectURL = (url) => {
        blobMapRemove(url);
        return origRevoke.call(this, url);
    };

    window.__catZapGetBlob = async (url) => {
        const blob = blobMap[url];
        if (blob) return await blob.arrayBuffer();
        try {
            const r = await fetch(url);
            return await r.arrayBuffer();
        } catch {
            return null;
        }
    };

    const waitForChat = (retries = 0) => {
        if (retries > 30) return;
        if (!document.querySelector('#main')) {
            setTimeout(() => waitForChat(retries + 1), 500);
            return;
        }
        setTimeout(discoverExistingBlobs, 2000);
    };

    const discoverExistingBlobs = () => {
        document.querySelectorAll('audio[src*="blob:"], audio[currentSrc*="blob:"]').forEach((a) => {
            const s = a.currentSrc || a.src || '';
            if (s.startsWith('blob:') && !blobMap[s]) {
                blobMapSet(s, null);
                window.postMessage({ type: 'CATZAP_NEW_BLOB', url: s, id: s }, '*');
            }
        });
    };

    waitForChat();

    window.addEventListener('message', (e) => {
        if (e.data?.type !== 'CATZAP_GET_BLOB') return;
        const { url, id } = e.data;
        (async () => {
            let data = null;
            try {
                data = await window.__catZapGetBlob(url);
            } catch {}
            window.postMessage({ type: 'CATZAP_BLOB_DATA', id, data }, '*');
        })();
    });

    // Click tracking — capture the row at the moment of click
    let _lastClickedRow = null;
    document.addEventListener('click', (e) => {
        _lastClickedRow = e.target.closest('.message-in,.message-out,[data-id]');
    }, true);

    // Detect audio.play() — use click tracking first, then scan DOM
    const origPlay = HTMLAudioElement.prototype.play;
    HTMLAudioElement.prototype.play = function () {
        const src = this.currentSrc || this.src || '';
        if (src.startsWith('blob:')) {
            let foundId = _lastClickedRow ? (_lastClickedRow.getAttribute('data-id') || '') : '';
            if (!foundId) {
                try {
                    const allRows = document.querySelectorAll('.message-in,.message-out,[data-id]');
                    const prefix = src.slice(0, 50);
                    for (const row of allRows) {
                        if (row.innerHTML.includes(prefix)) {
                            foundId = row.getAttribute('data-id') || '';
                            break;
                        }
                    }
                } catch {}
            }
            window.postMessage({
                type: 'CATZAP_AUDIO_PLAY',
                url: src,
                dataId: foundId
            }, '*');
        }
        return origPlay.apply(this, arguments);
    };

    window.postMessage({ type: 'CATZAP_READY' }, '*');
})();
