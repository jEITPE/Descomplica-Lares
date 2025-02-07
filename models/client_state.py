class ClientState:
    def __init__(self):
        self.state = {"etapa": "inicial", "respostas": {}}
        
    def save_response(self, field, value):
        if "respostas" not in self.state:
            self.state["respostas"] = {}
        self.state["respostas"][field] = value
        
    def get_stage(self):
        return self.state["etapa"]
        
    def set_stage(self, stage):
        self.state["etapa"] = stage
        
    def get_responses(self):
        return self.state.get("respostas", {}) 