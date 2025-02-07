from app import app
import os

if __name__ == '__main__':
    # Configurações de desenvolvimento
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = '1'
    
    # Executa o Flask com hot reload
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True,
        threaded=True
    ) 