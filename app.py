import os
import csv
import logging
import pandas as pd
import plotly.graph_objects as go
from flask import Flask, render_template, jsonify, request
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, request, redirect, url_for
from twilio.rest import Client 
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv
import markdown
from bs4 import BeautifulSoup
from time import sleep
from apscheduler.schedulers.background import BackgroundScheduler
import time
import re
import os
import csv
import json
import logging
from questionnaire_ai import QuestionnaireAI
import random
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go
import json
from openai import OpenAI
from flask import render_template

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

account_sid = os.getenv("ACCOUNT_SID")
auth_token = os.getenv("AUTH_TOKEN")
client = Client(account_sid, auth_token)

template_eat = os.getenv("CONTENT_ID_EAT")
template_pe = os.getenv("CONTENT_ID_PE")
template_iap = os.getenv("CONTENT_ID_IAP")
template_loop = os.getenv("CONTENT_ID_LOOP")
template_3anos = os.getenv("CONTENT_ID_3")
template_autonomo_registrado = os.getenv("CONTENT_ID_AR")
template_filhos = os.getenv("CONTENT_ID_FILHOS")

api_key = os.getenv("API_KEY_OPENAI")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

lola_md = os.path.join(BASE_DIR, 'data', 'treinamento_ia', 'lola.md')
lola_json = os.path.join(BASE_DIR, 'data', 'treinamento_ia', 'lola.json')
csv_file = os.path.join(BASE_DIR, 'data', 'csv', 'customers.csv')

# Configuração do Langchain
llm = ChatOpenAI(
    model="gpt-3.5-turbo",     # Modelo GPT-3.5-turbo
    max_tokens=130,
    temperature=0.2,            # Mantém respostas previsíveis
    openai_api_key=api_key
)

# Função para carregar e processar o arquivo Markdown
def carregar_markdown(markdown_path):
    try:
        with open(markdown_path, 'r', encoding='utf-8') as f:
            html = markdown.markdown(f.read())
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()
            print(f"Markdown carregado com sucesso:\n{text}")  # Debug
            return text
    except Exception as e:
        print(f"Erro ao carregar o markdown: {e}")
        return ""

# Caminho para o arquivo Markdown
try:
    markdown_instrucoes = carregar_markdown(lola_md) if 'lola_md' in globals() else None
except Exception as e:
    logger.warning(f"Erro ao carregar markdown: {e}")
    markdown_instrucoes = None

