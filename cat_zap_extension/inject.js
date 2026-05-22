(function() {
    if (window.__catZapLoaded) return;
    window.__catZapLoaded = true;

    const blobMap = {};
    const origCreate = URL.createObjectURL;
    URL.createObjectURL = function(blob) {
        const url = origCreate.call(this, blob);
        if (blob.type && blob.type.startsWith('audio/')) {
            blobMap[url] = blob;
            window.postMessage({ type: 'CATZAP_NEW_BLOB', url, id: url }, '*');
        }
        return url;
    };

    window.__catZapGetBlob = async function(url) {
        const blob = blobMap[url];
        if (blob) return await blob.arrayBuffer();
        try {
            const r = await fetch(url);
            return await r.arrayBuffer();
        } catch(e) {
            return null;
        }
    };

    // Also discover blobs already in the DOM (older messages loaded before inject.js)
    function discoverExistingBlobs() {
        document.querySelectorAll('audio[src*="blob:"], audio[currentSrc*="blob:"]').forEach(a => {
            const s = a.currentSrc || a.src || '';
            if (s.startsWith('blob:') && !blobMap[s]) {
                blobMap[s] = null;
                window.postMessage({ type: 'CATZAP_NEW_BLOB', url: s, id: s }, '*');
            }
        });
    }
    setTimeout(discoverExistingBlobs, 500);

    // Listen for requests from content script
    window.addEventListener('message', async (e) => {
        if (e.data.type !== 'CATZAP_GET_BLOB') return;
        const { url, id } = e.data;
        let data = null;
        try {
            data = await window.__catZapGetBlob(url);
        } catch(e) {}
        window.postMessage({ type: 'CATZAP_BLOB_DATA', id, data }, '*');
    });
})();
