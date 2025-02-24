import pandas as pd
import logging

def load_dashboard_data(csv_path):
    try:
        # Carregar dados do CSV
        df = pd.read_csv(csv_path)
        
        # Normalizar nomes das colunas
        df.columns = df.columns.str.strip()
        
        # Mapeamento atualizado com as colunas corretas do CSV
        column_mapping = {
            'nome': 'Nome',
            'idade': 'Idade',
            'cpf': 'CPF',
            'experiência > 3 anos': 'Experiência > 3 anos?',
            'estado civil': 'Estado Civil',
            'tipo de trabalho': 'Tipo de Trabalho',
            'restrição no cpf?': 'Restrição no CPF?',
            'filhos menores?': 'Filhos Menores?',
            'renda bruta mensal': 'Renda Bruta Mensal',
            # Aliases adicionais para flexibilidade
            'experiencia_3_anos': 'Experiência > 3 anos?',
            'estado_civil': 'Estado Civil',
            'tipo_trabalho': 'Tipo de Trabalho',
            'restricao_cpf': 'Restrição no CPF?',
            'filhos_menores': 'Filhos Menores?',
            'renda_bruta': 'Renda Bruta Mensal'
        }
        
        # Renomear colunas
        df = df.rename(columns=lambda x: column_mapping.get(x.lower(), x))
        
        # Validar que todas as colunas necessárias estão presentes
        required_columns = [
            'Nome', 'Idade', 'CPF', 'Experiência > 3 anos?',
            'Estado Civil', 'Tipo de Trabalho', 'Restrição no CPF?',
            'Filhos Menores?', 'Renda Bruta Mensal'
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logging.error(f"Colunas ausentes no CSV: {missing_columns}")
            return None
            
        if df.empty:
            logging.error("DataFrame vazio após carregar dados")
            return None
            
        return df
        
    except Exception as e:
        logging.error(f"Erro ao carregar dados: {str(e)}")
        return None
