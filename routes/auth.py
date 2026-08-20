import os
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Blueprint, redirect, url_for, session, request, current_app
from authlib.integrations.flask_client import OAuth
from flask_mail import Message, Mail

auth_bp = Blueprint('auth', __name__)

oauth = OAuth()

def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

def send_new_user_email(app, user_email, user_name):
    mail = Mail(app)
    admin_email = os.environ.get('ADMIN_EMAIL')
    sender_email = os.environ.get('MAIL_USERNAME')
    
    if not admin_email or not sender_email:
        return

    msg = Message(
        subject="🚀 Nouvel utilisateur inscrit sur Sunwi !",
        sender=sender_email,
        recipients=[admin_email],
        body=f"Un nouvel utilisateur vient de se connecter pour la première fois à Sunwi :\n\nNom : {user_name}\nEmail : {user_email}"
    )
    try:
        with app.app_context():
            mail.send(msg)
    except Exception as e:
        print(f"⚠️ Erreur d'envoi du mail de notification : {e}")

@auth_bp.route('/login/google')
def google_login():
    redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/auth/callback')
    return oauth.google.authorize_redirect(redirect_uri)

@auth_bp.route('/auth/callback')
def google_callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if not user_info:
        return redirect(url_for('main.hub'))

    google_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name', 'Utilisateur')
    db_user_id = None

    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        try:
            conn = psycopg2.connect(db_url, sslmode='require')
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Vérifier si l'utilisateur existe déjà
            cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
            existing_user = cur.fetchone()

            if not existing_user:
                # Première connexion : enregistrement en BDD Neon
                cur.execute(
                    "INSERT INTO users (email, display_name, google_id) VALUES (%s, %s, %s) RETURNING id;",
                    (email, name, google_id)
                )
                db_user_id = cur.fetchone()['id']
                conn.commit()
                
                # Envoi asynchrone du mail de notification
                app_obj = current_app._get_current_object()
                threading.Thread(
                    target=send_new_user_email, 
                    args=(app_obj, email, name), 
                    daemon=True
                ).start()
            else:
                db_user_id = existing_user['id']

            cur.close()
            conn.close()
        except Exception as e:
            print(f"⚠️ Erreur BDD authentification Google : {e}")

    # Enregistrement dans la session Flask avec l'ID BDD Neon
    session['sunwi_user'] = {
        'id': db_user_id,
        'google_id': google_id,
        'email': email,
        'name': name,
        'picture': user_info.get('picture')
    }

    return redirect(url_for('main.hub'))

@auth_bp.route('/logout')
def logout():
    session.pop('sunwi_user', None)
    session.pop('user_profile', None)
    return redirect(url_for('main.index'))