from flask import Flask, request
from twilio.rest import Client
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.llms import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
import markdown
from twilio.http.http_client import TwilioHttpClient
from bs4 import BeautifulSoup
from time import sleep
import re
import os
import csv
import json

app = Flask(__name__)

# Carrega as variáveis de ambiente
load_dotenv()

account_sid = os.getenv("ACCOUNT_SID")
auth_token = os.getenv("AUTH_TOKEN")
proxy_client = TwilioHttpClient(timeout=10)  # Define timeout de 10 segundos
client = Client(account_sid, auth_token, http_client=proxy_client)

template_eat = os.getenv("CONTENT_ID_EAT")
template_pe = os.getenv("CONTENT_ID_PE")
template_iap = os.getenv("CONTENT_ID_IAP")
template_av = os.getenv("CONTENT_ID_AV")
template_loop = os.getenv("CONTENT_ID_LOOP")
template_3anos = os.getenv("CONTENT_ID_3")
template_autonomo_registrado = os.getenv("CONTENT_ID_AR")
template_filhos = os.getenv("CONTENT_ID_FILHOS")

api_key = os.getenv("OPENAI_API_KEY")
lola_md = os.getenv("MARKDOWN_TRAINING")
lola_json = os.getenv("JSON_TRAINING")


# Configuração do Langchain
llm = OpenAI(
    temperature=0.4,            # Mantém respostas previsíveis
    max_tokens=300,             # Respostas curtas e objetivas
    top_p=0.7,                  # Foco em palavras mais prováveis
    frequency_penalty=0.5,      # Evita repetições
    presence_penalty=0.0,       # Mantém previsibilidade
    n=1,                        # Uma única resposta
    stop=["\n", "Cliente:"]     # Para respostas após delimitador
)

# Função para carregar e processar o arquivo Markdown
def carregar_markdown(markdown_path):
    try:
        with open(markdown_path, 'r', encoding='utf-8') as f:
            html = markdown.markdown(f.read())
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()
            return text
    except Exception as e:
        print(f"Erro ao carregar o markdown: {e}")
        return ""

# Caminho para o arquivo Markdown
markdown_instrucoes = carregar_markdown(lola_md)

# Carregar exemplos e instruções do JSON
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
    input_variables=["message", "markdown_instrucoes", "configuracoes"],
    template="""
    Você é a Lola, assistente virtual da imobiliária Descomplica Lares. 
    Você tem uma abordagem simples e clara. Textos muito grande não agradam os seus clientes, então seja o mais direta possível.
    Responda somente com base nas instruções fornecidas. Se a pergunta for fora do escopo, diga algo como: 
    "Mil perdões, eu não tenho certeza da resposta! 😓\nSe precisar marcar uma conversa com um corretor, digite *atendimento*"

    Sempre respostas curtas e diretas! Nunca responda algo que você não tem conhecimento, algo que você não foi treinada pra dizer,
    ou algo que não tenha nada haver com a Imobiliária em si!

    - Se o cliente disser algo como "obrigado", "valeu", "entendi", "blz" ou "agradecido", responda com algo como "De nada! Se precisar de algo mais, estarei aqui. 😊". "Caso queira marcar uma visita ou uma reunião online, digite *atendimento*!"
    - Se o cliente disser algo como "ok", "entendido" ou "finalizar", responda com algo como "Certo! Estarei por aqui caso precise. Até logo! 👋". "Caso queira marcar uma visita ou uma reunião online, digite *atendimento*!"
    - Nunca invente informações ou forneça respostas fora do escopo da imobiliária.
    - Seja educada e simpática, mas sempre clara e objetiva.

    Não se refira ao cliente, só responda às suas perguntas.

    ### Exemplos de perguntas que você pode responder:
    1. "Quais os documentos que eu preciso para dar entrada?" (Responda com a lista de documentos necessária).
    2. "Onde vocês se localizam?" (Responda com o endereço fornecido).
    3. "Vocês trabalham com imóveis comerciais?" (Responda que a imobiliária trabalha apenas com residências).
    4. "O endereço de vocês é o mesmo que está no catálogo?" (Responda algo como: "Sim, nosso endereço é o mesmo do catálogo: Rua Padre Antonio, 365.\nPosso ajudar em mais alguma coisa? 😊")

    ### Restrições:
    - Nunca invente informações.
    - Nunca forneça dados não incluídos nas instruções do markdown.
    - Nunca interfirá quando a mensagem do cliente for sobre:
        - Marcar uma reunião. "Gostaria de marcar uma reunião" "Como posso marcar uma reunião?"
        - Marcar uma visita. "Acho melhor marcar uma visita para conhecer o local e os empreendimentos!" "Quero agendar uma visita" "Como posso marcar uma visita"
        - Querer comprar ou dar entrada algum apartamento ou empreendimento já. "Quero dar entrada/comprar em um apartamento"

    Se perceber que o cliente está com as dúvidas sanadas, recomende-o a digitar apenas *atendimento*.:
        "De nada! Se precisar de algo mais, estarei aqui. 😊 Caso queira marcar uma visita ou uma reunião online, digite atendimento!"

    Ao final, pergunte se pode ajudar o cliente com mais alguma coisa.

    ### Instruções carregadas:
    {markdown_instrucoes}

    ### Exemplos de respostas para perguntas:
    {configuracoes}

    ### Mensagem do cliente:
    Cliente: {message}

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
    - Se o cliente apenas digitar: "atendimento".
    Responda com "PASS_BUTTON" se identificar alguma dessas intenções na mensagem.
    Caso contrário, responda com "CONTINUE".

    Exemplos que você não deve interferir:
    "Quais os documentos que eu preciso?" 
    "Onde vocês se localizam?"
    "Vocês trabalham com imóveis comerciais ou só residenciais?"
    "O que é preciso para fazer uma simulação de financiamento?"
    "Como vocês trabalham?"

    Cliente: {message}
    """
)
intention_chain = LLMChain(llm=llm, prompt=prompt_rubens)

