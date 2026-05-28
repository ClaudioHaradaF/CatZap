# Relatório de Bugs - CatZap v1.4

## Bug 1: Executável PyInstaller não inicia servidor

**Severidade:** Crítico  
**Status:** ✅ Resolvido (v1.4)  
**Componente:** `cat_zap.py` (empacotado)

### Descrição
Quando executado via executável PyInstaller (`CatZap_v1.3.exe`), o processo aparecia no Task Manager mas o servidor nunca respondia na porta 51777.

### Causa raiz
`ThreadingHTTPServer` falha silenciosamente em executáveis frozen do PyInstaller. O binding da porta nunca acontece, mas o processo continua vivo. Substituído por `HTTPServer` síncrono rodando em uma thread dedicada.

### Solução aplicada
1. ✅ `ThreadingHTTPServer` → `HTTPServer` (linha 10)
2. ✅ Model search path: `sys._MEIPASS` → `models/whisper` (linhas 17-34)
3. ✅ Modelos incluídos via `datas=[('models', 'models')]` no .spec
4. ✅ `exclude_binaries=True` no EXE para build one-folder (EXE 41MB + _internal/)
5. ✅ Sem `hiddenimports` no .spec (causavam STATUS_STACK_BUFFER_OVERRUN)
6. ✅ Console mantido como `True` para debug

### Verificação
- Servidor responde em `http://127.0.0.1:51777/health`
- Modelo carrega e fica pronto (~2 min em CPU int8)
- `{"status":"ok","model_loaded":true,"model_ready":true,"faster_whisper":true}` confirmado
- Extensão incluída em `_internal/cat_zap_extension/`
- Executável funcional em instalação limpa (sem hiddenimports)

---

## Bug 2: Compute type float16 incompatível com CPU

**Severidade:** Médio  
**Status:** Resolvido (workaround)  
**Componente:** `cat_zap.py:235`

### Descrição
O erro "Requested float16 compute type, but the target device or backend do not support efficient float16 computation" ocorre em CPUs sem suporte AVX ou CUDA.

### Erro
```
Requested float16 compute type, but the target device or backend do not support efficient float16 computation
```

### Solução aplicada
Revertido de `["float16", "int8"]` para `["int8"]` apenas. Compromete qualidade mas garante compatibilidade.

---

## Bug 3: Spellchecker import falha

**Severidade:** Baixo  
**Status:** Resolvido  
**Componente:** `cat_zap.py:29-40`

### Descrição
Import de `hunspell` e `spellchecker` falha em ambientes sem as bibliotecas instaladas.

### Solução
Adicionado try/catch com import condicional e logging de erro.

---

## Bug 4: Bandeja do sistema falha silenciosa

**Severidade:** Médio  
**Status:** Parcialmente resolvido  
**Componente:** `cat_zap.py:414-490`

### Descrição
A bandeja do sistema (`pystray`) falha em alguns Windows sem ícones ou com conflitos de DPI.

### Sintomas
- Nenhum ícone aparece na bandeja
- Servidor funciona mas sem interface de controle

### Solução parcial
Adicionado retry com exponential backoff (3 tentativas) e logging em `erro_tray.log`.

---

## Bug 5: Bootloader crash com hiddenimports no .spec

**Severidade:** Crítico  
**Status:** ✅ Resolvido (v1.4)  
**Componente:** `CatZap_standalone.spec`

### Descrição
Ao incluir `hiddenimports` no .spec do PyInstaller, o executável crasha imediatamente com `STATUS_STACK_BUFFER_OVERRUN` (exit code -1073740791).

### Causa raiz
`hiddenimports` força o PyInstaller a analisar módulos que podem ter dependências conflitantes ou DLLs incompatíveis. O bootloader falha ao tentar carregar o archive com esses módulos incluídos.

### Solução
Remover todos os `hiddenimports` do .spec. PyInstaller detecta automaticamente todas as dependências necessárias pela análise do código fonte.

### Verificação
- Build sem hiddenimports funciona perfeitamente
- Todas as imports do código (`faster_whisper`, `spellchecker`, `PIL`, etc.) são detectadas automaticamente

---

## Sumário de versões

| Versão | Tamanho | Tipo | Status |
|--------|---------|------|--------|
| CatZap_v1.4.zip | ~1.74 GB | Pasta PyInstaller + docs | ✅ **Pronto para distribuição** |
| CatZap_v1.3_ModeloEmbutido.zip | 425 MB | ZIP funcional (legado) | ✅ Testado |
| CatZap_v1.3.exe (legado) | ~690 MB | PyInstaller (antigo) | ❌ Substituído |

## Recomendação
Distribuir `CatZap_v1.4.zip` contendo:
- `CatZap_v1.4.exe` (41 MB) - Servidor
- `_internal/` (~1.7 GB) - Dependências + modelo + extensão
- `INICIAR_CATZAP.bat` - Launcher
- `LEIA-ME.txt` - Instruções