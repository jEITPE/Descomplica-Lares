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
from questionnaire_ai import QuestionnaireAI
from bs4 import BeautifulSoup
from time import sleep
from apscheduler.schedulers.background import BackgroundScheduler
import time
import re
import os
import csv
import json
import logging
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go
import json
from openai import OpenAI
from flask import render_template
import random
from datetime import datetime, timedelta


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

app = Flask(__name__, static_url_path='', static_folder='static')
app.config['SECRET_KEY'] = os.urandom(24)
app.config['UPLOAD_FOLDER'] = os.path.join('data', 'treinamento_ia', 'csv')

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

# Carrega as variáveis de ambiente
load_dotenv()

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

csv_dir = os.path.join(BASE_DIR, 'data', 'csv')
os.makedirs(csv_dir, exist_ok=True)
csv_file = os.path.abspath(os.path.join(csv_dir, 'costomers.csv'))

# Configuração do Langchain
llm = ChatOpenAI(
    model="gpt-3.5-turbo",     # Modelo GPT-3.5-turbo
    max_tokens=130,
    temperature=0.2,            # Mantém respostas previsíveis
    model_kwargs={
        "top_p": 0.7,
        "frequency_penalty": 0.5,
        "presence_penalty": 0.0
    },
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
    Você é a Lare, assistente virtual da imobiliária Descomplica Lares. 
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
    Você é um assistente especializado em identificar quando um usuário está respondendo corretamente a um questionário ou desviando do fluxo, seja fazendo perguntas, expressando dúvidas ou mudando de assunto. Sua função é analisar a interação do usuário e decidir se ele está seguindo o fluxo normal do questionário ou se precisa de assistência.

O assistente recebe três informações principais: o estado atual do cliente no questionário {current_stage}, a última pergunta feita ao cliente {last_question} e a mensagem recebida {message}. A análise da mensagem deve seguir regras rígidas para determinar se a resposta do usuário está de acordo com a pergunta anterior ou se ele está desviando do fluxo.

Se a mensagem do usuário for uma resposta válida à última pergunta feita, o assistente deve responder com "CONTINUE_FLOW", permitindo que o questionário prossiga normalmente. Caso a mensagem indique uma dúvida, uma nova pergunta, um pedido de esclarecimento ou qualquer outro tipo de desvio, o assistente deve responder com "FALLBACK", sinalizando que a interação do usuário não está alinhada com a pergunta atual e que pode ser necessário intervir para manter o fluxo correto.

Para classificar corretamente as mensagens, o assistente deve seguir as seguintes regras estritas:

Se a mensagem do usuário for uma resposta direta à última pergunta, mesmo que simples ou incompleta, ela deve ser classificada como "CONTINUE_FLOW". Isso inclui respostas numéricas quando a pergunta esperava um número (como idade, CPF, valor de renda), respostas curtas de "sim" ou "não" quando a pergunta foi binária, e respostas com palavras-chave esperadas (como "casado", "solteiro", "autônomo", "registrado" para perguntas sobre estado civil e trabalho).

Se a mensagem do usuário contiver uma interrogação (?), ela deve ser classificada como "FALLBACK", pois indica que o usuário está perguntando algo novo ou expressando uma dúvida.

Se a mensagem começar com palavras interrogativas como "qual", "como", "onde", "quando", "por que" ou "quem", deve ser classificada como "FALLBACK", pois indica que o usuário está fazendo uma nova pergunta em vez de responder ao questionário.

Se a mensagem do usuário expressar dúvida de forma explícita, como "não entendi", "pode explicar?", "não sei o que responder" ou algo semelhante, ela deve ser classificada como "FALLBACK", pois indica que o usuário precisa de esclarecimento antes de continuar.

Se a mensagem pedir informações adicionais ou esclarecimentos sobre o processo, deve ser classificada como "FALLBACK", pois isso significa que o usuário não está respondendo diretamente à última pergunta, mas sim buscando entender melhor o contexto.

Se a mensagem do usuário mencionar um assunto não relacionado à última pergunta feita, ela deve ser classificada como "FALLBACK". Por exemplo, se a última pergunta foi sobre idade e o usuário responde mencionando dinheiro ou renda, a resposta está fora de contexto e deve ser tratada como um desvio do fluxo.

Se a resposta do usuário for uma saudação ou agradecimento simples, como "ok", "obrigado" ou "tudo bem", ela deve ser classificada como "CONTINUE_FLOW", pois não altera o fluxo do questionário.

Se a resposta for um valor numérico esperado, como um CPF quando perguntado sobre CPF, uma idade válida quando perguntado sobre idade, um horário quando perguntado sobre horário de visita ou um valor monetário quando perguntado sobre renda, a resposta deve ser classificada como "CONTINUE_FLOW".

Se a mensagem do usuário menciona "registrado" ou "autônomo" ao responder sobre trabalho, deve ser classificada como "CONTINUE_FLOW", pois corresponde às opções esperadas.

Se houver qualquer incerteza sobre se a mensagem do usuário é uma resposta válida ou não, o assistente deve classificar como "FALLBACK", garantindo que o usuário receba assistência caso precise.

Exemplos práticos de classificação:

Se a pergunta for "Qual é a sua idade?" e o usuário responder "25", "35 anos" ou "tenho 30", a resposta deve ser "CONTINUE_FLOW", pois são respostas diretas à pergunta. Porém, se a resposta for "Qual idade mínima?", "E se eu tiver menos?", ou "Por que precisa da idade?", deve ser "FALLBACK", pois o usuário está fazendo uma pergunta ou expressando dúvida.

Se a pergunta for "Qual é o seu CPF?" e o usuário responder "123.456.789-10" ou "Não tenho aqui agora", deve ser "CONTINUE_FLOW", pois são respostas válidas. No entanto, se o usuário perguntar "Pode ser o CPF do meu marido?" ou "Como faço para tirar um CPF?", deve ser "FALLBACK", pois ele está desviando do questionário.

Se a pergunta for "Qual é a sua renda bruta mensal?" e o usuário responder "4500,00", "Ganho 3000 reais" ou "5000", deve ser "CONTINUE_FLOW", pois são respostas esperadas. No entanto, se o usuário perguntar "O que é renda bruta?", "Pode incluir hora extra?" ou "Precisa de comprovante?", deve ser "FALLBACK", pois ele está expressando dúvida ou pedindo esclarecimentos.

Se a pergunta for "Você tem filhos?" e o usuário responder "Sim, tenho 2" ou "Não", deve ser "CONTINUE_FLOW". No entanto, se a resposta for "Preciso informar quantos?" ou "Qual a idade mínima?", deve ser "FALLBACK", pois não responde diretamente à pergunta.

Se a pergunta for "Qual o seu nome?" e o usuário responder "João", "Maria", "Pedro" ou qualquer nome válido, a resposta deve ser "CONTINUE_FLOW". Porém, se o usuário perguntar "Qual nome?" ou "Preciso informar nome completo?", a resposta deve ser "FALLBACK", pois indica dúvida.

Se a pergunta for "Qual o seu horário de visita?" e o usuário responder "10:30" ou "15:45", deve ser "CONTINUE_FLOW", pois são horários válidos. Porém, se o usuário perguntar "Que horas vocês estão atendendo?" ou "Pode ser qualquer horário?", deve ser "FALLBACK", pois está pedindo informações adicionais.

Caso a resposta não tenha certeza se é válida ou não, o assistente deve sempre escolher "FALLBACK", garantindo que o usuário receba suporte antes de continuar o questionário.

No final, o assistente responde exclusivamente com "CONTINUE_FLOW" caso a resposta seja válida ou "FALLBACK" caso o usuário tenha dúvidas ou esteja desviando do fluxo esperado.


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
TEMPO_EXPIRACAO = 3600

# Agendador para verificar inatividade
scheduler = BackgroundScheduler()

# Função para verificar clientes inativos
def limpar_historico_antigo():
    tempo_atual = time.time()
    tempo_limite = 24 * 60 * 60  # 24 horas
    
    for numero in list(historico_clientes.keys()):
        if tempo_atual - historico_clientes[numero]["ultima_interacao"] > tempo_limite:
            del historico_clientes[numero]
            logger.info(f"Histórico do cliente {numero} removido após 24h de inatividade")

# Adicione ao scheduler
scheduler.add_job(limpar_historico_antigo, 'interval', hours=24)

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
    headers = ["nome", "idade", "cpf", "carteira_assinada", "estado_civil", "trabalho", "restricao_cpf", "filhos_menores", "renda_bruta", "dia", "horario"]

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
        "questionario_reuniao_renda_bruta": lambda m: bool(re.match(r"R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?", m)),
        "questionario_reuniao_dia": lambda m: bool(re.match(r"^\d{2}/\d{2}/\d{4}$", m)),
        "questionario_reuniao_horario": lambda m: validar_horario(m),
        "questionario_visita_nome": lambda m: len(m.split()) >= 2,
        "questionario_visita_idade": lambda m: m.replace(" ", "").isdigit(),
        "questionario_visita_cpf": lambda m: bool(re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", m)),
        "questionario_visita_renda_bruta": lambda m: bool(re.match(r"R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?", m)),
        "questionario_visita_dia": lambda m: bool(re.match(r"^\d{2}/\d{2}/\d{4}$", m)),
        "questionario_visita_horario": lambda m: validar_horario(m)
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
        from_='whatsapp:+554188277077',
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
            from_='whatsapp:+554188277077',
            to=from_whatsapp_number,
            body=result["message"]  # Usa a resposta da base de conhecimento
        )
        sleep(1.5)
        client.messages.create(
            from_='whatsapp:+554188277077',
            to=from_whatsapp_number,
            body="Posso continuar com as perguntas do formulário? 😊\n*(Responda com Sim ou Não)*"
        )
        estado_cliente["etapa"] = "aguardando_confirmacao_fallback"
        return "OK", 200
    
    elif result["type"] == "error":
        # Trata erro de validação
        client.messages.create(
            from_='whatsapp:+554188277077',
            to=from_whatsapp_number,
            body=result["message"]
        )
        client.messages.create(
            from_='whatsapp:+554188277077',
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
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                content_sid=globals()[next_question["template_id"]]
            )
        else:
            client.messages.create(
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                body=next_question["question"]
            )
        estado_cliente["etapa"] = f"questionario_{tipo_questionario}_{next_question['field']}"
    else:
        # Finaliza o questionário
        questionnaire.save_to_csv(questionario_respostas[from_whatsapp_number])
        client.messages.create(
            from_='whatsapp:+554188277077',
            to=from_whatsapp_number,
            body="Obrigado pelas informações, a Descomplica agradece! 🧡💜"
        )
        estado_cliente["etapa"] = f"finalizado_{tipo_questionario}"
    
    return "OK", 200

def load_interactions():
    try:
        interaction_file = os.path.join('data', 'interactions.json')
        if os.path.exists(interaction_file):
            with open(interaction_file, 'r') as f:
                return json.load(f)
        return {"interactions": {}}
    except Exception as e:
        logger.error(f"Erro ao carregar interações: {str(e)}")
        return {"interactions": {}}

def save_interaction(phone_number):
    try:
        interaction_file = os.path.join('data', 'interactions.json')
        data = load_interactions()
        
        # Se o número não existe nas interações, adiciona
        if phone_number not in data["interactions"]:
            data["interactions"][phone_number] = {
                "first_interaction": datetime.now().isoformat(),
                "last_interaction": datetime.now().isoformat()
            }
        else:
            # Se existe, apenas atualiza a última interação
            data["interactions"][phone_number]["last_interaction"] = datetime.now().isoformat()
        
        # Salva o arquivo
        with open(interaction_file, 'w') as f:
            json.dump(data, f, indent=4)
            
        return len(data["interactions"])  # Retorna o total de interações únicas
    except Exception as e:
        logger.error(f"Erro ao salvar interação: {str(e)}")
        return 0

# Configurações de monitoramento de custos
class APIMonitor:
    def __init__(self):
        self.openai_costs = {
            'gpt-3.5-turbo': 0.0015,  # Custo por 1K tokens
        }
        self.daily_usage = {}
        self.monthly_usage = {}
        self.last_reset = datetime.now()
    
    def track_openai_usage(self, model, tokens_used):
        """Registra uso da API OpenAI"""
        today = datetime.now().strftime('%Y-%m-%d')
        month = datetime.now().strftime('%Y-%m')

        logger.info(f"[DEBUG] track_openai_usage chamado com {tokens_used} tokens.")
        
        cost = (tokens_used / 1000) * self.openai_costs.get(model, 0)
        
        # Atualiza uso diário
        if today not in self.daily_usage:
            self.daily_usage[today] = {'cost': 0, 'tokens': 0, 'calls': 0}
        self.daily_usage[today]['cost'] += cost
        self.daily_usage[today]['tokens'] += tokens_used
        self.daily_usage[today]['calls'] += 1
        
        # Atualiza uso mensal
        if month not in self.monthly_usage:
            self.monthly_usage[month] = {'cost': 0, 'tokens': 0, 'calls': 0}
        self.monthly_usage[month]['cost'] += cost
        self.monthly_usage[month]['tokens'] += tokens_used
        self.monthly_usage[month]['calls'] += 1
        
        # Alerta se ultrapassar limites
        if self.monthly_usage[month]['cost'] > 50:  # Alerta se custo mensal > $50
            logger.warning(f"ALERTA DE CUSTO: Uso mensal da OpenAI ultrapassou $50 ({self.monthly_usage[month]['cost']:.2f})")
    
    def track_twilio_message(self, message_type='text'):
        """Registra uso da API Twilio"""
        today = datetime.now().strftime('%Y-%m-%d')
        month = datetime.now().strftime('%Y-%m')
        
        # Custo aproximado por mensagem
        cost = 0.005  # $0.005 por mensagem
        
        if today not in self.daily_usage:
            self.daily_usage[today] = {'twilio_cost': 0, 'messages': 0}
        self.daily_usage[today]['twilio_cost'] += cost
        self.daily_usage[today]['messages'] += 1
        
        if month not in self.monthly_usage:
            self.monthly_usage[month] = {'twilio_cost': 0, 'messages': 0}
        self.monthly_usage[month]['twilio_cost'] += cost
        self.monthly_usage[month]['messages'] += 1
        
        # Alerta se ultrapassar limites
        if self.monthly_usage[month]['messages'] > 1000:  # Alerta se mais de 1000 mensagens/mês
            logger.warning(f"ALERTA DE USO: Número de mensagens Twilio ultrapassou 1000 ({self.monthly_usage[month]['messages']})")
    
    def get_current_usage(self):
        """Retorna uso atual"""
        today = datetime.now().strftime('%Y-%m-%d')
        month = datetime.now().strftime('%Y-%m')
        
        return {
            'daily': self.daily_usage.get(today, {}),
            'monthly': self.monthly_usage.get(month, {}),
        }
    
    def save_usage_data(self):
        """Salva dados de uso em arquivo"""
        try:
            usage_file = os.path.join('data', 'api_usage.json')
            with open(usage_file, 'w') as f:
                json.dump({
                    'daily_usage': self.daily_usage,
                    'monthly_usage': self.monthly_usage,
                    'last_update': datetime.now().isoformat()
                }, f, indent=4)
        except Exception as e:
            logger.error(f"Erro ao salvar dados de uso: {str(e)}")

# Inicializa o monitor de API
api_monitor = APIMonitor()

@app.route('/monitoramento')
def monitoramento():
    """Rota amigável para monitoramento de custos"""
    usage = api_monitor.get_current_usage()
    return render_template(
        'api_costs.html',
        daily_usage=usage['daily'],
        monthly_usage=usage['monthly']
    )

# Mantém a rota original como fallback
@app.route('/api-costs')
def view_api_costs():
    return redirect(url_for('monitoramento'))

# Agendador para limpar dados antigos de uso
def limpar_dados_antigos():
    """Limpa dados de uso antigos"""
    try:
        usage_file = os.path.join('data', 'api_usage.json')
        if os.path.exists(usage_file):
            with open(usage_file, 'r') as f:
                data = json.load(f)
            
            # Limpa dados antigos
            for key in ['daily_usage', 'monthly_usage']:
                data[key] = {k: v for k, v in data[key].items() if (datetime.now() - datetime.fromisoformat(k)).days <= 90}
            
            # Salva os dados atualizados
            with open(usage_file, 'w') as f:
                json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Erro ao limpar dados antigos: {str(e)}")

# Adiciona ao scheduler
scheduler.add_job(limpar_dados_antigos, 'interval', days=1)

@app.route('/bot', methods=['POST'])
def bot():
    try:
        # Verificar se é um arquivo ou áudio
        if 'MediaContentType0' in request.values:
            media_type = request.values.get('MediaContentType0', '')
            from_whatsapp_number = request.values.get('From', '')
            
            # Se for um áudio, enviar mensagem informando que não suporta
            if media_type.startswith('audio/'):
                try:
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        body="Desculpe, não consigo processar mensagens de áudio. Por favor, envie sua mensagem em texto."
                    )
                except Exception as e:
                    logger.error(f"Erro ao enviar mensagem sobre áudio: {str(e)}")
            
            # Para qualquer tipo de mídia, continuamos o fluxo normal
            # mas não processamos o conteúdo da mídia

        # Continua com o fluxo normal
        from_whatsapp_number = request.values.get('From')
        if from_whatsapp_number not in conversation_contexts:
            conversation_contexts[from_whatsapp_number] = ConversationContext()
        
        context = conversation_contexts[from_whatsapp_number]
        incoming_msg = request.values.get('Body', '').strip()
        if not incoming_msg:
            logger.info('Mensagem vazia recebida; retornando OK sem processamento adicional.')
            return "OK", 200
        
        tempo_atual = time.time()

        # Controle de histórico
        if from_whatsapp_number not in historico_clientes:
            historico_clientes[from_whatsapp_number] = {
                "historico": [],
                "ultima_interacao": tempo_atual
            }
        else:
            historico_clientes[from_whatsapp_number]["ultima_interacao"] = tempo_atual

        # Histórico
        historico_clientes[from_whatsapp_number]["historico"].append(incoming_msg)
        historico = '\n'.join(historico_clientes[from_whatsapp_number]["historico"])

        if from_whatsapp_number not in cliente_estado:
            cliente_estado[from_whatsapp_number] = {"etapa": "inicial", "respostas": {}}
            try:
                logger.info(f"Enviando mensagem de boas-vindas para {from_whatsapp_number}")
                message = client.messages.create(
                    from_='whatsapp:+554188277077',
                    to=from_whatsapp_number,
                    body="Olá, Seja bem-vindo(a) 🏘\nAqui é a *Lare*, assistente virtual da Descomplica Lares! Como posso te ajudar?"
                )
                logger.info(f"Mensagem enviada com sucesso. SID: {message.sid}")
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem: {str(e)}")
            return "OK", 200

        estado_cliente = cliente_estado[from_whatsapp_number]

        logger.info(f"Mensagem recebida de {from_whatsapp_number}: {incoming_msg}")
        logger.info(f"Estado atual: {estado_cliente['etapa']}")
        logger.debug(f"Contexto completo: {conversation_contexts[from_whatsapp_number].context}")

        if incoming_msg == "Desejo voltar!":
            # Reinicia o estado do cliente
            cliente_estado[from_whatsapp_number] = {"etapa": "inicial", "respostas": {}}
            
            # Envia a mensagem de boas-vindas novamente
            client.messages.create(
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                body="Olá, Seja bem-vindo(a) 🏘\nAqui é a *Lare*, assistente virtual da Descomplica Lares! Como posso te ajudar?"
            )
            return "OK", 200

        if estado_cliente["etapa"] == "inicial":
            intent_response = intention_chain.run(message=incoming_msg).strip()
            logger.info(f"Intenção detectada: {intent_response}")
            if intent_response == "PASS_BUTTON":
                estado_cliente["etapa"] = "aguardando_opcao"
                client.messages.create(
                    from_='whatsapp:+554188277077',
                    to=from_whatsapp_number,
                    content_sid=template_eat
                )
                return "OK", 200
            elif intent_response == "CONTINUE":
                api_monitor.track_twilio_message()  # Monitorar uso do Twilio
                tokens_used = len(incoming_msg.split())  # Exemplo de contagem de tokens
                api_monitor.track_openai_usage("gpt-3.5-turbo", tokens_used)  # Monitorar uso da OpenAI
                response = conversation_chain.run({
                    "message": incoming_msg,
                    "historico": historico,
                    "markdown_instrucoes": markdown_instrucoes,
                    "configuracoes": configuracoes
                })
                client.messages.create(
                    from_='whatsapp:+554188277077',
                    to=from_whatsapp_number,
                    body=response
                )
                sleep(1.5)
                client.messages.create(
                    from_='whatsapp:+554188277077',
                    to=from_whatsapp_number,
                    body="*Para continuarmos, nós trabalhamos com reuniões online ou visitas na unidade, diga-nos qual você prefere 😄*\n*Porém, se tiver mais alguma dúvida, fique à vontade!*"
                )
                return "OK", 200

        if estado_cliente["etapa"] == "aguardando_opcao":
            if incoming_msg in BUTTON_IDS:
                if incoming_msg == "infos_descomplica":
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        content_sid=template_iap
                    )
                    sleep(1)
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        content_sid=template_pe
                    )
                    sleep(3)
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        content_sid=template_loop
                    )
                    estado_cliente["etapa"] = "aguardando_opcao"
                elif incoming_msg == "analise_credito":
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        body="Perfeito. Vamos te mandar algumas informações importantes para o envio de forma correta e os documentos necessários! 😎"
                    )
                    sleep(2)
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        body="""
Gostaríamos de garantir que o processo é *totalmente seguro*. A Descomplica Lares respeita e segue todas as normas estabelecidas pela *Lei Geral de Proteção de Dados (LGPD), _Lei nº 13.709    2018_*, que assegura a proteção e a privacidade dos seus dados pessoais. 
Sua privacidade é nossa prioridade, e todos os dados enviados são armazenados de forma segura e confidencial, com total responsabilidade da nossa parte. 🔒
"""
                    )
                    sleep(4)
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        content_sid=template_iap
                    )
                    sleep(2)
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        body="Esses são os documentos que serão necessários! E aqui vai uma sugestão 😊\n\nSe um dos arquivos de seus documentos for de um tamanho muito extenso, e não for possível enviar por aqui, *nos envie pelo e-mail: descomplicalares@gmail.com*. E deixe claro no e-mail a que documento você se refere!"
                    )
                    sleep(2)
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        body="Sua chamada já foi aberta! Já pode enviar os seus documentos que um corretor já entrará em contato para te auxiliar! 🧡💜"
                    )
                    sleep(2)
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        content_sid=template_loop
                    )
                elif incoming_msg == "marcar_reuniao":
                    # Pega a primeira pergunta do questionário
                    first_question = questionnaire.get_first_question("reuniao")
                    if first_question.get("template_id"):
                        client.messages.create(
                            from_='whatsapp:+554188277077',
                            to=from_whatsapp_number,
                            content_sid=globals()[first_question["template_id"]]
                        )
                    else:
                        client.messages.create(
                            from_='whatsapp:+554188277077',
                            to=from_whatsapp_number,
                            body=f"Ótimo! Para marcar sua reunião, precisamos de algumas informações. Vai levar só 3 minutinhos 😉\n{first_question['question']}"
                        )
                    estado_cliente["etapa"] = f"questionario_reuniao_{first_question['field']}"
                elif incoming_msg == "agendar_visita":
                    # Pega a primeira pergunta do questionário
                    first_question = questionnaire.get_first_question("visita")
                    if first_question.get("template_id"):
                        client.messages.create(
                            from_='whatsapp:+554188277077',
                            to=from_whatsapp_number,
                            content_sid=globals()[first_question["template_id"]]
                        )
                    else:
                        client.messages.create(
                            from_='whatsapp:+554188277077',
                            to=from_whatsapp_number,
                            body=f"Ótimo! Para agendar sua visita, precisamos de algumas informações! Vai levar só 3 minutinhos 😉\n{first_question['question']}"
                        )
                    estado_cliente["etapa"] = f"questionario_visita_{first_question['field']}"
    
            # Retorno padrão para o caso de nenhum dos if acima ser acionado
            return "OK", 200
    
        if estado_cliente["etapa"].startswith("questionario_reuniao"):
            current_field = estado_cliente["etapa"].replace("questionario_reuniao_", "")
            return process_questionnaire_step(from_whatsapp_number, incoming_msg, current_field, historico, "reuniao")
        elif estado_cliente["etapa"].startswith("questionario_visita"):
            current_field = estado_cliente["etapa"].replace("questionario_visita_", "")
            return process_questionnaire_step(from_whatsapp_number, incoming_msg, current_field, historico, "visita")
        elif estado_cliente["etapa"] == "finalizado_reuniao":
            client.messages.create(
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                body="*Sua chamada já foi aberta, em breve um corretor entrará em contato para confirmar os detalhes dessa reunião! ✅*"
            )
            sleep(2)

            client.messages.create(
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                body="*Antes temos alguns pontos importantes a salientar...*\n\n  • Reunião será _online_, como videochamada 🖥\n  • Você falará com um de nossos corretores, *já tenha alguns documentos em mãos, para possíveis verificações! 😎*"
            )
            estado_cliente["etapa"] = "finalizado_tudo"
            sleep(2)

            client.messages.create(
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                content_sid=template_loop
            )
            return "OK", 200
        elif estado_cliente["etapa"] == "finalizado_visita":
            # Primeiro pergunta o dia se ainda não foi perguntado
            if "dia" not in questionario_respostas.get(from_whatsapp_number, {}):
                if estado_cliente.get("aguardando_dia", False):
                    # Processa a resposta do dia
                    result = questionnaire.process_message(incoming_msg, "dia", historico)
                    
                    if result["type"] == "error":
                        client.messages.create(
                            from_='whatsapp:+554188277077',
                            to=from_whatsapp_number,
                            body=result["message"]
                        )
                        client.messages.create(
                            from_='whatsapp:+554188277077',
                            to=from_whatsapp_number,
                            body=questionnaire.questions["dia"]["pergunta"]
                        )
                        return "OK", 200
                    
                    # Salva o dia e continua para o horário
                    if from_whatsapp_number not in questionario_respostas:
                        questionario_respostas[from_whatsapp_number] = {}
                    questionario_respostas[from_whatsapp_number]["dia"] = result["value"]
                    estado_cliente["aguardando_dia"] = False
                    
                    # Pergunta o horário
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        body=questionnaire.questions["horario"]["pergunta"]
                    )
                    return "OK", 200
                else:
                    # Primeira vez perguntando o dia
                    estado_cliente["aguardando_dia"] = True
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        body=questionnaire.questions["dia"]["pergunta"]
                    )
                    return "OK", 200
        
            # Se já tem o dia, processa o horário
            result = questionnaire.process_message(incoming_msg, "horario", historico)
            
            if result["type"] == "error":
                client.messages.create(
                    from_='whatsapp:+554188277077',
                    to=from_whatsapp_number,
                    body=result["message"]
                )
                client.messages.create(
                    from_='whatsapp:+554188277077',
                    to=from_whatsapp_number,
                    body=questionnaire.questions["horario"]["pergunta"]
                )
                return "OK", 200
                
            # Salva o horário e continua
            if from_whatsapp_number in questionario_respostas:
                questionario_respostas[from_whatsapp_number]["horario"] = result["value"]
                questionnaire.save_to_csv(questionario_respostas[from_whatsapp_number])

            client.messages.create(
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                body=f"Visita agendada para o dia {questionario_respostas[from_whatsapp_number]['dia']} às {result['value']}! ⌚\n*Um corretor entrará em contato para confirmar os detalhes!*"
            )
            sleep(2.5)
            client.messages.create(
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                body="""
Estarei te passando uma lista de documentos que você pode trazer e uma confirmação de agendamento! 🏡\n
*É muito importante seu comparecimento, terá um corretor e gerente aguardando você pra te ajudar no processo de financiamento com a _CAIXA ECONÔMICA FEDERAL_ e visualização do portfólio dos imóveis!*
"""
            ) 
            sleep(3)

            client.messages.create(
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                content_sid=template_iap
            )
            sleep(3)

            client.messages.create(
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                content_sid=template_pe
            )

            estado_cliente["etapa"] = "encerrado"
            sleep(2)
            client.messages.create(
                from_='whatsapp:+554188277077',
                to=from_whatsapp_number,
                content_sid=template_loop
            )
            return "OK", 200
        elif estado_cliente["etapa"] == "aguardando_confirmacao_fallback":
            if incoming_msg.lower() in ["sim", "s", "yes", "y", "pode", "claro", "ok"]:
                # Restaura o estado anterior
                estado_anterior = aguardando_confirmacao.get(from_whatsapp_number)
                if estado_anterior:
                    estado_cliente["etapa"] = estado_anterior["etapa"]
                    # Mensagem de transição
                    client.messages.create(
                        from_='whatsapp:+554188277077',
                        to=from_whatsapp_number,
                        body="Ótimo! Vamos continuar então! 😊"
                    )
                    sleep(1)
                    # Repete a última pergunta
                    if "template_id" in questionnaire.questions[estado_anterior["current_field"]]:
                        template_id = questionnaire.questions[estado_anterior["current_field"]]["template_id"]
                        client.messages.create(
                            from_='whatsapp:+554188277077',
                            to=from_whatsapp_number,
                            content_sid=globals()[template_id]
                        )
                    else:
                        client.messages.create(
                            from_='whatsapp:+554188277077',
                            to=from_whatsapp_number,
                            body=estado_anterior["ultima_pergunta"]
                        )
            else:
                # Mensagens mais naturais para quando o usuário não quer continuar
                respostas_nao = [
                    "Tudo bem! Quando quiser retomar o formulário, é só me avisar dizendo 'quero continuar'. 😊",
                    "Ok, sem problemas! Podemos continuar depois, basta dizer 'quero continuar'. 👍",
                    "Entendi! Quando estiver pronto para continuar, me avise com 'quero continuar'. 🤗",
                    "Claro! Ficarei aqui aguardando. Quando quiser voltar, diga 'quero continuar'. 😉"
                ]
                client.messages.create(
                    from_='whatsapp:+554188277077',
                    to=from_whatsapp_number,
                    body=random.choice(respostas_nao)
                )
                estado_cliente["etapa"] = "inicial"
        
            # Limpa o estado de confirmação
            if from_whatsapp_number in aguardando_confirmacao:
                del aguardando_confirmacao[from_whatsapp_number]

            return "OK", 200

        # Retorno default se nenhuma condição anterior for satisfeita
        return "OK", 200
    except Exception as e:
        logger.error(f"Erro no processamento do bot: {str(e)}")
        return "OK", 200  # Sempre retorna OK mesmo em caso de erro

