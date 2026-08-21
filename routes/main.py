# routes/main.py
import os
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

main_bp = Blueprint('main', __name__)

SPOTIFY_WHITELIST = ["florent.pennarun@gmail.com", "riche-angelique@gmail.com", "dgo29fcb@gmail.com", "riche.angelique@gmail.com", "foxpapa@gmail.com"]

EMAIL_ALIASES = {
    "foxpapa@gmail.com": "florent.pennarun@gmail.com",
}

@main_bp.route('/')
def index():
    if session.get('sunwi_user') or session.get('user_profile'):
        return redirect(url_for('main.hub'))
    return render_template('landing.html')

@main_bp.route('/hub')
def hub():
    if not session.get('sunwi_user') and not session.get('user_profile'):
        return redirect(url_for('main.index'))

    modules = [
        # --- SPORT ---
        {'id': 'football_top500', 'title': 'Football (Top 500)', 'category': 'Sport', 'badge': 'Disponible', 'active': True, 'url': '/football/'},
        {'id': 'football_leagues', 'title': 'Football (Par championnat)', 'category': 'Sport', 'badge': 'Disponible', 'active': True, 'url': '#'},
        {'id': 'nba', 'title': 'NBA', 'category': 'Sport', 'badge': 'Disponible', 'active': True, 'url': '/nba/'},
        {'id': 'f1', 'title': 'F1', 'category': 'Sport', 'badge': 'Disponible', 'active': True, 'url': '#'},  

        # --- PERSONNEL ---
        {'id': 'spotify', 'title': 'Musique (Spotify)', 'category': 'Personnel (Nécessite une connexion externe)', 'badge': 'Disponible', 'active': True, 'url': '/spotify/'},
        {'id': 'steam', 'title': 'Steam', 'category': 'Personnel (Nécessite une connexion externe)', 'badge': 'Bientôt', 'active': False, 'url': '#'},

        # --- GAMING ---
        {'id': 'pokemon_global', 'title': 'Pokémon (Global)', 'category': 'Gaming', 'badge': 'Disponible', 'active': True, 'url': '/pokemon/'},
        {'id': 'pokemon_generations', 'title': 'Pokémon (Par génération)', 'category': 'Gaming', 'badge': 'Disponible', 'active': True, 'url': '#'},
        {'id': 'pokemon_types', 'title': 'Pokémon (Par type)', 'category': 'Gaming', 'badge': 'Disponible', 'active': True, 'url': '#'},
        {'id': 'lol_global', 'title': 'League of Legends (Global)', 'category': 'Gaming', 'badge': 'Disponible', 'active': True, 'url': '/lol/'},
        {'id': 'lol_roles', 'title': 'League of Legends (Par rôle)', 'category': 'Gaming', 'badge': 'Disponible', 'active': True, 'url': '#'},
        {'id': 'genshin', 'title': 'Genshin Impact', 'category': 'Gaming', 'badge': 'Disponible', 'active': True, 'url': '/genshin/'},
        
        # --- MUSIQUE ---
        {'id': 'music_top100', 'title': 'Top 100 Kpop (Par année)', 'category': 'Musique', 'badge': 'Disponible', 'active': True, 'url': '/music/'},

        # --- CINÉMA ---
        {'id': 'disney', 'title': 'Films Disney', 'category': 'Cinéma', 'badge': 'Bientôt', 'active': True, 'url': '/disney/'}
    ]

    user = session.get('sunwi_user', {})
    user_email = user.get('email')
    
    if not user_email or user_email not in SPOTIFY_WHITELIST:
        modules = [m for m in modules if m['id'] not in ['spotify', 'spotify_custom_create']]

    category_order = ['Sport', 'Gaming', 'Musique', 'Cinéma', 'Personnel (Nécessite une connexion externe)']

    grouped = {}
    for m in modules:
        grouped.setdefault(m['category'], []).append(m)

    ordered_categories = [
        {'name': cat, 'modules': grouped[cat]}
        for cat in category_order if cat in grouped
    ]

    return render_template('hub.html', categories=ordered_categories)

