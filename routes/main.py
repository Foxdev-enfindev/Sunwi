# routes/main.py
import threading
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def hub():
    modules = [
        # --- SPORT ---
        {
            'id': 'football',
            'title': 'Football (Top 500)',
            'category': 'Sport',
            'badge': 'Disponible',
            'active': True,
            'url': '/football/'
        },
        {
            'id': 'ligue1',
            'title': 'Ligue 1',
            'category': 'Sport',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        },
        {
            'id': 'laliga',
            'title': 'LaLiga',
            'category': 'Sport',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        },
        {
            'id': 'premier_league',
            'title': 'Premier League',
            'category': 'Sport',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        },
        {
            'id': 'serie_a',
            'title': 'Serie A',
            'category': 'Sport',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        },
        {
            'id': 'bundesliga',
            'title': 'Bundesliga',
            'category': 'Sport',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        },
        {
            'id': 'nba',
            'title': 'NBA',
            'category': 'Sport',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        },

        # --- PERSONNEL ---
        {
            'id': 'spotify',
            'title': 'Musique (Spotify)',
            'category': 'Personnel (Nécessite une connexion externe)',
            'badge': 'Disponible',
            'active': True,
            'url': '/spotify/'
        },
        {
            'id': 'steam',
            'title': 'Steam',
            'category': 'Personnel (Nécessite une connexion externe)',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        },

        # --- CINÉMA ---
        {
            'id': 'disney',
            'title': 'Films Disney',
            'category': 'Cinéma',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        },

        # --- GAMING ---
        {
            'id': 'pokemon',
            'title': 'Pokémon',
            'category': 'Gaming',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        }
    ]

    category_order = ['Sport', 'Personnel (Nécessite une connexion externe)', 'Cinéma', 'Gaming']

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
    session.modified = True
    
    if is_silent:
        try:
            from routes.spotify import get_spotify_client
            sp = get_spotify_client()
            if sp:
                sp.pause_playback()
        except Exception as e:
            print(f"⚠️ Impossible de mettre Spotify en pause : {e}")

    user_profile = session.get('user_profile')
    if user_profile and user_profile.get('id'):
        try:
            from routes.spotify import save_user_silent_mode_db
            threading.Thread(target=save_user_silent_mode_db, args=(user_profile['id'], is_silent), daemon=True).start()
        except Exception:
            pass

    return redirect(request.referrer or url_for('main.hub'))