from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import json
import csv
import os
import re

class QuestionnaireAI:
    def __init__(self, api_key, csv_file_path, markdown_path=None, json_path=None):
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            max_tokens=130,
            temperature=0.2,
            top_p=0.7,
            frequency_penalty=0.5,
            presence_penalty=0.0,
            openai_api_key=api_key
        )
        self.csv_file_path = csv_file_path
        
        # Carrega o conhecimento do treinamento
        self.knowledge_base = self.load_knowledge_base(markdown_path, json_path)
        
        # Prompt para responder perguntas usando o conhecimento base
        self.answer_prompt = PromptTemplate(
            input_variables=["question", "knowledge_base", "current_field"],
            template="""
            Você é a Lare, assistente virtual da Descomplica Lares, especializada em responder dúvidas sobre o processo de compra de imóveis.
            Use a base de conhecimento fornecida para responder à pergunta do usuário de forma amigável e prestativa.

            Base de Conhecimento:
            {knowledge_base}

            Contexto atual: O usuário está respondendo perguntas sobre {current_field}
            Pergunta do usuário: {question}

            Regras para resposta:
            1. Seja direta e objetiva, mas mantenha um tom amigável
            2. Use emojis para tornar a resposta mais acolhedora
            3. Se a resposta estiver na base de conhecimento, use-a como referência
            4. Se não tiver certeza, diga algo como "Não tenho essa informação específica, mas posso chamar um corretor para te ajudar melhor! 😊"
            5. Após responder a dúvida, incentive a continuar o formulário
            6. Mantenha as respostas curtas e diretas

            Exemplos de respostas:
            - Para dúvidas sobre idade: "A idade mínima é 18 anos! 😊 Podemos continuar com o formulário?"
            - Para dúvidas sobre documentos: "Você precisará de RG, CPF e comprovante de residência! 📄 Vamos continuar?"
            - Para dúvidas sobre restrições: "Sim, é possível dar entrada mesmo com algumas restrições! Cada caso é analisado individualmente 🤝"

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

        Responda as perguntas normalmente, sem 'Lola:'.


            Responda de forma natural e amigável:
            """
        )
        self.answer_chain = LLMChain(llm=self.llm, prompt=self.answer_prompt)
        
        self.questions = {
            "nome": {
                "pergunta": "Por favor, informe o seu *nome completo*.",
                "validacao": lambda x: len(x.split()) >= 2,
                "erro": "O nome deve conter pelo menos dois nomes (nome e sobrenome)."
            },
            "idade": {
                "pergunta": "Quantos *anos* você tem? _(Ex: *35*)_",
                "validacao": lambda x: x.isdigit(),
                "erro": "A idade deve ser um número inteiro válido."
            },
            "cpf": {
                "pergunta": "Qual é o seu *CPF*? _(XXX.XXX.XXX-XX)_",
                "validacao": lambda x: bool(re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", x)),
                "erro": "O CPF deve estar no formato XXX.XXX.XXX-XX."
            },
            "carteira_assinada": {
                "pergunta": "Você tem carteira assinada há mais de 3 anos?",
                "template_id": "template_3anos"
            },
            "estado_civil": {
                "pergunta": "Qual é o seu *estado civil*?"
            },
            "trabalho": {
                "pergunta": "Você é registrado ou autônomo?",
                "template_id": "template_autonomo_registrado"
            },
            "restricao_cpf": {
                "pergunta": "Você sabe se tem *restrição* no CPF? _(Ex: Dívidas, Erros cadastrais)_"
            },
            "filhos_menores": {
                "pergunta": "Você tem filhos menores de idade?",
                "template_id": "template_filhos"
            },
            "renda_bruta": {
                "pergunta": "Qual é a sua *Renda Bruta Mensal* 💸 _(Ex: 4500,00)_",
                "validacao": lambda x: bool(re.match(r"^\d+([.,]\d{2})?$", x.replace("R$", "").strip())),
                "erro": "A renda bruta deve ser um valor numérico válido (Ex: 4500,00)."
            },
            "dia": {
                "pergunta": "Qual dia você gostaria de visitar? _(Ex: 25/03)_",
                "validacao": lambda x: bool(re.match(r"^(0?[1-9]|[12][0-9]|3[01])/(0?[1-9]|1[0-2])$", x)),
                "erro": "A data deve estar no formato DD/MM (ex: 25/03)."
            },
            "horario": {
                "pergunta": "Qual o melhor horário para você visitar? 😊 Os horários disponíveis são de _*Segunda a Sábado das 09:00 às 20:00 e Domingo das 09:00 às 12:00.*_ \nPor favor, escolha um horário terminando com *5 no final* _(Ex: 10:35, 11:15)_",
                "validacao": lambda x: bool(re.match(r"^([0-1]?[0-9]|2[0-3]):[0-5]5$", x)),
                "erro": "O horário deve estar no formato HH:MM e terminar com 5 (ex: 10:35, 11:15)."
            }
        }
        
        self.fallback_prompt = PromptTemplate(
            input_variables=["message", "current_question", "context", "historico", "last_question", "current_stage"],
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
            """
        )
        self.fallback_chain = LLMChain(llm=self.llm, prompt=self.fallback_prompt)
        
        # Definindo a ordem das perguntas
        self.question_order = [
            "nome",
            "idade",
            "cpf",
            "carteira_assinada",
            "estado_civil",
            "trabalho",
            "restricao_cpf",
            "filhos_menores",
            "renda_bruta"
        ]
        
        # Ordem específica para visita
        self.visita_order = self.question_order + ["dia", "horario"]
        
        self.conversation_history = []
        self.current_context = {}
        
    def load_knowledge_base(self, markdown_path, json_path):
        """Carrega e combina o conhecimento do markdown e json"""
        knowledge = ""
        
        # Carrega markdown se fornecido
        if markdown_path and os.path.exists(markdown_path):
            try:
                with open(markdown_path, 'r', encoding='utf-8') as f:
                    knowledge += f.read() + "\n\n"
            except Exception as e:
                print(f"Erro ao carregar markdown: {e}")
        
        # Carrega json se fornecido para o treinamento
        if json_path and os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                    # Formata as perguntas e respostas do JSON
                    for qa in json_data.get("treinamento", []):
                        knowledge += f"Pergunta: {qa['pergunta']}\nResposta: {qa['resposta']}\n\n"
            except Exception as e:
                print(f"Erro ao carregar json: {e}")
        
        return knowledge

    def get_answer_from_knowledge_base(self, question, current_field=""):
        """Busca uma resposta na base de conhecimento"""
        try:
            response = self.answer_chain.invoke(
                input={
                "question": question,
                "knowledge_base": self.knowledge_base,
                "current_field": current_field
            })
            return response
        except Exception as e:
            print(f"Erro ao buscar resposta: {e}")
            return None

    def process_message(self, message, current_field, historico=""):
        """Processa a mensagem do usuário e retorna uma resposta apropriada"""
        try:
            # Verifica se é uma pergunta ou dúvida usando o fallback_chain
            fallback_response = self.fallback_chain.invoke({
                "message": message,
                "current_question": self.questions[current_field]["pergunta"],
                "context": historico,
                "last_question": self.questions[current_field]["pergunta"],
                "current_stage": current_field
            })
            fallback_result = str(fallback_response.get('text', '')).strip()
            
            if fallback_result == "FALLBACK":
                # Se for uma dúvida, busca resposta na base de conhecimento
                answer = self.get_answer_from_knowledge_base(message, current_field)
                if answer:
                    return {
                        "type": "fallback",
                        "message": answer
                    }
                else:
                    return {
                        "type": "fallback",
                        "message": "Desculpe, não entendi sua dúvida. Pode reformular? 😊"
                    }
            
            # Se não for fallback, valida a resposta
            if current_field in self.questions and "validacao" in self.questions[current_field]:
                is_valid = self.questions[current_field]["validacao"](message)
                if not is_valid:
                    return {
                        "type": "error",
                        "message": self.questions[current_field]["erro"]
                    }
            
            # Se passou pela validação, retorna sucesso
            return {
                "type": "success",
                "field": current_field,
                "value": message
            }
            
        except Exception as e:
            print(f"Erro ao processar mensagem: {e}")
            return {
                "type": "error",
                "message": "Desculpe, tive um problema ao processar sua mensagem. Pode tentar novamente?"
            }

    def process_message_new(self, message):
        """Método legado mantido para compatibilidade"""
        return self.process_message(message, "geral", "")
        
    def get_first_question(self, tipo_questionario="reuniao"):
        """Retorna a primeira pergunta do questionário"""
        field = self.question_order[0]
        return {
            "field": field,
            "question": self.questions[field]["pergunta"],
            "template_id": self.questions[field].get("template_id")
        }
        
    def get_next_question(self, current_field, tipo_questionario="reuniao"):
        """Retorna a próxima pergunta baseada na ordem definida"""
        order = self.visita_order if tipo_questionario == "visita" else self.question_order
        try:
            current_index = order.index(current_field)
            if current_index + 1 < len(order):
                next_field = order[current_index + 1]
                return {
                    "field": next_field,
                    "question": self.questions[next_field]["pergunta"],
                    "template_id": self.questions[next_field].get("template_id")
                }
        except ValueError:
            pass
        return None
        
    def clean_and_validate_data(self, respostas):
        """Limpa e valida os dados antes de salvar"""
        cleaned_data = {}
        for field, value in respostas.items():
            # Remove espaços extras
            value = value.strip()
            
            # Formatação específica por campo
            if field == "cpf":
                # Remove qualquer caractere não numérico
                value = re.sub(r'[^\d]', '', value)
                # Formata o CPF
                value = f"{value[:3]}.{value[3:6]}.{value[6:9]}-{value[9:]}"
            elif field == "renda_bruta":
                # Remove R$ e espaços
                value = value.replace("R$", "").strip()
                # Garante duas casas decimais
                if "," in value:
                    value = value.replace(".", "").replace(",", ".")
                if "." not in value:
                    value = value + ".00"
                elif len(value.split(".")[1]) == 1:
                    value = value + "0"
            elif field in ["nome", "estado_civil"]:
                # Capitaliza nomes próprios
                value = value.title()
            elif field == "horario":
                # Garante formato HH:MM
                if len(value.split(":")[0]) == 1:
                    value = "0" + value
            
            cleaned_data[field] = value
        return cleaned_data
        
    def save_to_csv(self, respostas):
        # Cria o diretório se não existir
        os.makedirs(os.path.dirname(self.csv_file_path), exist_ok=True)

        # Limpa e valida os dados
        cleaned_data = self.clean_and_validate_data(respostas)

        headers = list(self.questions.keys()) + ["dia", "horario"]
        data = {field: cleaned_data.get(field, "") for field in headers}

        file_exists = os.path.isfile(self.csv_file_path)

        with open(self.csv_file_path, "a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            if not file_exists:
                writer.writeheader()  # Garante que o cabeçalho é escrito apenas uma vez
            writer.writerow(data)
        
        print(f"✅ Dados salvos no CSV: {data}")
 