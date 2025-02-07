from flask import Flask, request
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

app = Flask(__name__)

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
csv_file = os.path.join(BASE_DIR, 'data', 'csv', 'customers.csv')

# Configuração do Langchain
llm = ChatOpenAI(
    model="gpt-3.5-turbo",     # Modelo GPT-3.5-turbo
    max_tokens=130,
    temperature=0.2,            # Mantém respostas previsíveis
    top_p=0.7,                  # Foco em palavras mais prováveis
    frequency_penalty=0.5,      # Evita repetições
    presence_penalty=0.0,      # Mantém previsibilidade
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
markdown_instrucoes = carregar_markdown(lola_md)

# Carregar JSON
def carregar_json(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Erro ao carregar configurações: {e}")
        return {}

# Caminho para o arquivo JSON
configuracoes = carregar_json(lola_json)

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
                        from_='whatsapp:+14155238886',
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
                    from_='whatsapp:+14155238886',
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
                from_='whatsapp:+14155238886',
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
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    content_sid=template_eat
                )
                return "OK", 200
            elif intent_response == "CONTINUE":
                response = conversation_chain.run({
                    "message": incoming_msg,
                    "historico": historico,
                    "markdown_instrucoes": markdown_instrucoes,
                    "configuracoes": configuracoes
                })
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body=response
                )
                sleep(1.5)
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="*Para continuarmos, nós trabalhamos com reuniões online ou visitas na unidade, diga-nos qual você prefere 😄*\n*Porém, se tiver mais alguma dúvida, fique à vontade!*"
                )
                return "OK", 200

        if estado_cliente["etapa"] == "aguardando_opcao":
            if incoming_msg in BUTTON_IDS:
                if incoming_msg == "infos_descomplica":
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        content_sid=template_iap
                    )
                    sleep(1)
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        content_sid=template_pe
                    )
                    sleep(3)
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        content_sid=template_loop
                    )
                    estado_cliente["etapa"] = "aguardando_opcao"
                elif incoming_msg == "analise_credito":
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        body="Perfeito. Vamos te mandar algumas informações importantes para o envio de forma correta e os documentos necessários! 😎"
                    )
                    sleep(2)
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        body="""
Gostaríamos de garantir que o processo é *totalmente seguro*. A Descomplica Lares respeita e segue todas as normas estabelecidas pela *Lei Geral de Proteção de Dados (LGPD), _Lei nº 13.709/2018_*, que assegura a proteção e a privacidade dos seus dados pessoais. 
Sua privacidade é nossa prioridade, e todos os dados enviados são armazenados de forma segura e confidencial, com total responsabilidade da nossa parte. 🔒
"""
                    )
                    sleep(4)
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        content_sid=template_iap
                    )
                    sleep(2)
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        body="Esses são os documentos que serão necessários! E aqui vai uma sugestão 😊\n\nSe um dos arquivos de seus documentos for de um tamanho muito extenso, e não for possível enviar por aqui, *nos envie pelo e-mail: descomplicalares@gmail.com*. E deixe claro no e-mail a que documento você se refere!"
                    )
                    sleep(2)
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        body="Sua chamada já foi aberta! Já pode enviar os seus documentos que um corretor já entrará em contato para te auxiliar! 🧡💜"
                    )
                    sleep(2)
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        content_sid=template_loop
                    )
                elif incoming_msg == "marcar_reuniao":
                    # Pega a primeira pergunta do questionário
                    first_question = questionnaire.get_first_question("reuniao")
                    if first_question.get("template_id"):
                        client.messages.create(
                            from_='whatsapp:+14155238886',
                            to=from_whatsapp_number,
                            content_sid=globals()[first_question["template_id"]]
                        )
                    else:
                        client.messages.create(
                            from_='whatsapp:+14155238886',
                            to=from_whatsapp_number,
                            body=f"Ótimo! Para marcar sua reunião, precisamos de algumas informações. Vai levar só 3 minutinhos 😉\n{first_question['question']}"
                        )
                    estado_cliente["etapa"] = f"questionario_reuniao_{first_question['field']}"
                elif incoming_msg == "agendar_visita":
                    # Pega a primeira pergunta do questionário
                    first_question = questionnaire.get_first_question("visita")
                    if first_question.get("template_id"):
                        client.messages.create(
                            from_='whatsapp:+14155238886',
                            to=from_whatsapp_number,
                            content_sid=globals()[first_question["template_id"]]
                        )
                    else:
                        client.messages.create(
                            from_='whatsapp:+14155238886',
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
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="*Sua chamada já foi aberta, em breve um corretor entrará em contato para confirmar os detalhes dessa reunião! ✅*"
            )
            sleep(2)

            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="*Antes temos alguns pontos importantes a salientar...*\n\n  • Reunião será _online_, como videochamada 🖥\n  • Você falará com um de nossos corretores, *já tenha alguns documentos em mãos, para possíveis verificações! 😎*"
            )

            estado_cliente["etapa"] = "finalizado_tudo"
            sleep(2)

            client.messages.create(
                from_='whatsapp:+14155238886',
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
                            from_='whatsapp:+14155238886',
                            to=from_whatsapp_number,
                            body=result["message"]
                        )
                        client.messages.create(
                            from_='whatsapp:+14155238886',
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
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        body=questionnaire.questions["horario"]["pergunta"]
                    )
                    return "OK", 200
                else:
                    # Primeira vez perguntando o dia
                    estado_cliente["aguardando_dia"] = True
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        body=questionnaire.questions["dia"]["pergunta"]
                    )
                    return "OK", 200
        
            # Se já tem o dia, processa o horário
            result = questionnaire.process_message(incoming_msg, "horario", historico)
            
            if result["type"] == "error":
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body=result["message"]
                )
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body=questionnaire.questions["horario"]["pergunta"]
                )
                return "OK", 200
                
            # Salva o horário e continua
            if from_whatsapp_number in questionario_respostas:
                questionario_respostas[from_whatsapp_number]["horario"] = result["value"]
                questionnaire.save_to_csv(questionario_respostas[from_whatsapp_number])

            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body=f"Visita agendada para o dia {questionario_respostas[from_whatsapp_number]['dia']} às {result['value']}! ⌚\n*Um corretor entrará em contato para confirmar os detalhes!*"
            )
            sleep(2.5)
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="""
Estarei te passando uma lista de documentos que você pode trazer e uma confirmação de agendamento! 🏡\n
*É muito importante seu comparecimento, terá um corretor e gerente aguardando você pra te ajudar no processo de financiamento com a _CAIXA ECONÔMICA FEDERAL_ e visualização do portfólio dos imóveis!*
"""
            ) 
            sleep(3)

            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=template_iap
            )
            sleep(3)

            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=template_pe
            )

            estado_cliente["etapa"] = "encerrado"
            sleep(2)
            client.messages.create(
                from_='whatsapp:+14155238886',
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
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        body="Ótimo! Vamos continuar então! 😊"
                    )
                    sleep(1)
                    # Repete a última pergunta
                    if "template_id" in questionnaire.questions[estado_anterior["current_field"]]:
                        template_id = questionnaire.questions[estado_anterior["current_field"]]["template_id"]
                        client.messages.create(
                            from_='whatsapp:+14155238886',
                            to=from_whatsapp_number,
                            content_sid=globals()[template_id]
                        )
                    else:
                        client.messages.create(
                            from_='whatsapp:+14155238886',
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
                    from_='whatsapp:+14155238886',
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

@app.route('/')
def index():
    return "Funcionando 2025!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=True)