prompt_agendadora = PromptTemplate(
    input_variables=["message", "dia", "horario"],
    template="""
    Você é a Agendadora, uma assistente especializada em agendamentos para a imobiliária Descomplica Lares.

    Funções principais:
    1. Informar horários disponíveis:
       - Segunda a sábado: 09:00 às 20:00.
       - Domingo: 09:00 às 12:00.
    2. Garantir que os horários escolhidos devem terminar com *5 no final* (ex: 10:35, 11:15, 12:45).
    3. Confirmar o horário informado pelo cliente, sem validar a disponibilidade (isso será tratado pelo corretor).  
    4. Se o horário não for válido, peça educadamente para escolher um horário no formato correto.  

    Regras:
    - Nunca invente horários ou detalhes não mencionados nas regras acima.
    - Se o cliente tiver dúvidas, informe-o para digitar *atendimento* para falar com um corretor.  
    - Registre o horário fornecido e confirme o agendamento, destacando que será revisado por um corretor.  

    Exemplos:
    - Cliente: "Quero marcar para segunda às 10:35."
      Resposta: "Horário agendado para segunda às 10:35. 😊\nUm corretor entrará em contato para confirmar os detalhes!"  
    - Cliente: "Posso marcar às 10:30?"
      Resposta: "Ops! 😊 Os horários precisam terminar com *5 no final*. Exemplos: 10:35, 11:15. Por favor, escolha um horário válido."

    Cliente: {message}
    Agendamento:
    Dia: {dia}
    Horário: {horario}
    """
)

# Criação do LLMChain para a Agendadora
agendamento_chain = LLMChain(llm=llm, prompt=prompt_agendadora)

# Mapeamento dos IDs dos botões
BUTTON_IDS = {
    "infos_descomplica": "informações",
    "marcar_reuniao": "marcar reunião",
    "agendar_visita": "agendar visita"
}

cliente_estado = {}

# Função para criar reunião com Google Meet
def marcar_reuniao(service, nome_cliente, descricao):
    pass

def validar_horario(horario):
    # Verifica apenas se o horário termina com '5'
    return horario.strip()[-1] == "5"

def salvar_resposta(estado_cliente, campo, valor):
    if "respostas" not in estado_cliente:
        estado_cliente["respostas"] = {}
    estado_cliente["respostas"][campo] = valor

# Função para salvar as respostas no CSV
def salvar_no_csv(estado_cliente):
    file_path = r"C:\Users\joaop\Documents\Descomplica (ORG)\Descomplica (ORG)\csv\costumers.csv"
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
    elif campo == "email":
        if not re.match(r"[^@]+@[^@]+\.[^@]+", valor):
            return False, "O e-mail informado não é válido."
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