def load_data():
    try:
        logger.info("Iniciando carregamento de dados")

        csv_dir = os.path.join(BASE_DIR, 'data', 'csv')
        os.makedirs(csv_dir, exist_ok=True)
        file_path = os.path.join(csv_dir, 'customers.csv')
        
        # Carregar interações únicas
        interaction_data = load_interactions()
        total_interacoes = len(interaction_data.get("interactions", {}))
        
        # Definir os nomes das colunas
        column_names = ['Nome', 'Idade', 'CPF', 'Experiência > 3 anos', 'Estado Civil', 
                       'Tipo de Trabalho', 'Motivo', 'Filhos Menores', 'Renda Mensal', 
                       'Unnamed1', 'Unnamed2']
        
        # Tentar diferentes encodings em ordem
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'iso-8859-1']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding, names=column_names, header=None)
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise Exception("Não foi possível ler o arquivo com nenhum dos encodings tentados")
        
        # Calcular métricas de interação
        interacoes_excedentes = max(0, total_interacoes - 150)
        custo_total = interacoes_excedentes * 2  # R$ 2,00 por interação excedente
        
        # Adicionar métricas ao contexto
        df.attrs['metricas'] = {
            'total_interacoes': total_interacoes,
            'interacoes_excedentes': interacoes_excedentes,
            'custo_total': custo_total
        }
        
        # Remover colunas não utilizadas
        df = df.drop(['Unnamed1', 'Unnamed2', 'CPF', 'Motivo'], axis=1)
        
        # Limpar e converter dados
        df['Idade'] = pd.to_numeric(df['Idade'], errors='coerce')
        df['Renda Mensal'] = df['Renda Mensal'].str.replace('.', '').str.replace(',', '.').astype(float)
        
        # Normalizar strings para UTF-8
        text_columns = ['Nome', 'Estado Civil', 'Tipo de Trabalho', 'Filhos Menores', 'Experiência > 3 anos']
        for col in text_columns:
            df[col] = df[col].astype(str).apply(lambda x: x.strip())
        
        return df
        
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {str(e)}")
        return pd.DataFrame()

