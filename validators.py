import re

class InputValidator:
    @staticmethod
    def validate_name(name):
        if len(name.split()) < 2:
            return False, "O nome deve conter pelo menos dois nomes"
        return True, None
        
    @staticmethod 
    def validate_cpf(cpf):
        if not re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", cpf):
            return False, "CPF inválido"
        return True, None 

class QuestionnaireValidator:
    @staticmethod
    def validate_questionnaire_response(message, stage):
        validators = {
            "questionario_reuniao_nome": lambda m: (
                len(m.split()) >= 2 and 
                all(part.isalpha() for part in m.split()) and
                len(m) >= 5
            ),
            "questionario_reuniao_idade": lambda m: (
                m.replace(" ", "").isdigit() and 
                18 <= int(m) <= 100
            ),
            "questionario_reuniao_cpf": lambda m: bool(re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", m)),
            "questionario_reuniao_carteira": lambda m: any(
                word.lower() in m.lower() 
                for word in ["sim", "não", "nao", "tenho", "não tenho"]
            ),
            "questionario_reuniao_estado_civil": lambda m: any(
                word.lower() in m.lower() 
                for word in ["solteiro", "casado", "divorciado", "viúvo", "separado"]
            ),
            "questionario_reuniao_renda_bruta": lambda m: (
                bool(re.match(r"^R?\$?\s*\d+[.,]?\d*$", m.replace(" ", ""))) and
                float(m.replace("R$", "").replace(".", "").replace(",", ".").strip()) > 0
            )
        }
        return validators.get(stage, lambda _: True)(message) 