# Carregar JSON
def carregar_json(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Erro ao carregar configurações: {e}")
        return {}

# Caminho para o arquivo JSON
try:
    configuracoes = carregar_json(lola_json) if 'lola_json' in globals() else None
except Exception as e:
    logger.warning(f"Erro ao carregar JSON: {e}")
    configuracoes = None

# Prompt para Lola
prompt_lola = PromptTemplate(
    input_variables=["message", "markdown_instrucoes", "configuracoes", "historico"],
    template="""
    Você é a Lola, assistente virtual da imobiliária Descomplica Lares. 
    Você tem uma abordagem simples e clara. Textos muito grande não agradam os seus clientes, então seja o mais direta possível.
    Responda somente com base nas instruções fornecidas. Se a pergunta for fora do escopo, diga algo como: 
    "Mil perdões, eu não tenho certeza da resposta! 😓\nSe precisar marcar uma conversa com um corretor, digite *atendimento*"

    Sempre respostas curtas e diretas! Nunca responda algo que você não tem conhecimento, algo que você não foi treinada pra dizer,
    ou algo que não tenha nada haver com a Imobiliária em si!

    - Se o cliente disser algo como "obrigado", "valeu", "entendi", "blz" ou "agradecido", responda com algo como "De nada! Se precisar de algo mais, estarei aqui. 😊"
    - Se o cliente disser algo como "ok", "entendido" ou "finalizar", responda com algo como "Certo! Estarei por aqui caso precise. Até logo! 👋"."
    - Nunca invente informações ou forneça respostas fora do escopo da imobiliária.
    - Seja educada e simpática, mas sempre clara e objetiva.

    Não se refira ao cliente, só responda às suas perguntas.

    ### Exemplos de perguntas que você pode responder:
    1. "Quais os documentos que eu preciso para dar entrada?" (Responda com a lista de documentos necessária).
    2. "Onde vocês se localizam?" (Responda com o endereço fornecido).
    3. "Vocês trabalham com imóveis comerciais?" (Responda que a imobiliária trabalha apenas com residências).
    4. "O endereço de vocês é o mesmo que está no catálogo?" (Responda algo como: "Sim, nosso endereço é o mesmo do catálogo: Rua Padre Antonio, 365.")

    ### Restrições:
    - Nunca invente informações.
    - Nunca forneça dados não incluídos nas instruções do markdown.
    - Nunca interfirá quando a mensagem do cliente for sobre:
        - Marcar uma reunião. "Gostaria de marcar uma reunião" "Como posso marcar uma reunião?"
        - Marcar uma visita. "Acho melhor marcar uma visita para conhecer o local e os empreendimentos!" "Quero agendar uma visita" "Como posso marcar uma visita"
        - Querer comprar ou dar entrada algum apartamento ou empreendimento. "Quero dar entrada/comprar em um apartamento"

        
    ### Histórico de mensagens:
    1. Se o cliente perguntar algo já mencionado anteriormente, responda reforçando as informações do {historico}. 
    2. Se o cliente fizer referência a uma pergunta anterior, revise o {historico} e, se aplicável, conecte a resposta com o que já foi discutido. 
    3. Caso o cliente peça um resumo, gere um resumo curto com base no {historico} fornecido.
    4. Sempre verifique se as instruções fornecidas no markdown têm prioridade sobre o {historico}, e só utilize o {historico} como suporte adicional. 
    5. Nunca forneça informações que não estão nas instruções ou no {historico}.
    6. Se o histórico tiver sido reiniciado, e o cliente voltar, ou algo desse tipo, responda com: "Desculpe, mas não tenho um histórico recente da nossa conversa. Posso te ajudar com alguma dúvida específica? 😊"
    
         
    Use emojis, para dar o sentimento de simpatia!

    ### Instruções carregadas:
    {markdown_instrucoes}

    ### Exemplos de respostas para perguntas:
    {configuracoes}

    ### Mensagem do cliente:
    Cliente: {message}

    ### Histórico de mensagens:
    {historico}

    Responda as perguntas normalmente, sem 'Lola:'.
    """
)
conversation_chain = LLMChain(llm=llm, prompt=prompt_lola)

# Prompt para Rubens
prompt_rubens = PromptTemplate(
    input_variables=["message"],
    template="""
    Você é um assistente especializado chamado Rubens. Sua única função é detectar intenções relacionadas a:
    - Marcar uma reunião. "Gostaria de marcar uma reunião" "Como posso marcar uma reunião?"
    - Marcar uma visita. "Acho melhor marcar uma visita para conhecer o local e os empreendimentos!" "Quero agendar uma visita" "Como posso marcar uma visita"
    - Querer saber como ser aprovado e o processo de aprovação do crédito e demais. 
    - Querer comprar ou dar entrada algum apartamento ou empreendimento. "Queria saber como dar entrada em um apartamento". 
    - Análise de crédito, envio de documentos, documentos em mãos. Querer ver quanto de crédito tem na Caixa.
    - Se o cliente apenas digitar: "atendimento".

    Responda com "PASS_BUTTON" se identificar alguma dessas intenções na mensagem.
    Caso contrário, responda com "CONTINUE".

    Exemplos que você não deve interferir:
    "Quais os documentos que eu preciso?" 
    "Onde vocês se localizam?"
    "Vocês trabalham com imóveis comerciais ou só residenciais?"
    "O que é preciso para fazer uma simulação de financiamento?"
    "Como vocês trabalham?"

    ### Mensagem do cliente:
    Cliente: {message}
    """
)
intention_chain = LLMChain(llm=llm, prompt=prompt_rubens)

# Prompt Fallback
prompt_fallback = PromptTemplate(
    input_variables=["message", "markdown_instrucoes", "configuracoes", "historico", "current_stage", "last_question"],
    template="""
    Você é um assistente que identifica quando um cliente desvia do fluxo principal do questionário.
    
    Estado atual do cliente: {current_stage}
    Última pergunta feita ao cliente: {last_question}

    REGRAS ESTRITAS:
    1. Se o cliente estiver em qualquer etapa do questionário, analise se a mensagem é uma resposta à última pergunta feita
    2. Se a mensagem parecer ser uma resposta à pergunta anterior, responda com "CONTINUE_FLOW"
    3. Se for uma nova pergunta ou dúvida, responda com "FALLBACK"

    EXEMPLOS DE ANÁLISE:
    - Se última pergunta foi sobre idade e cliente responde com números = CONTINUE_FLOW
    - Se última pergunta foi sobre CPF e cliente faz uma pergunta = FALLBACK
    - Se cliente responde algo totalmente fora do contexto = FALLBACK

    QUANDO INTERVIR (FALLBACK):
    - Perguntas urgentes sobre o processo
    - Dúvidas que podem impedir o cliente de continuar
    - Mensagens que claramente não são respostas à pergunta atual
    - Sempre que tiver dúvidas, perguntar ao cliente se ele quer continuar o questionario
    - Sempre que tiver interrogação na mensagem

    QUANDO NÃO INTERVIR (CONTINUE_FLOW):
    - Respostas que parecem corresponder à pergunta atual
    - Números quando perguntado sobre idade
    - Formato de CPF quando perguntado sobre CPF
    - Respostas simples como "sim", "não" quando apropriado
    - Respostas que parecem corresponder à pergunta atual
    - Respostas validas para perguntas do questionario
    - Respostas de estado civil
    - Registrado ou Autonomo
    - Quando falar de renda bruta
    - Quando falar um Nome
    - Quando falar um número que é valida pra ser uma idade de alguém


    ### Mensagem do cliente:
    {message}

    ### Histórico recente:
    {historico}

    Responda apenas com "FALLBACK" ou "CONTINUE_FLOW".
    """
)
fallback_chain = LLMChain(llm=llm, prompt=prompt_fallback)

# Mapeamento dos IDs dos botões
BUTTON_IDS = {
    "infos_descomplica": "informações",
    "marcar_reuniao": "marcar reunião",
    "agendar_visita": "agendar visita",
    "analise_credito": "análise de crédito"
}

# Inicializando o estado do cliente
cliente_estado = {}

# Inicializando o Histórico da IA
historico_clientes = {}

# Inicializando o tracking de última pergunta
ultima_pergunta = {}

# Inicializando o estado de confirmação
aguardando_confirmacao = {}

# Tempo limite para expiração do histórico
TEMPO_EXPIRACAO = 1800

# Agendador para verificar inatividade
scheduler = BackgroundScheduler()

# Função para verificar clientes inativos
def verificar_inatividade():
    tempo_atual = time.time()
    for numero, dados in list(historico_clientes.items()):
        if tempo_atual - dados["ultima_interacao"] > TEMPO_EXPIRACAO:
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=numero,
                body="Seu atendimento foi finalizado! 😪\nCaso queira retomar o contato, *basta enviar uma nova mensagem.*"
            )
            del historico_clientes[numero]

