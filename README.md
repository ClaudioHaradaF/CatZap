# CatZap - WhatsApp Audio Transcriber

Aplicação para transcrição automática de áudios do WhatsApp Web usando tecnologia de reconhecimento de fala (Whisper).

## 📋 Funcionalidades

- Transcrição em tempo real de áudios do WhatsApp Web
- Interface discreta com balões de transcrição na tela
- Suporte para múltiplos idiomas via modelo Whisper
- Inicialização automática com o Windows
- Instalador único que configura tudo automaticamente
- Extensão do navegador para integração perfeita com WhatsApp Web

## 🏗️ Arquitetura

Consulte o documento detalhado de arquitetura em [CatZap/anchored_summary.md](CatZap/anchored_summary.md)

### Componentes Principais

1. **Servidor (cat_zap.py)**:
   - Baseado em Whisper para transcrição
   - Endpoints /transcribe e /log
   - Executa invisivelmente na bandeja do sistema

2. **Extensão do Navegador**:
   - inject.js: Intercepta áudios e eventos de clique
   - content.js: Exibe balões de transcrição e gerencia comunicação
   - Comunica via postMessage e chrome.runtime

3. **Instalador (CatZap_Setup.exe)**:
   - Criado com Inno Setup
   - Instala servidor e extensão
   - Configura atalho na área de trabalho
   - Adiciona inicialização automática
   - Instala dependências VC++ Redistribuível

## 🚀 Instalação

### Opção 1: Distribuição com Modelo Embutido (Recomendado)
1. Baixe `CatZap_v1.3_ModeloEmbutido.zip` da [seção de releases](#-releases)
2. Extraia o ZIP para uma pasta (ex: `C:\Program Files\CatZap`)
3. Execute `INICIAR_CATZAP.bat` - o modelo já está embutido, não precisa internet
4. Pronto! A extensão será carregada automaticamente

### Opção 2: Instalação Manual (Desenvolvedores)
1. Clone o repositório:
   `ash
   git clone https://github.com/ClaudioHaradaF/CatZap.git
   `
2. Instale as dependências:
   `ash
   pip install -r CatZap/requirements_transcriber.txt
   `
3. Execute o servidor:
   `ash
   python CatZap/cat_zap.py
   `
4. Carregue a extensão em CatZap/cat_zap_extension/ no modo desenvolvedor do Chrome/Edge
5. Acesse https://web.whatsapp.com

## 💡 Uso

Após a instalação:
1. Use o atalho da área de trabalho para abrir o WhatsApp Web
2. Navigue normalmente até uma conversa com áudios
3. Clique em play em qualquer áudio
4. Um balão com a transcrição aparecerá próximo à mensagem
5. Configure o comportamento dos balões (modo Auto/Manter) pelo ícone no canto inferior direito

## 🔨 Construindo a partir do Fonte

### Pré-requisitos
- Python 3.8+
- Inno Setup 6 (para o instalador)
- PyInstaller
- Conta GitHub com acesso ao repositório

### Passos
1. Clone o repositório
2. Instale dependências de desenvolvimento:
   `ash
   pip install pyinstaller
   `
3. Gere o executável do servidor:
   `ash
   pyinstaller --onefile --windowed CatZap/cat_zap.py
   `
4. O executável será criado em dist/cat_zap.exe
5. Use o script CatZap/CatZap_Setup.iss com Inno Setup para criar o instalador completo

## 📦 Releases

A versão mais recente está disponível como:
- **CatZap_Setup.exe** (~275 MB): Instalador completo
- **CatZap_old.exe** (~253 MB): Executável do servidor apenas (para testes)

Acesse a [página de releases](https://github.com/ClaudioHaradaF/CatZap/releases) para downloads.

## 🤝 Contribuindo

1. Fork o repositório
2. Crie uma branch para sua feature (git checkout -b feature/AmazingFeature)
3. Faça commit das alterações (git commit -m 'Add some AmazingFeature')
4. Push para a branch (git push origin feature/AmazingFeature)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 🙏 Agradecimentos

- [OpenAI Whisper](https://github.com/openai/whisper) pela tecnologia de transcrição
- Comunidade de desenvolvedores de extensões para navegador
- Usuários beta que testaram e forneceram feedback valioso

---
*Documentação gerada automaticamente e mantida pela equipe de desenvolvimento.*
