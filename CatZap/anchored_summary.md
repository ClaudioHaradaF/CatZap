# CatZap — Anchored Summary

## Arquitetura

| Componente | Mundo | Papel |
|---|---|---|
| `inject.js` | MAIN | Intercepta `URL.createObjectURL` (captura blobs de áudio), monkey-patch `HTMLAudioElement.prototype.play` (detecta play + click tracking), atende requisições de blob via `postMessage` |
| `content.js` | ISOLATED | Handle de mensagens (`CATZAP_NEW_BLOB`, `CATZAP_AUDIO_PLAY`), transcrição via servidor local, exibição de balloons com fallback de posição, MutationObservers, log para terminal via `/log` |
| `cat_zap.py` | Servidor | Whisper + endpoint `/transcribe` + endpoint `/log` + auto-hide console via `ctypes` |

## O Problema Raiz

O `<audio>` do WhatsApp NÃO está dentro de `.message-in,.message-out` no DOM moderno. Por isso `closest(ROW_SELECTOR)` falha.

## Como o Row é Encontrado

### No inject.js (momento do play)
1. **Click tracking**: listener `click` guarda `e.target.closest(ROW_SELECTOR)` em `_lastClickedRow`
2. **Scan DOM** (fallback): varre todas as rows por `row.innerHTML.includes(prefix_do_blob)`

### No content.js (handler CATZAP_AUDIO_PLAY)
1. `dataId` do inject.js → `querySelector`
2. `findAllBlobUrls(row)` → atributos src/style
3. `row.innerHTML.includes(prefix)` → varredura textual
4. `_lastAudioPlayRow` → cache do MutationObserver

## Balões (Balloon)

| Situação | Comportamento |
|---|---|
| Row existe | Posicionado relativo à row |
| Row removida pelo React | Centro inferior da tela |
| Modo "Manter" (📌) | Balões acumulam |
| Modo "Auto" (🔄) | Balão anterior some ao tocar novo áudio |

Toggle no canto inferior direito (ao lado do 🐱). Estado persiste via `chrome.storage.local`.

## Terminal Invisível

- `_hide_console()` esconde a janela via `ctypes` após o startup
- Servidor roda em bandeja (tray icon) — só o 🐱 aparece
- Usuário final nunca vê CMD

## Empacotamento

### `CatZap_Setup.exe` (Inno Setup)

O instalador único que o usuário final recebe:

| Ação | Detalhe |
|---|---|
| Instala servidor | `C:\Program Files\CatZap\CatZap.exe` |
| Instala extensão | `C:\Program Files\CatZap\extension\` |
| Detecta Chrome/Edge | Cria atalho na área de trabalho |
| Atalho | Abre o navegador com `--load-extension` direto no WhatsApp |
| Inicialização | Adiciona `CatZap.exe` ao `HKCU\Run` (sobe com Windows) |
| VC++ Redist | Instala automaticamente se necessário |
| Primeira execução | Marcador `.installed` criado — servidor sobe invisível direto |

### Fluxo do usuário leigo

```
1. Recebe CatZap_Setup.exe (via WhatsApp, Drive, pendrive)
2. Duplo clique → Next, Next, Finish
3. Atalho "CatZap - WhatsApp" aparece na área de trabalho
4. Clica no atalho → Chrome abre no WhatsApp
5. Clica play no áudio → transcrição aparece
6. Nunca mais precisa fazer nada (servidor sobe com Windows)
```

## Arquivos Entregues

| Arquivo | Tamanho | Função |
|---|---|---|
| `CatZap_Setup.exe` | ~275 MB | Instalador único |
| `CatZap.exe` | ~253 MB | Servidor compilado (PyInstaller) |
| `cat_zap.py` | — | Código fonte do servidor |
| `cat_zap_extension/` | — | Extensão Chrome/Edge |