# Inicia o agendador
scheduler.add_job(verificar_inatividade, 'interval', seconds=1800)
scheduler.start()

def salvar_resposta(estado_cliente, campo, valor):
    if "respostas" not in estado_cliente:
        estado_cliente["respostas"] = {}
    estado_cliente["respostas"][campo] = valor

def validar_horario(horario):
    # Verifica apenas se o horário termina com '5'
    return horario.strip()[-1] == "5"

# Função para salvar as respostas no CSV
def salvar_no_csv(estado_cliente):
    file_path = csv_file
    headers = ["nome", "idade", "cpf", "carteira_assinada", "estado_civil", 
             "trabalho", "restricao_cpf", "filhos_menores", "renda_bruta", "dia", "horario"]

    data = {
        "nome": estado_cliente["respostas"].get("nome", ""),
        "idade": estado_cliente["respostas"].get("idade", ""),
        "cpf": estado_cliente["respostas"].get("cpf", ""),
        "carteira_assinada": estado_cliente["respostas"].get("carteira_assinada", ""),
        "estado_civil": estado_cliente["respostas"].get("estado_civil", ""),
        "trabalho": estado_cliente["respostas"].get("trabalho", ""),
        "restricao_cpf": estado_cliente["respostas"].get("restricao_cpf", ""),
        "filhos_menores": estado_cliente["respostas"].get("filhos_menores", ""),
        "renda_bruta": estado_cliente["respostas"].get("renda_bruta", ""),
        "dia": estado_cliente["respostas"].get("dia", ""),
        "horario": estado_cliente["respostas"].get("horario", "")
    }

    # Verificar se o arquivo já existe
    file_exists = os.path.isfile(file_path)

    # Salvar no arquivo CSV
    with open(file_path, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        if not file_exists:
            writer.writeheader()  # Escreve o cabeçalho se o arquivo for novo
        writer.writerow(data)

def validar_informacao(campo, valor):
    """
    Valida o valor baseado no campo.
    Retorna True se for válido, ou False e uma mensagem de erro caso contrário.
    """
    if campo == "nome":
        if len(valor.split()) < 2:
            return False, "O nome deve conter pelo menos dois nomes (nome e sobrenome)."
    elif campo == "cpf":
        if not re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", valor):
            return False, "O CPF deve estar no formato correto: XXX.XXX.XXX-XX."
    elif campo == "idade":
        if not valor.isdigit():
            return False, "A idade deve ser um número inteiro válido."
    elif campo == "renda_bruta":
        try:
            renda = float(valor.replace("R$", "").replace(",", "").strip())
            if renda <= 0:
                return False, "A renda bruta deve ser um valor numérico positivo."
        except ValueError:
            return False, "A renda bruta deve ser um valor numérico válido _(Ex: 4500,00)_."

    return True, None

def validar_todas_respostas(respostas):
    erros = []
    for campo, valor in respostas.items():
        valido, erro = validar_informacao(campo, valor)
        if not valido:
            erros.append({"campo": campo, "erro": erro})
    return len(erros) == 0, erros

def is_questionnaire_response(message, stage):
    """
    Verifica se a mensagem parece ser uma resposta ao questionário
    """
    questionnaire_stages = {
        "questionario_reuniao_nome": lambda m: len(m.split()) >= 2,
        "questionario_reuniao_idade": lambda m: m.replace(" ", "").isdigit(),
        "questionario_reuniao_cpf": lambda m: bool(re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", m)),
        # Adicione outras validações conforme necessário
    }
    
    if stage in questionnaire_stages:
        return questionnaire_stages[stage](message)
    return False

class ConversationContext:
    def __init__(self):
        self.context = {
            "last_questions": [],
            "pending_information": set(),
            "critical_points": set(),
            "interaction_count": 0
        }
    
    def add_interaction(self, message, is_question=False):
        self.interaction_count += 1
        if is_question:
            self.last_questions.append(message)
            if len(self.last_questions) > 3:
                self.last_questions.pop(0)

    def should_intervene(self, message, current_stage):
        # Lógica para decidir se deve intervir baseado no contexto
        if current_stage.startswith("questionario_"):
            return False
        return True

# Uso no código principal:
conversation_contexts = {}

def execute_with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(1)  # Espera 1 segundo antes de tentar novamente

def fazer_pergunta(from_whatsapp_number, pergunta, etapa):
    """
    Função auxiliar para fazer perguntas e registrar no histórico
    """
    ultima_pergunta[from_whatsapp_number] = pergunta
    cliente_estado[from_whatsapp_number]["etapa"] = etapa
    client.messages.create(
        from_='whatsapp:+14155238886',
        to=from_whatsapp_number,
        body=pergunta
    )

# Inicialização da QuestionnaireAI
questionnaire = QuestionnaireAI(
    api_key=api_key, 
    csv_file_path=csv_file,
    markdown_path=lola_md,
    json_path=lola_json
)

# Dicionário para armazenar respostas do questionário
questionario_respostas = {}

def process_questionnaire_step(from_whatsapp_number, incoming_msg, current_field, historico, tipo_questionario="reuniao"):
    """
    Função helper para processar cada etapa do questionário
    """
    result = questionnaire.process_message(incoming_msg, current_field, historico)
    estado_cliente = cliente_estado[from_whatsapp_number]
    
    if result["type"] == "fallback":
        # Salva o estado atual para retornar depois
        aguardando_confirmacao[from_whatsapp_number] = {
            "etapa": estado_cliente["etapa"],
            "tipo_questionario": tipo_questionario,
            "current_field": current_field,
            "ultima_pergunta": questionnaire.questions[current_field]["pergunta"]
        }
        
        # Trata o fallback
        client.messages.create(
            from_='whatsapp:+14155238886',
            to=from_whatsapp_number,
            body=result["message"]  # Usa a resposta da base de conhecimento
        )
        sleep(1.5)
        client.messages.create(
            from_='whatsapp:+14155238886',
            to=from_whatsapp_number,
            body="Posso continuar com as perguntas do formulário? 😊\n*(Responda com Sim ou Não)*"
        )
        estado_cliente["etapa"] = "aguardando_confirmacao_fallback"
        return "OK", 200
    
    elif result["type"] == "error":
        # Trata erro de validação
        client.messages.create(
            from_='whatsapp:+14155238886',
            to=from_whatsapp_number,
            body=result["message"]
        )
        client.messages.create(
            from_='whatsapp:+14155238886',
            to=from_whatsapp_number,
            body=questionnaire.questions[current_field]["pergunta"]
        )
        return "OK", 200
    
    # Sucesso - salva resposta e pega próxima pergunta
    if from_whatsapp_number not in questionario_respostas:
        questionario_respostas[from_whatsapp_number] = {}
    questionario_respostas[from_whatsapp_number][result["field"]] = result["value"]
    
    next_question = questionnaire.get_next_question(current_field, tipo_questionario)
    if next_question:
        if next_question.get("template_id"):
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=globals()[next_question["template_id"]]
            )
        else:
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body=next_question["question"]
            )
        estado_cliente["etapa"] = f"questionario_{tipo_questionario}_{next_question['field']}"
    else:
        # Finaliza o questionário
        questionnaire.save_to_csv(questionario_respostas[from_whatsapp_number])
        client.messages.create(
            from_='whatsapp:+14155238886',
            to=from_whatsapp_number,
            body="Obrigado pelas informações, a Descomplica agradece! 🧡💜"
        )
        estado_cliente["etapa"] = f"finalizado_{tipo_questionario}"
    
    return "OK", 200