@app.route('/bot', methods=['POST'])
def bot():
    incoming_msg = request.values.get('Body', '').strip()
    from_whatsapp_number = request.values.get('From')

    if from_whatsapp_number not in cliente_estado:
        cliente_estado[from_whatsapp_number] = {"etapa": "inicial", "respostas": {}}
        client.messages.create(
            from_='whatsapp:+14155238886',
            to=from_whatsapp_number,
            body="Olá, Seja bem-vindo(a) 😊\nAqui é a *Lola*, assistente virtual da Descomplica Lares! Como posso te ajudar?"
        )
        return "OK", 200

    estado_cliente = cliente_estado[from_whatsapp_number]

    print(f"Mensagem recebida: {incoming_msg}")

    if incoming_msg == "Desejo voltar!":
        estado_cliente["etapa"] = "aguardando_opcao"
        client.messages.create(
            from_='whatsapp:+14155238886',
            to=from_whatsapp_number,
            body="Voltando ao início! Por favor, escolha uma das opções novamente. 😊"
        )
        sleep(2)
        client.messages.create(
            from_='whatsapp:+14155238886',
            to=from_whatsapp_number,
            content_sid=template_eat
        )
        return "OK", 200

    if estado_cliente["etapa"] == "inicial":
        intent_response = intention_chain.run(message=incoming_msg).strip()
        print(f"Intenção detectada: {intent_response}")  # Log para debug
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
                "markdown_instrucoes": markdown_instrucoes,
                "configuracoes": configuracoes
            })
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body=response
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
            elif incoming_msg == "marcar_reuniao":
                estado_cliente["etapa"] = "questionario_reuniao_nome"
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Ótimo! Para marcar sua reunião, precisamos de algumas informações! 😉\nPor favor, informe o seu *nome completo*."
                )
            elif incoming_msg == "agendar_visita":
                estado_cliente["etapa"] = "questionario_visita_nome"
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Ótimo! Para agendar sua visita, precisamos de algumas informações! 😉\nPor favor, informe o seu *nome completo*."
                )
            return "OK", 200
            
    if estado_cliente["etapa"].startswith("questionario_visita"):
        if estado_cliente["etapa"] == "questionario_visita_nome":
            valido, erro = validar_informacao("nome", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente o seu nome completo."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "nome", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_idade"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Quantos *anos* você tem? _(Ex: *35*)_"
            )
        elif estado_cliente["etapa"] == "questionario_visita_idade":
            valido, erro = validar_informacao("idade", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente a sua idade."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "idade", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_cpf"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Qual é o seu *CPF*? _(XXX.XXX.XXX-XX)_"
            )
        elif estado_cliente["etapa"] == "questionario_visita_cpf":
            valido, erro = validar_informacao("cpf", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente o seu CPF."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "cpf", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_carteira"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=template_3anos
            )
        elif estado_cliente["etapa"] == "questionario_visita_carteira":
            salvar_resposta(estado_cliente, "carteira_assinada", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_estado_civil"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Qual é o seu *estado civil*?"
            )
        elif estado_cliente["etapa"] == "questionario_visita_estado_civil":
            salvar_resposta(estado_cliente, "estado_civil", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_trabalho"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=template_autonomo_registrado
            )
        elif estado_cliente["etapa"] == "questionario_visita_trabalho":
            salvar_resposta(estado_cliente, "trabalho", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_restricao"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Você sabe se tem *restrição* no CPF? _(Ex: Dívidas, Erros cadastrais)_"
            )
        elif estado_cliente["etapa"] == "questionario_visita_restricao":
            salvar_resposta(estado_cliente, "restricao_cpf", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_filhos"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=template_filhos
            )
        elif estado_cliente["etapa"] == "questionario_visita_filhos":
            salvar_resposta(estado_cliente, "filhos_menores", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_renda_bruta"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body=f"{estado_cliente['respostas'].get('nome', 'Cliente').title()}, diga-nos a sua *Renda Bruta Mensal* 💸 _(Ex: 4500,00)_"
            )
        elif estado_cliente["etapa"] == "questionario_visita_renda_bruta":
            salvar_resposta(estado_cliente, "renda_bruta", incoming_msg)
            
            # Revisar informações antes de finalizar
            validacao, resultado = validar_todas_respostas(estado_cliente["respostas"])
            if not validacao:
                for erro in resultado:
                    client.messages.create(
                        from_='whatsapp:+14155238886',
                        to=from_whatsapp_number,
                        body=f"Erro no campo '{erro['campo']}': {erro['erro']}"
                    )
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Por favor, corrija os campos acima antes de continuar."
                )
                return "OK", 200
            # Continua para o estado final se tudo estiver válido
            estado_cliente["etapa"] = "finalizado_visita"
            salvar_no_csv(estado_cliente)
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Obrigado pelas informações, a Descomplica agradece! 💚"
            )
            sleep(2)
        elif estado_cliente["etapa"] == "finalizado_visita":
            estado_cliente["etapa"] = "aguardando_agendamento"
            # Validação do horário
            horario_cliente = estado_cliente["respostas"]["horario"]
            if not validar_horario(horario_cliente):
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Ops! 😊 Os horários precisam terminar com *5 no final*. Exemplos: 10:35, 11:15, 12:45.\nPor favor, informe um horário válido."
                )
                return "OK", 200

            # Passa o controle para a IA Agendadora
            response = agendamento_chain.run({
                "message": incoming_msg,
                "dia": estado_cliente["respostas"]["dia"],
                "horario": horario_cliente
            })

            # Confirmação do agendamento
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body=response
            )
            sleep(3)
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=template_loop
            )
            return "OK", 200


    if estado_cliente["etapa"].startswith("questionario_reuniao"):
        if estado_cliente["etapa"] == "questionario_reuniao_nome":
            valido, erro = validar_informacao("nome", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente o seu nome completo."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "nome", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_idade"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Quantos *anos* você tem? _(Ex: *35*)_"
            )
        elif estado_cliente["etapa"] == "questionario_reuniao_idade":
            valido, erro = validar_informacao("idade", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(     
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente a sua idade."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "idade", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_cpf"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Qual é o seu *CPF*? _(XXX.XXX.XXX-XX)_"
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_cpf":
            valido, erro = validar_informacao("cpf", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente o seu CPF no formato XXX.XXX.XXX-XX."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "cpf", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_carteira"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=template_3anos
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_carteira":
            salvar_resposta(estado_cliente, "carteira_assinada", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_estado_civil"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Qual é o seu *estado civil*?"
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_estado_civil":
            salvar_resposta(estado_cliente, "estado_civil", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_trabalho"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=template_autonomo_registrado
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_trabalho":
            salvar_resposta(estado_cliente, "trabalho", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_restricao"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Você sabe se tem *restrição* no CPF?"
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_restricao":
            salvar_resposta(estado_cliente, "restricao_cpf", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_filhos"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=template_filhos
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_filhos":
            salvar_resposta(estado_cliente, "filhos_menores", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_renda_bruta"
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body=f"{estado_cliente['respostas'].get('nome', 'Cliente').title()}, diga-nos a sua *Renda Bruta Mensal* 💸 _(Ex: 4500,00)_"
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_renda_bruta":
            valido, erro = validar_informacao("renda_bruta", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente a sua renda bruta."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "renda_bruta", incoming_msg)
            estado_cliente["etapa"] = "finalizado_reuniao"
            salvar_no_csv(estado_cliente)
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Obrigado pelas informações, a Descomplica agradece! 💚"
            )
            sleep(2)
        elif estado_cliente["etapa"] == "finalizado_reuniao":
            estado_cliente["etapa"] = "aguardando_agendamento_reuniao"

            # Validação do horário
            horario_cliente = estado_cliente["respostas"]["horario"]
            if not validar_horario(horario_cliente):
                client.messages.create(
                    from_='whatsapp:+14155238886',
                    to=from_whatsapp_number,
                    body="Ops! 😊 Os horários precisam terminar com *5 no final*. Exemplos: 10:35, 11:15, 12:45.\nPor favor, informe um horário válido."
                )
                return "OK", 200

            # Passa o controle para a IA Agendadora
            response = agendamento_chain.run({
                "message": incoming_msg,
                "dia": estado_cliente["respostas"]["dia"],
                "horario": horario_cliente
            })

            # Confirmação do agendamento
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body=response
            )
            sleep(2)
            client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                content_sid=template_loop
            )
        return "OK", 200

    '''# Fallback
    client.messages.create(
                from_='whatsapp:+14155238886',
                to=from_whatsapp_number,
                body="Não entendi o que você quis dizer 😓\nSe estiver com alguma dificuldade digite *atendimento*"
            )'''
    return "OK", 200


@app.route('/')
def index():
    return "Funcionando!"

if __name__ == '__main__':
    app.run()