def create_graphs(df):
    try:
        logger.info("Iniciando criação dos gráficos")
        graphs = {}
        
        # Configuração padrão de layout
        layout_config = {
            'template': 'plotly_white',
            'showlegend': True,
            'margin': dict(l=40, r=40, t=40, b=40),
            'height': 300,
            'paper_bgcolor': 'rgba(0,0,0,0)',
            'plot_bgcolor': 'rgba(0,0,0,0)',
            'font': {
                'family': 'Inter, sans-serif',
                'size': 12,
                'color': '#555'
            }
        }
        
        # Gráfico de idade - Linha com área
        logger.info("Criando gráfico de idade")
        idade_bins = pd.cut(df['Idade'], bins=[0, 25, 30, 35, 40, 100], labels=['20-25', '26-30', '31-35', '36-40', '41+'])
        idade_counts = idade_bins.value_counts().sort_index()
        
        idade_data = [{
            'type': 'scatter',
            'x': idade_counts.index,
            'y': idade_counts.values,
            'mode': 'lines+markers',
            'name': 'Distribuição',
            'line': {
                'color': '#8339EA',
                'width': 3,
                'shape': 'spline'
            },
            'marker': {
                'size': 8,
                'color': '#8339EA'
            },
            'fill': 'tozeroy',
            'fillcolor': 'rgba(131, 57, 234, 0.1)'
        }]
        
        idade_layout = {
            **layout_config,
            'title': {'text': 'Distribuição por Idade', 'font': {'family': 'Inter, sans-serif', 'size': 16}},
            'xaxis': {
                'title': None,
                'showgrid': False,
                'showline': False
            },
            'yaxis': {
                'title': None,
                'showgrid': True,
                'gridcolor': 'rgba(0,0,0,0.1)',
                'showline': False
            }
        }
        
        graphs['idade'] = {'data': idade_data, 'layout': idade_layout}
        
        # Gráfico de renda - Barras modernas
        logger.info("Criando gráfico de renda")
        renda_bins = pd.cut(df['Renda Mensal'], 
                          bins=[0, 3000, 5000, 8000, float('inf')],
                          labels=['0-3k', '3k-5k', '5k-8k', '8k+'])
        renda_counts = renda_bins.value_counts().sort_index()
        
        renda_data = [{
            'type': 'bar',
            'x': renda_counts.index,
            'y': renda_counts.values,
            'name': 'Distribuição',
            'marker': {
                'color': '#FDBB0C',
                'opacity': 0.9
            }
        }]
        
        renda_layout = {
            **layout_config,
            'title': {'text': 'Distribuição de Investimento', 'font': {'family': 'Inter, sans-serif', 'size': 16}},
            'xaxis': {
                'title': None,
                'showgrid': False,
                'showline': False
            },
            'yaxis': {
                'title': None,
                'showgrid': True,
                'gridcolor': 'rgba(0,0,0,0.1)',
                'showline': False
            }
        }
        
        graphs['renda'] = {'data': renda_data, 'layout': renda_layout}
        
        # Gráfico de tipo de trabalho - Donut moderno
        logger.info("Criando gráfico de tipo de trabalho")
        trabalho_counts = df['Tipo de Trabalho'].value_counts()
        trabalho_data = [{
            'type': 'pie',
            'labels': trabalho_counts.index,
            'values': trabalho_counts.values,
            'hole': 0.6,
            'marker': {
                'colors': ['#8339EA', '#FDBB0C'],
            },
            'textinfo': 'percent',
            'textposition': 'outside',
            'textfont': {
                'family': 'Inter, sans-serif',
                'size': 12
            }
        }]
        
        trabalho_layout = {
            **layout_config,
            'title': {'text': 'Origem dos Leads', 'font': {'family': 'Inter, sans-serif', 'size': 16}},
            'showlegend': True,
            'legend': {
                'orientation': 'h',
                'yanchor': 'bottom',
                'y': -0.2,
                'xanchor': 'center',
                'x': 0.5
            }
        }
        
        graphs['trabalho'] = {'data': trabalho_data, 'layout': trabalho_layout}
        
        # Gráfico de filhos - Barras verticais modernas
        logger.info("Criando gráfico de filhos")
        filhos_counts = df['Filhos Menores'].value_counts()
        filhos_data = [{
            'type': 'bar',
            'x': filhos_counts.index,
            'y': filhos_counts.values,
            'marker': {
                'color': '#8339EA',
                'opacity': 0.9
            },
            'textposition': 'auto'
        }]
        
        filhos_layout = {
            **layout_config,
            'title': {'text': 'Interesse dos Leads', 'font': {'family': 'Inter, sans-serif', 'size': 16}},
            'xaxis': {
                'title': None,
                'showgrid': False,
                'showline': False
            },
            'yaxis': {
                'title': None,
                'showgrid': True,
                'gridcolor': 'rgba(0,0,0,0.1)',
                'showline': False
            }
        }
        
        graphs['filhos'] = {'data': filhos_data, 'layout': filhos_layout}
        
        # Gráfico de experiência - Pie moderno
        logger.info("Criando gráfico de experiência")
        carteira_counts = df['Experiência > 3 anos'].value_counts()
        carteira_data = [{
            'type': 'pie',
            'labels': carteira_counts.index,
            'values': carteira_counts.values,
            'marker': {
                'colors': ['#8339EA', '#FDBB0C']
            },
            'textinfo': 'percent',
            'textposition': 'inside',
            'textfont': {
                'family': 'Inter, sans-serif',
                'size': 12,
                'color': 'white'
            }
        }]
        
        carteira_layout = {
            **layout_config,
            'title': {'text': 'Status dos Leads', 'font': {'family': 'Inter, sans-serif', 'size': 16}},
            'showlegend': True,
            'legend': {
                'orientation': 'h',
                'yanchor': 'bottom',
                'y': -0.2,
                'xanchor': 'center',
                'x': 0.5
            }
        }
        
        graphs['carteira'] = {'data': carteira_data, 'layout': carteira_layout}
        
        logger.info("Gráficos criados com sucesso")
        return graphs
        
    except Exception as e:
        logger.error(f"Erro ao criar gráficos: {str(e)}")
        return None

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
        
        # Ensure proper UTF-8 encoding
        insights = insights.encode('utf-8', errors='ignore').decode('utf-8')
        
        logger.info("Insights gerados com sucesso")
        return insights
        
    except Exception as e:
        logger.error(f"Erro ao gerar insights: {str(e)}")
        return "Erro ao gerar insights."
    
