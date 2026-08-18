# routes/main.py
import threading
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

main_bp = Blueprint('main', __name__)

# --- Ta liste blanche d'emails autorisés pour le module Spotify ---
SPOTIFY_WHITELIST = ["florent.pennarun@gmail.com", "autre_email@exemple.com"]

@main_bp.route('/')
def hub():
    modules = [
        # --- SPORT ---
        {
            'id': 'football_top500',
            'title': 'Football (Top 500)',
            'category': 'Sport',
            'badge': 'Disponible',
            'active': True,
            'url': '/football/'
        },
        {
            'id': 'football_leagues',
            'title': 'Football (Par championnat)',
            'category': 'Sport',
            'badge': 'Disponible',
            'active': True,
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

        # --- GAMING ---
        {
            'id': 'pokemon_global',
            'title': 'Pokémon (Global)',
            'category': 'Gaming',
            'badge': 'Disponible',
            'active': True,
            'url': '/pokemon/'
        },
        {
            'id': 'pokemon_generations',
            'title': 'Pokémon (Par génération)',
            'category': 'Gaming',
            'badge': 'Disponible',
            'active': True,
            'url': '#'
        },
        {
            'id': 'pokemon_types',
            'title': 'Pokémon (Par type)',
            'category': 'Gaming',
            'badge': 'Disponible',
            'active': True,
            'url': '#'
        },
        # --- MUSIQUE ---
        {
            'id': 'music_top100',
            'title': 'Top 100 Kpop (Par année)',
            'category': 'Musique',
            'badge': 'Disponible',
            'active': True,
            'url': '/music/'
        },

        # --- CINÉMA ---
        {
            'id': 'disney',
            'title': 'Films Disney',
            'category': 'Cinéma',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        }
    ]

    # --- FILTRE SPOTIFY WHITELIST ---
    user = session.get('sunwi_user', {})
    user_email = user.get('email')
    
    if not user_email or user_email not in SPOTIFY_WHITELIST:
        # On supprime le module Spotify de la liste
        modules = [m for m in modules if m['id'] != 'spotify']
        # Optionnel : si on veut masquer le module 'steam' aussi (et donc toute la catégorie)
        # modules = [m for m in modules if m['category'] != 'Personnel (Nécessite une connexion externe)']

    category_order = ['Sport', 'Personnel (Nécessite une connexion externe)', 'Gaming', 'Musique', 'Cinéma']

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

    user_profile = session.get('user_profile') or session.get('sunwi_user')
    if user_profile and user_profile.get('id'):
        try:
            from routes.spotify import save_user_silent_mode_db
            threading.Thread(target=save_user_silent_mode_db, args=(user_profile['id'], is_silent), daemon=True).start()
        except Exception:
            pass

    return redirect(request.referrer or url_for('main.hub'))