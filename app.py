from flask import Flask, request
from twilio.rest import Client 
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from dotenv import load_dotenv
import markdown
from bs4 import BeautifulSoup
import datetime
from time import sleep
from apscheduler.schedulers.background import BackgroundScheduler
import time
import re
import os
import csv
import json

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
lola_md = os.getenv("MARKDOWN_TRAINING")
lola_json = os.getenv("JSON_TRAINING")

csv_file = os.getenv("CSV_FILE")

# Configuração do Langchain
llm = ChatOpenAI(
    model="gpt-4-turbo",
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
        - Querer comprar ou dar entrada algum apartamento ou empreendimento já. "Quero dar entrada/comprar em um apartamento"

        
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
    input_variables=["message", "markdown_instrucoes", "configuracoes", "historico"],
    template="""
    Você é um assistente que identifica a intenção do cliente para um outro agente atuar.
    Você acompanha toda a conversa. Sua única função é detectar intenções relacionadas a:
    - Agradecimentos e finalização de conversa.
    "Obrigado"
    "Obrigada"
    "Valeu"
    "Gratidão"
    "Muito obrigado"
    "Muito obrigada"
    "Agradecido"
    "Agradecida"

    "Tchau"
    "Até mais"
    "Até logo"
    "Adeus"
    "Ok"
    "Beleza"
    "Acabou"
    "Já terminou?"

    - Perguntas genéricas ou irrelevantes ao fluxo.
    "O que você acha disso?"
    "Você pode me ajudar com outra coisa?"
    "Como está o tempo hoje?"
    "Você é uma pessoa?"
    "Quantos anos você tem?"

    - Solicitações de suporte geral.
    "Ajuda"
    "Suporte"
    "Tenho uma dúvida"
    "Não sei o que fazer"
    - Mensagens fora de contexto ou aleatória (Fora do escopo).
    "Me diga uma piada"
    "Só estou testando"

    - Mensagens de frustração.
    "Isso não está funcionando"
    "Não entendi"
    "Pode explicar melhor?"

    Sempre que tiver uma interrogação (?) na {message}, dê uma olhada mais profunda.

    Responda com "FALLBACK" se identificar alguma dessas intenções na mensagem.
    Caso contrário, responda com "CONTINUE_FLOW".

    ### Instruções carregadas:
    {markdown_instrucoes}

    ### Exemplos de respostas para perguntas:
    {configuracoes}

    ### Mensagem do cliente:
    Cliente: {message}

    ### Histórico de mensagens
    {historico}
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
                from_='whatsapp:+5541987526657',
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

@app.route('/bot', methods=['POST'])
def bot():
    incoming_msg = request.values.get('Body', '').strip()
    from_whatsapp_number = request.values.get('From')

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
        client.messages.create(
            from_='whatsapp:+5541987526657',
            to=from_whatsapp_number,
            body="Olá, Seja bem-vindo(a) 🏘\nAqui é a *Lare*, assistente virtual da Descomplica Lares! Como posso te ajudar?"
        )
        return "OK", 200

    estado_cliente = cliente_estado[from_whatsapp_number]

    print(f"Mensagem recebida: {incoming_msg}")

    if incoming_msg == "Desejo voltar!":
        # Reinicia o estado do cliente
        cliente_estado[from_whatsapp_number] = {"etapa": "inicial", "respostas": {}}
        
        # Envia a mensagem de boas-vindas novamente
        client.messages.create(
            from_='whatsapp:+5541987526657',
            to=from_whatsapp_number,
            body="Olá, Seja bem-vindo(a) 🏘\nAqui é a *Lare*, assistente virtual da Descomplica Lares! Como posso te ajudar?"
        )
        return "OK", 200

    if estado_cliente["etapa"] == "inicial":
        intent_response = intention_chain.run(message=incoming_msg).strip()
        print(f"Intenção detectada: {intent_response}")
        if intent_response == "PASS_BUTTON":
            estado_cliente["etapa"] = "aguardando_opcao"
            client.messages.create(
                from_='whatsapp:+5541987526657',
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
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body=response
            )
            sleep(1.5)
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="*Para continuarmos, nós trabalhamos com reuniões online ou visitas na unidade, diga-nos qual você prefere 😄*\n*Porém, se tiver mais alguma dúvida, fique à vontade!*"
            )
            return "OK", 200

    if estado_cliente["etapa"] == "aguardando_opcao":
        if incoming_msg in BUTTON_IDS:
            if incoming_msg == "infos_descomplica":
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    content_sid=template_iap
                )
                sleep(1)
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    content_sid=template_pe
                )
                sleep(3)
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    content_sid=template_loop
                )
                estado_cliente["etapa"] = "aguardando_opcao"
            elif incoming_msg == "analise_credito":
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Perfeito. Vamos te mandar algumas informações importantes para o envio de forma correta e os documentos necessários! 😎"
                )
                sleep(2)
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="""
Gostaríamos de garantir que o processo é *totalmente seguro*. A Descomplica Lares respeita e segue todas as normas estabelecidas pela *Lei Geral de Proteção de Dados (LGPD), _Lei nº 13.709/2018_*, que assegura a proteção e a privacidade dos seus dados pessoais. 
Sua privacidade é nossa prioridade, e todos os dados enviados são armazenados de forma segura e confidencial, com total responsabilidade da nossa parte. 🔒
"""
                )
                sleep(4)
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    content_sid=template_iap
                )
                sleep(2)
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Esses são os documentos que serão necessários! E aqui vai uma sugestão 😊\n\nSe um dos arquivos de seus documentos for de um tamanho muito extenso, e não for possível enviar por aqui, *nos envie pelo e-mail: descomplicalares@gmail.com*. E deixe claro no e-mail a que documento você se refere!"
                )
                sleep(2)
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Sua chamada já foi aberta! Já pode enviar os seus documentos que um corretor já entrará em contato para te auxiliar! 🧡💜"
                )
                sleep(2)
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    content_sid=template_loop
                )
            elif incoming_msg == "marcar_reuniao":
                estado_cliente["etapa"] = "questionario_reuniao_nome"
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Ótimo! Para marcar sua reunião, precisamos de algumas informações. Vai levar só 3 minutinhos 😉\nPor favor, informe o seu *nome completo*."
                )
            elif incoming_msg == "agendar_visita":
                estado_cliente["etapa"] = "questionario_visita_nome"
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Ótimo! Para agendar sua visita, precisamos de algumas informações! Vai levar só 3 minutinhos 😉\nPor favor, informe o seu *nome completo*."
                )
            return "OK", 200
    
    questionario_etapas = {
        "questionario_reuniao_nome", "questionario_reuniao_nome", 
        "questionario_visita_idade", "questionario_reuniao_idade",
        "questionario_visita_cpf", "questionario_reuniao_cpf",
        "questionario_visita_carteira", "questionario_reuniao_carteira",
        "questionario_visita_estado_civil", "questionario_reuniao_estado_civil",
        "questionario_visita_trabalho", "questionario_reuniao_trabalho",
        "questionario_visita_restricao", "questionario_reuniao_restricao",
        "questionario_visita_filhos", "questionario_reuniao_filhos",
        "questionario_visita_renda_bruta", "questionario_reuniao_renda_bruta",
        "finalizado_tudo", "finalizado_visita", "aguardando_opcao"
    }
            
    if estado_cliente["etapa"].startswith("questionario_visita"):
        if estado_cliente["etapa"] == "questionario_visita_nome":
            valido, erro = validar_informacao("nome", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente o seu nome completo."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "nome", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_idade"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Quantos *anos* você tem? _(Ex: *35*)_"
            )
        elif estado_cliente["etapa"] == "questionario_visita_idade":
            valido, erro = validar_informacao("idade", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente a sua idade."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "idade", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_cpf"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Qual é o seu *CPF*? _(XXX.XXX.XXX-XX)_"
            )
        elif estado_cliente["etapa"] == "questionario_visita_cpf":
            valido, erro = validar_informacao("cpf", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente o seu CPF."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "cpf", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_carteira"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                content_sid=template_3anos
            )
        elif estado_cliente["etapa"] == "questionario_visita_carteira":
            salvar_resposta(estado_cliente, "carteira_assinada", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_estado_civil"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Qual é o seu *estado civil*?"
            )
        elif estado_cliente["etapa"] == "questionario_visita_estado_civil":
            salvar_resposta(estado_cliente, "estado_civil", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_trabalho"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                content_sid=template_autonomo_registrado
            )
        elif estado_cliente["etapa"] == "questionario_visita_trabalho":
            salvar_resposta(estado_cliente, "trabalho", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_restricao"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Você sabe se tem *restrição* no CPF? _(Ex: Dívidas, Erros cadastrais)_"
            )
        elif estado_cliente["etapa"] == "questionario_visita_restricao":
            salvar_resposta(estado_cliente, "restricao_cpf", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_filhos"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                content_sid=template_filhos
            )
        elif estado_cliente["etapa"] == "questionario_visita_filhos":
            salvar_resposta(estado_cliente, "filhos_menores", incoming_msg)
            estado_cliente["etapa"] = "questionario_visita_renda_bruta"
            client.messages.create(
                from_='whatsapp:+5541987526657',
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
                        from_='whatsapp:+5541987526657',
                        to=from_whatsapp_number,
                        body=f"Erro no campo '{erro['campo']}': {erro['erro']}"
                    )
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Por favor, corrija os campos acima antes de continuar."
                )
                return "OK", 200
            # Continua para o estado final se tudo estiver válido
            salvar_no_csv(estado_cliente)
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Obrigado pelas informações, a Descomplica agradece! 🧡💜"
            )   
            sleep(1.5)
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Qual o melhor horário para você visitar? 😊 Os horários disponíveis são de _*Segunda a Sábado das 09:00 às 20:00 e Domingo das 09:00 às 12:00.*_ \nPor favor, escolha um horário terminando com *5 no final* _(Ex: 10:35, 11:15)_"
            )
            estado_cliente["etapa"] = "finalizado_visita"
    elif estado_cliente["etapa"] == "finalizado_visita":
        client.messages.create(
        from_='whatsapp:+5541987526657',
        to=from_whatsapp_number,
        body="Horário agendado! ⌚\n*Um corretor entrará em contato para confirmar os detalhes!*"
        )
        sleep(2.5)
        client.messages.create(
        from_='whatsapp:+5541987526657',
        to=from_whatsapp_number,
        body="""
Estarei te passando uma lista de documentos que você pode trazer e uma confirmação de agendamento! 🏡\n
*É muito importante seu comparecimento, terá um corretor e gerente aguardando você pra te ajudar no processo de financiamento com a _CAIXA ECONÔMICA FEDERAL_ e visualização do portfólio dos imóveis!*
"""
        ) 
        sleep(3)

        client.messages.create(
            from_='whatsapp:+5541987526657',
            to=from_whatsapp_number,
            content_sid=template_iap
        )
        sleep(3)

        client.messages.create(
            from_='whatsapp:+5541987526657',
            to=from_whatsapp_number,
            content_sid=template_pe
        )

        # Estado final
        estado_cliente["etapa"] = "encerrado"
        sleep(2)
        client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    content_sid=template_loop
                )
        return "OK", 200


    if estado_cliente["etapa"].startswith("questionario_reuniao"):
        if estado_cliente["etapa"] == "questionario_reuniao_nome":
            valido, erro = validar_informacao("nome", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente o seu nome completo."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "nome", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_idade"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Quantos *anos* você tem? _(Ex: *35*)_"
            )
        elif estado_cliente["etapa"] == "questionario_reuniao_idade":
            valido, erro = validar_informacao("idade", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(     
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente a sua idade."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "idade", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_cpf"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Qual é o seu *CPF*? _(XXX.XXX.XXX-XX)_"
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_cpf":
            valido, erro = validar_informacao("cpf", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente o seu CPF no formato XXX.XXX.XXX-XX."
                )
                return "OK", 200
            salvar_resposta(estado_cliente, "cpf", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_carteira"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                content_sid=template_3anos
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_carteira":
            salvar_resposta(estado_cliente, "carteira_assinada", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_estado_civil"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Qual é o seu *estado civil*?"
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_estado_civil":
            salvar_resposta(estado_cliente, "estado_civil", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_trabalho"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                content_sid=template_autonomo_registrado
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_trabalho":
            salvar_resposta(estado_cliente, "trabalho", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_restricao"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Você sabe se tem *restrição* no CPF? _(Ex: Dívidas, Erros cadastrais)_"
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_restricao":
            salvar_resposta(estado_cliente, "restricao_cpf", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_filhos"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                content_sid=template_filhos
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_filhos":
            salvar_resposta(estado_cliente, "filhos_menores", incoming_msg)
            estado_cliente["etapa"] = "questionario_reuniao_renda_bruta"
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body=f"{estado_cliente['respostas'].get('nome', 'Cliente').title()}, diga-nos a sua *Renda Bruta Mensal* 💸 _(Ex: 4500,00)_"
            )

        elif estado_cliente["etapa"] == "questionario_reuniao_renda_bruta":
            valido, erro = validar_informacao("renda_bruta", incoming_msg)
            if not valido:
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body=erro
                )
                client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    body="Por favor, informe novamente a sua renda bruta."
                )
                return "OK", 200
            
            salvar_resposta(estado_cliente, "renda_bruta", incoming_msg)
            salvar_no_csv(estado_cliente)
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body="Obrigado pelas informações, a Descomplica agradece! 🧡💜"
            )
            sleep(2)
            estado_cliente["etapa"] = "finalizado_reuniao"
    if estado_cliente["etapa"] == "finalizado_reuniao":
        client.messages.create(
            from_='whatsapp:+5541987526657',
            to=from_whatsapp_number,
            body="*Sua chamada já foi aberta, em breve um corretor entrará em contato para confirmar os detalhes dessa reunião! ✅*"
            )
        sleep(2)

        client.messages.create(
        from_='whatsapp:+5541987526657',
        to=from_whatsapp_number,
        body="*Antes temos alguns pontos importantes a salientar...*\n\n  • Reunião será _online_, como videochamada 🖥\n  • Você falará com um de nossos corretores, *já tenha alguns documentos em mãos, para possíveis verificações! 😎*"
        )

        estado_cliente["etapa"] = "finalizado_tudo"
        sleep(2)

        client.messages.create(
                    from_='whatsapp:+5541987526657',
                    to=from_whatsapp_number,
                    content_sid=template_loop
                )
    

    if estado_cliente["etapa"] in questionario_etapas:
        fallback_response = fallback_chain.run(message=incoming_msg).strip()
        print(f"Intenção detectada: {fallback_response}")  # Log para debug

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

        if fallback_response == "FALLBACK":
            response_fallback = conversation_chain.run({
                        "message": incoming_msg,
                        "historico": historico,
                        "markdown_instrucoes": markdown_instrucoes,
                        "configuracoes": configuracoes
                    })
            
            client.messages.create(
                from_='whatsapp:+5541987526657',
                to=from_whatsapp_number,
                body=response_fallback
                )
            return "OK", 200
        return "OK", 200
    return "OK", 200


@app.route('/')
def index():
    return "Funcionando 2024!"

if __name__ == '__main__':
    app.run()