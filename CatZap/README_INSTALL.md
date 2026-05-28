# CatZap v1.3 - Instalador Automático

## Como Instalar

1. **Download** `CatZap_v1.3_ModeloEmbutido.zip`
2. **Extraia** o ZIP para uma pasta (ex: `C:\Program Files\CatZap`)
3. **Execute** `INICIAR_CATZAP.bat` - o modelo já está embutido, não precisa internet
4. Pronto! O ícone da bandeja aparecerá na barra de tarefas

## Requisitos

- Windows 10 ou 11 (64-bit)
- Python 3.10 ou superior instalado
- 500 MB de espaço livre

## Instalação via Chrome/Edge (Manual)

Se o atalho não funcionar, instale a extensão manualmente:
1. Acesse `chrome://extensions`
2. Ative "Modo de desenvolvedor"
3. Clique em "Carregar sem compactar"
4. Selecione a pasta `cat_zap_extension` (dentro do CatZap)

## O que está incluído

- `cat_zap.py` - Servidor com modelo Whisper small embutido (~425MB)
- `models/whisper/model.bin` - Modelo de transcrição (Whisper small)
- `cat_zap_extension/` - Extensão para WhatsApp Web
- `vc_redist.x64.exe` - Dependências do Visual C++ (se necessário)
- `INICIAR_CATZAP.bat` - Script de inicialização

## Como funciona

1. O script `INICIAR_CATZAP.bat` inicia o servidor Python
2. O modelo Whisper é carregado do disco (não precisa internet)
3. WhatsApp Web é aberto automaticamente
4. A extensão detecta áudios e envia para transcrição
5. Clique em áudio para ver a transcrição em balão

## Comandos úteis

- Ctrl+Shift+H - Abrir painel de histórico
- ESC - Fechar todos os balões
- Clique no ícone da bandeja para:
  - Verificar status do servidor
  - Abrir pasta da extensão
  - Sair do programa

## Solução de problemas

**Servidor não inicia:**
- Verifique se Python está no PATH
- Execute `python --version` no CMD

**Modelo não carrega:**
- Verifique se `models/whisper/model.bin` existe (~423MB)
- Veja o log em `%APPDATA%\CatZap\erro_modelo.log`

**Bandeja não aparece:**
- Veja o log em `%APPDATA%\CatZap\erro_tray.log`

## Desinstalar

1. Feche o CatZap pela bandeja ou task manager
2. Delete a pasta CatZap
3. Delete `%APPDATA%\CatZap`

## Desenvolvedor

**Cláudio Harada**  
GitHub: https://github.com/ClaudioHaradaF/CatZap