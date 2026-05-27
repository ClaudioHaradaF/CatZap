# Testes Automatizados CatZap

Este diretório contém testes automatizados para o servidor CatZap.

## Como Executar

```bash
cd CatZap
python test_catzap.py
```

## Testes Disponíveis

| Teste | Descrição |
|-------|-----------|
| test_01_health_check | Verifica endpoint /health |
| test_02_model_status | Verifica endpoint /model-status |
| test_03_history_endpoint | Verifica endpoint /history (novo) |
| test_04_transcribe_endpoint_structure | Verifica estrutura do /transcribe |
| test_05_delete_history | Verifica DELETE /history (novo) |

## Pré-requisitos

```bash
pip install -r requirements_test.txt
```

## Novas Funcionalidades Testadas

- **Endpoint /history** - Retorna lista de transcrições
- **DELETE /history** - Limpa histórico de transcrições
- **duration_secs** - Retornado na transcrição