@app.route('/dashboard')
def dashboard():
    try:
        logger.info("Carregando dados para o dashboard")
        df = load_data()  # Carregar dados do CSV
        
        if df.empty:
            logger.error("DataFrame vazio após carregar dados")
            return render_template(
                'dashboard.html',
                error="Não foi possível carregar os dados. Verifique o arquivo CSV.",
                table="",
                graphJSON="{}",
                insights="",
                total_interacoes=0,
                interacoes_excedentes=0,
                custo_total=0.0
            )
        
        # Carregar dados de interações do JSON
        interaction_data = load_interactions()
        total_interacoes = len(interaction_data.get("interactions", {}))
        interacoes_excedentes = max(0, total_interacoes - 150)
        custo_total = interacoes_excedentes * 2

        # Resto do código permanece igual, apenas usando as variáveis que definimos acima
        table = df.head(4).to_html(
            classes=['table', 'table-striped', 'table-hover'],
            index=False,
            float_format=lambda x: '{:,.2f}'.format(x).replace(',', '_').replace('.', ',').replace('_', '.'),
            formatters={
                'Renda Mensal': lambda x: f'R$ {x:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
            }
        )
        
        # Gerar insights com as métricas de interação
        insights = generate_insights(df)
        insights += f"""
        <li><strong>Métricas de Interação:</strong>
            <ul>
                <li>Total de interações: {total_interacoes}</li>
                <li>Interações excedentes: {interacoes_excedentes}</li>
                <li>Custo adicional: R$ {custo_total:.2f}</li>
            </ul>
        </li>
        """
        
        # Criar gráficos
        graphs = create_graphs(df)
        if not graphs:
            logger.error("Falha ao criar gráficos")
            graphs = {}
            
        # Preparar dados para paginação
        total_rows = len(df)
        has_more = total_rows > 4

        # Converter gráficos para JSON
        graphJSON = json.dumps(graphs, cls=plotly.utils.PlotlyJSONEncoder)
        logger.info(f"Dados preparados com sucesso. Total de interações: {total_interacoes}")
        
        # Adicionar log para monitoramento de custos
        if interacoes_excedentes > 0:
            logger.warning(f"Atenção: {interacoes_excedentes} interações excedentes, gerando custo de R$ {custo_total:.2f}")
        
        return render_template(
            'dashboard.html',
            table=table,
            graphJSON=graphJSON,
            insights=insights,
            total_rows=total_rows,
            has_more=has_more,
            total_interacoes=total_interacoes,
            interacoes_excedentes=interacoes_excedentes,
            custo_total=custo_total,
            limite_gratuito=150
        )
        
    except Exception as e:
        logger.error(f"Erro ao renderizar dashboard: {str(e)}")
        return render_template(
            'dashboard.html',
            error="Ocorrer um erro ao carregar o dashboard. Por favor, tente novamente.",
            table="",
            graphJSON="{}",
            insights="",
            total_interacoes=0,
            interacoes_excedentes=0,
            custo_total=0.0,
            limite_gratuito=150
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

# Agendador para limpar dados antigos de uso
def cleanup_old_usage_data():
    """Limpa dados de uso mais antigos que 90 dias"""
    try:
        cutoff_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        api_monitor.daily_usage = {k: v for k, v in api_monitor.daily_usage.items() 
                                 if k >= cutoff_date}
        api_monitor.save_usage_data()
    except Exception as e:
        logger.error(f"Erro ao limpar dados antigos: {str(e)}")

# Adiciona job ao scheduler existente
scheduler.add_job(cleanup_old_usage_data, 'cron', day='1')
scheduler.start()

@app.route('/')
def index():
    return "Funcionando 2025!"

if __name__ != "__main__":
    gunicorn_app = app