def load_data():
    try:
        logger.info("Iniciando carregamento de dados")
        file_path = os.path.join('data', 'treinamento_ia', 'csv', 'costumers.csv')
        
        # Definir os nomes das colunas
        column_names = ['Nome', 'Idade', 'CPF', 'Experiência > 3 anos', 'Estado Civil', 
                       'Tipo de Trabalho', 'Motivo', 'Filhos Menores', 'Renda Mensal', 
                       'Unnamed1', 'Unnamed2']
        
        try:
            df = pd.read_csv(file_path, encoding='latin1', names=column_names, header=None)
        except:
            df = pd.read_csv(file_path, encoding='utf-8', names=column_names, header=None)
        
        # Remover colunas não utilizadas
        df = df.drop(['Unnamed1', 'Unnamed2', 'CPF', 'Motivo'], axis=1)
        
        # Limpar e converter dados
        df['Idade'] = pd.to_numeric(df['Idade'], errors='coerce')
        df['Renda Mensal'] = df['Renda Mensal'].str.replace('.', '').str.replace(',', '.').astype(float)
        
        logger.info(f"Dados carregados com sucesso. Shape: {df.shape}")
        logger.info(f"Colunas: {df.columns.tolist()}")
        logger.info(f"Primeiras linhas:\n{df.head()}")
        
        return df
        
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {str(e)}")
        return pd.DataFrame()

