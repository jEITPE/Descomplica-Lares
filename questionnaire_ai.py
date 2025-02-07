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
            Você é a Lola, assistente virtual da Descomplica Lares, especializada em responder dúvidas sobre o processo de compra de imóveis.
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
            input_variables=["message", "current_question", "context"],
            template="""
            Você é um assistente especializado em identificar quando um usuário está fazendo uma pergunta ou tem uma dúvida
            durante um questionário, em vez de responder à pergunta que foi feita.

            Pergunta atual: {current_question}
            Contexto da conversa: {context}
            Mensagem do usuário: {message}

            REGRAS ESTRITAS DE DETECÇÃO:
            1. Se a mensagem contém uma interrogação (?), DEVE ser "FALLBACK"
            2. Se a mensagem começa com palavras interrogativas (qual, como, onde, quando, por que, quem), DEVE ser "FALLBACK"
            3. Se a mensagem expressa dúvida (ex: "não entendi", "não sei", "pode explicar"), DEVE ser "FALLBACK"
            4. Se a mensagem pede informações adicionais ou esclarecimentos, DEVE ser "FALLBACK"
            5. Se a mensagem é uma resposta direta à pergunta atual (mesmo que incorreta), responda "CONTINUE"
            6. Se a mensagem é uma saudação ou agradecimento simples (ex: "ok", "obrigado"), responda "CONTINUE"
            7. Se a mensagem menciona termos não presentes na pergunta atual (ex: pergunta sobre idade mas mensagem fala de dinheiro), DEVE ser "FALLBACK"

            EXEMPLOS ESPECÍFICOS:
            - Pergunta: "Qual é o seu CPF?"
              FALLBACK: "Como faço para tirar CPF?"
              FALLBACK: "Precisa ser o meu CPF?"
              FALLBACK: "Pode ser o CPF do meu marido?"
              CONTINUE: "Não tenho aqui agora"
              CONTINUE: "123.456.789-10"
            
            - Pergunta: "Qual é a sua idade?"
              FALLBACK: "Qual idade mínima?"
              FALLBACK: "Por que precisa da idade?"
              FALLBACK: "E se eu tiver menos?"
              CONTINUE: "tenho 25"
              CONTINUE: "35 anos"

            - Pergunta: "Você tem carteira assinada há mais de 3 anos?"
              FALLBACK: "Precisa ser carteira assinada?"
              FALLBACK: "E se for menos tempo?"
              FALLBACK: "Como comprovo isso?"
              CONTINUE: "Sim"
              CONTINUE: "Não, só tenho 2 anos"

            - Pergunta: "Qual é a sua Renda Bruta Mensal?"
              FALLBACK: "O que é renda bruta?"
              FALLBACK: "Pode incluir hora extra?"
              FALLBACK: "Precisa de comprovante?"
              CONTINUE: "4500"
              CONTINUE: "Ganho 3000 por mês"

            IMPORTANTE: Se houver QUALQUER dúvida se é uma pergunta ou não, escolha "FALLBACK".
            
            Responda apenas com "CONTINUE" ou "FALLBACK".
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
        
        # Carrega json se fornecido
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
            response = self.answer_chain.run({
                "question": question,
                "knowledge_base": self.knowledge_base,
                "current_field": current_field
            })
            return response.strip()
        except Exception as e:
            print(f"Erro ao buscar resposta: {e}")
            return None

    def process_message(self, message):
        """Processa a mensagem do usuário e retorna uma resposta apropriada"""
        return self.process_message_new(message)

    def process_message_new(self, message):
        """Processa a mensagem do usuário e retorna uma resposta apropriada"""
        try:
            # Adiciona a mensagem ao histórico
            self.conversation_history.append({"role": "user", "content": message})
            
            # Lógica básica de resposta
            message = message.lower().strip()
            
            # Perguntas sobre localização
            if any(word in message for word in ["onde", "local", "endereço", "localizado", "fica"]):
                response = """Nossa unidade está localizada em:
                
🏢 Rua Voluntários da Pátria, 654 - Sala 1208
Santana, São Paulo - SP
CEP: 02010-000

Próximo ao metrô Santana! 🚇"""
            
            # Perguntas sobre horário de funcionamento
            elif any(word in message for word in ["horário", "hora", "funcionamento", "aberto"]):
                response = """Nosso horário de atendimento é:

⏰ Segunda a Sexta: 09h às 18h
⏰ Sábado: 09h às 13h

Agende uma visita ou reunião online! 😊"""
            
            # Perguntas sobre financiamento
            elif any(word in message for word in ["financiamento", "parcela", "valor", "preço"]):
                response = """Trabalhamos com financiamento pela Caixa Econômica Federal! 🏦

Para simular valores e condições, precisamos de algumas informações:
1. Renda familiar
2. Valor de entrada disponível
3. Tipo de imóvel desejado

Podemos agendar uma reunião para fazer essa simulação? 📊"""
            
            # Resposta padrão
            else:
                response = """Posso te ajudar com:

1. Informações sobre nossos imóveis 🏠
2. Simulação de financiamento 💰
3. Agendamento de visitas 📅
4. Documentação necessária 📄

Como posso te ajudar?"""
            
            # Adiciona a resposta ao histórico
            self.conversation_history.append({"role": "assistant", "content": response})
            
            return response
            
        except Exception as e:
            return "Desculpe, tive um problema ao processar sua mensagem. Pode tentar novamente?"
        
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
        # Limpa e valida os dados
        cleaned_data = self.clean_and_validate_data(respostas)
        
        headers = list(self.questions.keys()) + ["dia", "horario"]
        data = {field: cleaned_data.get(field, "") for field in headers}
        
        file_exists = os.path.isfile(self.csv_file_path)
        
        with open(self.csv_file_path, "a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow(data) 