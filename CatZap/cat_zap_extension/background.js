// CatZap - Service Worker (background)
const SERVER = 'http://127.0.0.1:51777';
let healthCache = { status: 'unknown', lastCheck: 0 };

const checkHealth = async () => {
    try {
        const r = await fetch(`${SERVER}/health`, { signal: AbortSignal.timeout(5000) });
        const data = await r.json();
        healthCache = { status: 'online', data, lastCheck: Date.now() };
    } catch {
        healthCache = { status: 'offline', lastCheck: Date.now() };
    }
    try {
        await chrome.storage.local.set({ catzap_server: healthCache });
    } catch {}
};

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'CATZAP_PING') {
        if (Date.now() - healthCache.lastCheck > 15000) {
            checkHealth().then(() => sendResponse(healthCache));
            return true;
        }
        sendResponse(healthCache);
    }
});

// Periodic health check
checkHealth();
setInterval(checkHealth, 30000);