@main_bp.route('/profile')
def profile():
    sunwi_user = session.get('sunwi_user') or {}
    spotify_user = session.get('spotify_user_profile') or session.get('user_profile') or {}

    if not sunwi_user and not spotify_user:
        return redirect(url_for('main.index'))

    # 1. Collecte et résolution des emails (principaux + alias)
    raw_emails = set()
    if sunwi_user.get('email'): raw_emails.add(sunwi_user['email'])
    if spotify_user.get('email'): raw_emails.add(spotify_user['email'])

    all_user_emails = set(raw_emails)
    for email in raw_emails:
        if email in EMAIL_ALIASES:
            all_user_emails.add(EMAIL_ALIASES[email])
        for alias, main_email in EMAIL_ALIASES.items():
            if main_email == email:
                all_user_emails.add(alias)

    primary_email = sunwi_user.get('email') or spotify_user.get('email')
    if primary_email in EMAIL_ALIASES:
        primary_email = EMAIL_ALIASES[primary_email]

    # 2. Collecte de tous les IDs
    ids_to_check = set()
    if sunwi_user.get('id'): ids_to_check.add(str(sunwi_user['id']))
    if sunwi_user.get('google_id'): ids_to_check.add(str(sunwi_user['google_id']))
    if spotify_user.get('id'): ids_to_check.add(str(spotify_user['id']))

    user = {
        'name': sunwi_user.get('name') or spotify_user.get('display_name') or 'Utilisateur',
        'email': primary_email,
        'picture': sunwi_user.get('picture') or (spotify_user.get('image') if isinstance(spotify_user.get('image'), str) else None)
    }

    user_stats = []
    custom_modules = []

    MODULE_CONFIG = {
        'football': {'title': 'Football', 'url': '/football/classement'},
        'f1': {'title': 'Formule 1', 'url': '/f1/classement'},
        'lol': {'title': 'League of Legends', 'url': '/lol/classement'},
        'disney': {'title': 'Films Disney', 'url': '/disney/classement'},
        'nba': {'title': 'NBA', 'url': '/nba/classement'},
        'pokemon': {'title': 'Pokémon', 'url': '/pokemon/classement'},
        'music': {'title': 'Musique (K-Pop)', 'url': '/music/classement'},
        'top100': {'title': 'Top 100 Musique', 'url': '/music/classement'},
        'tracks': {'title': 'Spotify', 'url': '/spotify/classement'},
    }

    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        try:
            conn = psycopg2.connect(db_url, sslmode='require')
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Recherche des tables user_*_scores
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND table_name LIKE 'user_%_scores';
            """)
            score_tables = [row['table_name'] for row in cur.fetchall()]

            if 'tracks_scores' not in score_tables:
                score_tables.append('tracks_scores')

            ids_tuple = tuple(ids_to_check) if ids_to_check else ('',)
            emails_tuple = tuple(all_user_emails) if all_user_emails else ('',)

            # 3. Calcul du nombre exact de duels (SUM(matches_count) / 2)
            for table_name in score_tables:
                raw_key = table_name.replace('user_', '').replace('_scores', '')
                config = MODULE_CONFIG.get(raw_key, {
                    'title': raw_key.capitalize(), 
                    'url': f'/{raw_key}/'
                })

                try:
                    total_duels = 0

                    # Somme des matchs par user_id
                    if ids_to_check:
                        query = f"SELECT COALESCE(SUM(matches_count), 0) / 2 AS total FROM {table_name} WHERE user_id::text IN %s;"
                        cur.execute(query, (ids_tuple,))
                        res = cur.fetchone()
                        total_duels = int(res['total']) if res else 0

                    # Fallback par email si user_id n'a rien donné
                    if total_duels == 0 and all_user_emails:
                        try:
                            query_email = f"SELECT COALESCE(SUM(matches_count), 0) / 2 AS total FROM {table_name} WHERE user_email IN %s;"
                            cur.execute(query_email, (emails_tuple,))
                            res_email = cur.fetchone()
                            total_duels = int(res_email['total']) if res_email else 0
                        except Exception:
                            conn.rollback()

                    # Fallback ultime pour tracks_scores si le user_id n'est pas encore assigné
                    if total_duels == 0 and table_name == 'tracks_scores':
                        try:
                            cur.execute("SELECT COALESCE(SUM(matches_count), 0) / 2 AS total FROM tracks_scores;")
                            res_tracks = cur.fetchone()
                            total_duels = int(res_tracks['total']) if res_tracks else 0
                        except Exception:
                            conn.rollback()

                    if total_duels > 0:
                        user_stats.append({
                            'module_name': config['title'],
                            'total_duels': total_duels,
                            'ranking_url': config['url']
                        })
                except Exception as e:
                    conn.rollback()
                    print(f"ℹ️ Erreur calcul duels pour {table_name} : {e}")

            # 4. Modules personnalisés
            try:
                cur.execute("""
                    SELECT id, title, track_count 
                    FROM custom_modules 
                    WHERE user_id::text IN %s OR user_email IN %s
                    ORDER BY id DESC;
                """, (ids_tuple, emails_tuple))
                custom_modules = cur.fetchall()
            except Exception:
                conn.rollback()

            cur.close()
            conn.close()
        except Exception as e:
            print(f"⚠️ Erreur BDD Profil : {e}")

    return render_template('profile.html', user=user, stats=user_stats, custom_modules=custom_modules)

@main_bp.route('/feedback', methods=['POST'])
def send_feedback():
    feedback_type = request.form.get('feedback_type', 'bug')
    message_body = request.form.get('message', '').strip()

    if not message_body:
        return jsonify({'status': 'error', 'message': 'Le message ne peut pas être vide.'}), 400

    sunwi_user = session.get('sunwi_user') or {}
    spotify_user = session.get('spotify_user_profile') or session.get('user_profile') or {}
    
    sender_name = sunwi_user.get('name') or spotify_user.get('display_name') or 'Utilisateur inconnu'
    sender_email = sunwi_user.get('email') or spotify_user.get('email') or 'Non renseigné'

    smtp_server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('MAIL_PORT', 587))
    smtp_user = os.environ.get('MAIL_USERNAME') or os.environ.get('ADMIN_EMAIL')
    smtp_password = os.environ.get('MAIL_PASSWORD')
    admin_email = os.environ.get('ADMIN_EMAIL') or smtp_user

    if not smtp_user or not smtp_password or not admin_email:
        print("⚠️ Configuration SMTP manquante pour l'envoi de feedback.")
        return jsonify({'status': 'error', 'message': 'Erreur de configuration serveur.'}), 500

    subject = f"[Sunwi Feedback] [{feedback_type.upper()}] De {sender_name}"
    
    content = f"""Un nouveau retour a été envoyé depuis Sunwi :

