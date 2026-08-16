# routes/main.py
import threading
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def hub():
    modules = [
        {
            'id': 'football',
            'title': 'Football',
            'category': 'Sport',
            'badge': 'Disponible',
            'active': True,
            'url': '/football/'
        },
        {
            'id': 'spotify',
            'title': 'Musique (Spotify)',
            'category': 'Personnel',
            'badge': 'Disponible',
            'active': True,
            'url': '/spotify/'
        },
        {
            'id': 'disney',
            'title': 'Films Disney',
            'category': 'Cinéma',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        },
        {
            'id': 'pokemon',
            'title': 'Pokémon',
            'category': 'Gaming',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        }
    ]

    category_order = ['Sport', 'Personnel', 'Cinéma', 'Gaming']

    grouped = {}
    for m in modules:
        grouped.setdefault(m['category'], []).append(m)

    ordered_categories = [
        {'name': cat, 'modules': grouped[cat]}
        for cat in category_order if cat in grouped
    ]

    return render_template('hub.html', categories=ordered_categories)

@main_bp.route('/set_audio_mode/<mode>')
def set_audio_mode(mode):
    is_silent = (mode == 'silent')
    session['silent_mode'] = is_silent
    session.modified = True  # Persiste la session immédiatement
    
    # 1. Si on passe en mode silencieux, on met en pause la lecture Spotify
    if is_silent:
        try:
            from routes.spotify import get_spotify_client
            sp = get_spotify_client()
            if sp:
                sp.pause_playback()
        except Exception as e:
            print(f"⚠️ Impossible de mettre Spotify en pause : {e}")

    # 2. Si un utilisateur Spotify est connecté, on sauvegarde la préférence en BDD
    user_profile = session.get('user_profile')
    if user_profile and user_profile.get('id'):
        try:
            from routes.spotify import save_user_silent_mode_db
            threading.Thread(target=save_user_silent_mode_db, args=(user_profile['id'], is_silent), daemon=True).start()
        except Exception:
            pass

    # 3. Redirection sur la page actuelle
    return redirect(request.referrer or url_for('main.hub'))