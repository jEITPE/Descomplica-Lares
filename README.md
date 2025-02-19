# Descomplica Lares 🏠

Sistema integrado de atendimento e gestão para a imobiliária Descomplica Lares, combinando um bot inteligente de WhatsApp com um dashboard analítico.

## 📋 Sobre o Projeto

O Descomplica Lares é uma solução completa que visa automatizar e otimizar o processo de atendimento e análise de leads imobiliários. O sistema combina inteligência artificial com análise de dados para proporcionar uma experiência personalizada aos clientes e insights valiosos para a equipe de vendas.

### 🌟 Principais Funcionalidades

- **Bot Inteligente WhatsApp**
  - Atendimento automatizado 24/7
  - Coleta inteligente de informações
  - Agendamento de reuniões e visitas
  - Análise preliminar de crédito
  - Respostas personalizadas via GPT

- **Dashboard Analítico**
  - Visualização de dados em tempo real
  - Análise demográfica dos leads
  - Distribuição de renda e idade
  - Status e origem dos leads
  - Insights automáticos

## 🚀 Tecnologias Utilizadas

- **Backend**
  - Python 3.x
  - Flask
  - OpenAI GPT
  - LangChain
  - Pandas

- **Frontend**
  - HTML/CSS
  - JavaScript
  - Plotly.js

- **Integrações**
  - Twilio (WhatsApp API)
  - OpenAI API

## 💻 Pré-requisitos

- Python 3.x
- Pip (Gerenciador de pacotes Python)
- Conta Twilio com WhatsApp Business API
- Chave de API OpenAI
- Ambiente virtual Python (recomendado)

## 🔧 Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/Descomplica-Lares.git
   cd Descomplica-Lares
   ```

2. Crie e ative o ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure as variáveis de ambiente (.env):
   ```
   API_KEY_OPENAI=sua_chave_api
   ACCOUNT_SID=seu_sid_twilio
   AUTH_TOKEN=seu_token_twilio
   ```

## 🚀 Executando o Projeto

1. Ative o ambiente virtual (se ainda não estiver ativo)
2. Execute o servidor Flask:
   ```bash
   python app.py
   ```

3. Acesse o dashboard em: `http://localhost:5000/dashboard`

## 📊 Estrutura do Projeto

```
Descomplica-Lares/
├── app.py              # Aplicação principal
├── data/               # Dados e arquivos de treinamento
│   ├── csv/
│   └── treinamento_ia/
├── static/             # Arquivos estáticos
├── templates/          # Templates HTML
└── requirements.txt    # Dependências do projeto
```

## 🤖 Funcionalidades do Bot

- **Atendimento Inicial**
  - Boas-vindas personalizadas
  - Identificação de intenções
  - Respostas contextuais

- **Coleta de Informações**
  - Dados pessoais
  - Situação financeira
  - Preferências de imóveis

- **Agendamentos**
  - Reuniões online
  - Visitas presenciais
  - Análise de crédito

## 📈 Dashboard

- **Visualizações**
  - Gráficos interativos
  - Tabelas dinâmicas
  - Métricas em tempo real

- **Análises**
  - Perfil dos leads
  - Conversões
  - Tendências de mercado

## 🔒 Segurança

- Proteção de dados sensíveis
- Conformidade com LGPD
- Criptografia de informações pessoais
- Autenticação segura

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Faça um Fork do projeto
2. Crie uma Branch para sua Feature (`git checkout -b feature/AmazingFeature`)
3. Faça commit das suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Faça Push para a Branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está sob a licença [MIT](LICENSE).

## 📧 Contato

Para suporte ou dúvidas sobre o projeto, entre em contato através de [descomplicalares@gmail.com].

---
Desenvolvido com 💜 pela equipe Descomplica Lares