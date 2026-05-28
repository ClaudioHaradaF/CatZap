# CHANGELOG - CatZap v1.4

## [1.4] - 2026-05-28

### Corrigido
- **PyInstaller bug crítico**: servidor não respondia na porta 51777 em executável frozen
  - Causa raiz: `ThreadingHTTPServer` falha silenciosamente em executáveis empacotados
  - Solução: substituído por `HTTPServer` (síncrono) com thread dedicada
- Modelo carrega corretamente de `sys._MEIPASS/models/whisper` no modo frozen
- Bootloader crash (STATUS_STACK_BUFFER_OVERRUN) ao incluir `hiddenimports` no .spec
  - Solução: remover hiddenimports, deixar PyInstaller detectar automaticamente

### Adicionado
- Extensão Chrome/Edge incluída automaticamente no executável
- Script `INICIAR_CATZAP.bat` para o diretório de distribuição
- Documentação em português (`LEIA-ME.txt`) incluída no pacote
- Pacote zip de distribuição `CatZap_v1.4.zip`

### Melhorado
- Build otimizado: EXE de 41 MB + pasta `_internal/` (~1.7 GB) em modo one-folder
- Console mantido visível para debug do carregamento do modelo

## [1.3] - 2025-01-27

### Adicionado
- Modelo Whisper embutido (~425MB) - funciona offline sem necessidade de download
- Script `INICIAR_CATZAP.bat` para execução simplificada (basta clicar)
- Priorização de caminho do modelo: WHISPER_CACHE_DIR > models/whisper > _internal/models/whisper
- Documentação de instalação para usuários não-técnicos

### Corrigido
- Spellchecker import com try/catch para evitar crash em ambientes sem hunspell
- Logging de erros na bandeja com retry exponencial (3 tentativas)

### Conhecido (v1.3)
- ~~Executável PyInstaller falha silenciosamente~~ ✅ **Resolvido na v1.4**
- Retornado para int8 (CPU) ao invés de float16 por causa de incompatibilidade de hardware

## Arquivos Principais
- `CatZap_v1.4.zip` - Pacote de distribuição (extrair e executar)
- `CatZap\cat_zap.py` - Servidor com modelo integrado
- `CatZap\dist\CatZap_v1.4\INICIAR_CATZAP.bat` - Launcher automático