Type : {feedback_type.capitalize()}
Utilisateur : {sender_name} ({sender_email})

Message :
--------------------------------------------------
{message_body}
--------------------------------------------------"""

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = admin_email
    msg['Subject'] = subject
    msg.attach(MIMEText(content, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        return jsonify({'status': 'success', 'message': 'Merci ! Ton retour a bien été envoyé.'})
    except Exception as e:
        print(f"❌ Erreur envoi mail feedback : {e}")
        return jsonify({'status': 'error', 'message': 'Impossible d\'envoyer le message pour le moment.'}), 500

@main_bp.route('/set_audio_mode/<mode>')
def set_audio_mode(mode):
    is_silent = (mode == 'silent')
    session['silent_mode'] = is_silent
    session.modified = True
    
    if is_silent:
        try:
            from routes.spotify import get_spotify_client
            sp = get_spotify_client()
            if sp:
                sp.pause_playback()
        except Exception as e:
            print(f"⚠️ Impossible de mettre Spotify en pause : {e}")

    user_profile = session.get('user_profile') or session.get('sunwi_user')
    if user_profile and user_profile.get('id'):
        try:
            from routes.spotify import save_user_silent_mode_db
            threading.Thread(target=save_user_silent_mode_db, args=(user_profile['id'], is_silent), daemon=True).start()
        except Exception:
            pass

    return redirect(request.referrer or url_for('main.hub'))