def generate_insights(df):
    try:
        logger.info("Iniciando geração de insights")
        insights = "<ul class='insights-list'>"
        
        # Insight sobre idade
        idade_media = df['Idade'].mean()
        idade_min = df['Idade'].min()
        idade_max = df['Idade'].max()
        insights += f"<li><strong>Faixa Etária:</strong> A idade média dos leads é {idade_media:.1f} anos, variando de {idade_min:.0f} a {idade_max:.0f} anos.</li>"
        
        # Insight sobre renda
        renda_media = df['Renda Mensal'].mean()
        renda_min = df['Renda Mensal'].min()
        renda_max = df['Renda Mensal'].max()
        insights += f"<li><strong>Perfil Financeiro:</strong> A renda média mensal é R$ {renda_media:,.2f}, com valores entre R$ {renda_min:,.2f} e R$ {renda_max:,.2f}.</li>"
        
        # Insight sobre tipo de trabalho
        trabalho_counts = df['Tipo de Trabalho'].value_counts()
        tipo_mais_comum = trabalho_counts.index[0]
        percentual_tipo = (trabalho_counts[0] / len(df)) * 100
        insights += f"<li><strong>Situação Profissional:</strong> {percentual_tipo:.1f}% dos leads são {tipo_mais_comum}.</li>"
        
        # Insight sobre filhos
        tem_filhos = (df['Filhos Menores'].str.lower() == 'sim').mean() * 100
        insights += f"<li><strong>Estrutura Familiar:</strong> {tem_filhos:.1f}% dos leads têm filhos menores.</li>"
        
        # Insight sobre experiência
        experiencia = (df['Experiência > 3 anos'].str.lower() == 'sim').mean() * 100
        insights += f"<li><strong>Experiência Profissional:</strong> {experiencia:.1f}% têm mais de 3 anos de experiência.</li>"
        
        insights += "</ul>"
        logger.info("Insights gerados com sucesso")
        return insights
        
    except Exception as e:
        logger.error(f"Erro ao gerar insights: {str(e)}")
        return "<p class='alert alert-warning'>Não foi possível gerar insights no momento.</p>"

