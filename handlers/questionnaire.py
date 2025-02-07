def handle_questionnaire(client_state, message, from_number):
    stage = client_state.get_stage()
    
    if stage == "questionario_reuniao_nome":
        return handle_name_question(client_state, message, from_number)
    elif stage == "questionario_reuniao_idade":
        return handle_age_question(client_state, message, from_number)
    # ... outros handlers ... 