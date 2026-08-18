# app.py
import os
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from flask_session import Session
from flask_mail import Mail
from db import init_global_db
from routes.main import main_bp
from routes.spotify import spotify_bp
from routes.auth import auth_bp, init_oauth
from routes.football import football_bp
from routes.pokemon import pokemon_bp
from routes.music import music_bp

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'une_cle_secrete_super_securisee_elotify_12345')

# Configuration Mail
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
Mail(app)

# Session configuration
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
Session(app)

# Initialisation de la BDD globale & OAuth Google
init_global_db()
init_oauth(app)

# Enregistrement des Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(spotify_bp, url_prefix='/spotify')
app.register_blueprint(auth_bp)
app.register_blueprint(football_bp)
app.register_blueprint(pokemon_bp)
app.register_blueprint(music_bp, url_prefix='/music')

@app.after_request
def add_header(response):
    """
    Force le navigateur à ne pas mettre en cache les pages.
    En appuyant sur "Précédent", le navigateur redemande la page au serveur
    au lieu de rejouer le formulaire/l'état en cache.
    """
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)