def create_graphs(df):
    try:
        logger.info("Iniciando criação dos gráficos")
        graphs = {}
        
        # Configuração padrão de layout
        layout_config = {
            'template': 'plotly_white',
            'showlegend': True,
            'margin': dict(l=40, r=40, t=40, b=40),
            'height': 300
        }
        
        # Gráfico de idade
        logger.info("Criando gráfico de idade")
        idade_data = [{
            'type': 'histogram',
            'x': df['Idade'].tolist(),
            'nbinsx': 20,
            'name': 'Distribuição',
            'marker': {'color': '#4CAF50'}
        }]
        
        idade_layout = {
            **layout_config,
            'title': 'Distribuição de Idade',
            'xaxis': {'title': 'Idade'},
            'yaxis': {'title': 'Quantidade'}
        }
        
        graphs['idade'] = {'data': idade_data, 'layout': idade_layout}
        
        # Gráfico de renda
        logger.info("Criando gráfico de renda")
        renda_data = [{
            'type': 'histogram',
            'x': df['Renda Mensal'].tolist(),
            'nbinsx': 20,
            'name': 'Distribuição',
            'marker': {'color': '#2196F3'}
        }]
        
        renda_layout = {
            **layout_config,
            'title': 'Distribuição de Renda',
            'xaxis': {'title': 'Renda (R$)'},
            'yaxis': {'title': 'Quantidade'}
        }
        
        graphs['renda'] = {'data': renda_data, 'layout': renda_layout}
        
        # Gráfico de tipo de trabalho
        logger.info("Criando gráfico de tipo de trabalho")
        trabalho_counts = df['Tipo de Trabalho'].value_counts()
        trabalho_data = [{
            'type': 'pie',
            'labels': trabalho_counts.index.tolist(),
            'values': trabalho_counts.values.tolist(),
            'hole': 0.3,
            'marker': {'colors': ['#FF9800', '#9C27B0']}
        }]
        
        trabalho_layout = {
            **layout_config,
            'title': 'Tipo de Trabalho'
        }
        
        graphs['trabalho'] = {'data': trabalho_data, 'layout': trabalho_layout}
        
        # Gráfico de filhos
        logger.info("Criando gráfico de filhos")
        filhos_counts = df['Filhos Menores'].value_counts()
        filhos_data = [{
            'type': 'bar',
            'x': filhos_counts.index.tolist(),
            'y': filhos_counts.values.tolist(),
            'marker': {'color': '#E91E63'}
        }]
        
        filhos_layout = {
            **layout_config,
            'title': 'Número de Filhos Menores',
            'xaxis': {'title': 'Tem Filhos'},
            'yaxis': {'title': 'Número de Pessoas'}
        }
        
        graphs['filhos'] = {'data': filhos_data, 'layout': filhos_layout}
        
        # Gráfico de experiência
        logger.info("Criando gráfico de experiência")
        carteira_counts = df['Experiência > 3 anos'].value_counts()
        carteira_data = [{
            'type': 'pie',
            'labels': carteira_counts.index.tolist(),
            'values': carteira_counts.values.tolist(),
            'hole': 0.3,
            'marker': {'colors': ['#3F51B5', '#F44336']}
        }]
        
        carteira_layout = {
            **layout_config,
            'title': 'Mais de 3 Anos de Experiência'
        }
        
        graphs['carteira'] = {'data': carteira_data, 'layout': carteira_layout}
        
        logger.info("Gráficos criados com sucesso")
        return graphs
        
    except Exception as e:
        logger.error(f"Erro ao criar gráficos: {str(e)}")
        return None

