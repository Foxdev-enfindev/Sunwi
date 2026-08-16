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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)