@app.route('/dashboard')
def dashboard():
    try:
        logger.info("Carregando dados para o dashboard")
        df = load_data()
        if df.empty:
            logger.error("DataFrame vazio após carregar dados")
            return render_template(
                'dashboard.html',
                error="Não foi possível carregar os dados. Verifique o arquivo CSV.",
                table="",
                graphJSON="{}",
                insights=""
            )

        # Criar tabela HTML com as 4 primeiras linhas
        table = df.head(4).to_html(
            classes=['table', 'table-striped', 'table-hover'],
            index=False,
            float_format=lambda x: '{:,.2f}'.format(x).replace(',', '_').replace('.', ',').replace('_', '.'),
            formatters={
                'Renda Mensal': lambda x: f'R$ {x:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
            }
        )
        
        # Gerar insights
        insights = generate_insights(df)
        
        # Criar gráficos
        graphs = create_graphs(df)
        if not graphs:
            logger.error("Falha ao criar gráficos")
            graphs = {}
            
        # Preparar dados para paginação
        total_rows = len(df)
        has_more = total_rows > 4

        # Converter gráficos para JSON
        import plotly.utils
        graphJSON = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)
        logger.info("Dados preparados com sucesso para o template")
        
        return render_template(
            'dashboard.html',
            table=table,
            graphJSON=graphJSON,
            insights=insights,
            total_rows=total_rows,
            has_more=has_more
        )
        
    except Exception as e:
        logger.error(f"Erro ao renderizar dashboard: {str(e)}")
        return render_template(
            'dashboard.html',
            error="Ocorreu um erro ao carregar o dashboard. Por favor, tente novamente.",
            table="",
            graphJSON="{}",
            insights=""
        )

@app.route('/load_more_data')
def load_more_data():
    df = load_data()
    start = int(request.args.get('start', 4))
    length = int(request.args.get('length', 10))
    
    more_data = df.iloc[start:start+length].to_html(
        classes=['table', 'table-striped', 'table-hover'],
        index=False,
        float_format=lambda x: '{:,.2f}'.format(x).replace(',', '_').replace('.', ',').replace('_', '.'),
        formatters={
            'Renda Mensal': lambda x: f'R$ {x:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
        }
    )
    
    return jsonify({
        'data': more_data,
        'has_more': start + length < len(df)
    })

@app.route('/')
def index():
    logger.info("Rota index acessada")
    return redirect(url_for('dashboard'))

if __name__ != "__main__":
    gunicorn_app = app