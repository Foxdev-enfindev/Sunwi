# routes/music.py
import os
import threading
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Blueprint, render_template, request, redirect, url_for, session, Response, stream_with_context, jsonify

from elo_engine import compute_and_update_vote, select_matchup

music_bp = Blueprint('music', __name__)

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    """Initialise les tables pour le module Top 100 Musique si elles n'existent pas."""
    if not DATABASE_URL:
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Table des métadonnées partagées
        cur.execute("""
            CREATE TABLE IF NOT EXISTS top100_tracks (
                track_id VARCHAR(255) NOT NULL,
                genre VARCHAR(50) NOT NULL,
                year INT NOT NULL,
                name TEXT NOT NULL,
                artist TEXT NOT NULL,
                country VARCHAR(10) DEFAULT 'KR',
                cover_url TEXT,
                preview_url TEXT,
                PRIMARY KEY (track_id, genre, year)
            );
        """)
        
        # Table des scores personnels par utilisateur
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_music_scores (
                user_id VARCHAR(255) NOT NULL,
                track_id VARCHAR(255) NOT NULL,
                genre VARCHAR(50) NOT NULL,
                year INT NOT NULL,
                elo INT DEFAULT 1000,
                matches_count INT DEFAULT 0,
                PRIMARY KEY (user_id, track_id, genre, year)
            );
        """)
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Erreur initialisation BDD Music : {e}")

init_db()

def get_current_user_id():
    """Récupère l'ID utilisateur connecté ou None si non connecté."""
    sunwi_user = session.get('sunwi_user') or session.get('user_profile')
    if not isinstance(sunwi_user, dict):
        return None
    if sunwi_user.get('id'):
        return sunwi_user.get('id')
        
    email = sunwi_user.get('email')
    if email:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            res = cur.fetchone()
            cur.close()
            conn.close()
            if res:
                if 'sunwi_user' in session and isinstance(session['sunwi_user'], dict):
                    session['sunwi_user']['id'] = res[0]
                elif 'user_profile' in session and isinstance(session['user_profile'], dict):
                    session['user_profile']['id'] = res[0]
                return res[0]
    return None

def fetch_user_tracks_from_db(user_id, genre, year):
    """Charge les morceaux globaux et y injecte le Elo personnel depuis la BDD."""
    if not DATABASE_URL:
        return []
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                t.track_id AS id, 
                t.name, 
                t.artist, 
                t.cover_url AS image_url, 
                t.preview_url,
                COALESCE(s.elo, 1000) AS elo,
                COALESCE(s.matches_count, 0) AS matches_count
            FROM top100_tracks t
            LEFT JOIN user_music_scores s 
                ON t.track_id = s.track_id 
               AND t.genre = s.genre 
               AND t.year = s.year 
               AND s.user_id = %s
            WHERE LOWER(t.genre) = %s AND t.year = %s;
        """, (str(user_id), genre, year))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        # Conversion explicite en liste de dictionnaires purs
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"⚠️ Erreur chargement titres Music : {e}")
        return []

def get_cached_user_tracks(user_id, genre, year):
    """Gère un cache en session pour éviter de refaire une requête SQL à chaque vote."""
    cache_key = f'music_cache_{genre}_{year}'
    if cache_key not in session or not session[cache_key]:
        tracks = fetch_user_tracks_from_db(user_id, genre, year)
        session[cache_key] = {str(t['id']): dict(t) for t in tracks}
        session.modified = True
    return session[cache_key]

def _save_user_vote_async(user_id, genre, year, scores_to_update, winner_id, loser_id):
    """Sauvegarde le Elo dans user_music_scores en arrière-plan."""
    if not DATABASE_URL:
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        for track_id, data in scores_to_update.items():
            cur.execute("""
                INSERT INTO user_music_scores (user_id, track_id, genre, year, elo, matches_count)
                VALUES (%s, %s, %s, %s, %s, 1)
                ON CONFLICT (user_id, track_id, genre, year)
                DO UPDATE SET 
                    elo = EXCLUDED.elo,
                    matches_count = user_music_scores.matches_count + 1;
            """, (str(user_id), str(track_id), genre, year, data['elo']))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Erreur BDD Music Async : {e}")

@music_bp.route('/')
def duel():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    genre = request.args.get('genre', 'kpop').strip().lower()
    try:
        year = int(request.args.get('year', 2024))
    except (ValueError, TypeError):
        year = 2024

    # Si on change de genre/année, on réinitialise le duel en cours stocké
    if session.get('music_current_genre') != genre or session.get('music_current_year') != year:
        session.pop('music_current_duel', None)

    session['music_current_genre'] = genre
    session['music_current_year'] = year

    tracks_dict = get_cached_user_tracks(user_id, genre, year)
    tracks_list = list(tracks_dict.values())

    if len(tracks_list) < 2:
        return f"Pas assez de titres importés en base de données pour {genre.upper()} {year} (minimum 2 requis).", 400

    # Gestion de la conservation du duel en cours (comme Spotify)
    current_duel = session.get('music_current_duel')
    track_a, track_b = None, None

    if current_duel:
        track_a = next((t for t in tracks_list if str(t['id']) == str(current_duel[0])), None)
        track_b = next((t for t in tracks_list if str(t['id']) == str(current_duel[1])), None)

    if not track_a or not track_b or track_a['id'] == track_b['id']:
        track_a, track_b = select_matchup(tracks_list)
        session['music_current_duel'] = (track_a['id'], track_b['id'])

    last_result = session.pop('music_last_result', None) or session.pop('dernier_resultat_music', None)
    silent_mode = session.get('silent_mode', False)
    profile = session.get('user_profile') or session.get('sunwi_user')

    return render_template(
        'music.html',
        track_a=track_a,
        track_b=track_b,
        genre=genre,
        year=year,
        last_result=last_result,
        user=profile,
        silent_mode=silent_mode
    )

@music_bp.route('/vote', methods=['POST'])
def vote():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    p1_id = str(request.form.get('p1_id') or request.form.get('id_a'))
    p2_id = str(request.form.get('p2_id') or request.form.get('id_b'))
    outcome = float(request.form.get('outcome', 0.5))

    genre = session.get('music_current_genre', 'kpop')
    year = session.get('music_current_year', 2024)

    tracks_dict = get_cached_user_tracks(user_id, genre, year)

    track_a = tracks_dict.get(p1_id)
    track_b = tracks_dict.get(p2_id)

    if track_a and track_b:
        new_elo_a, new_elo_b, winner_id, loser_id, last_result = compute_and_update_vote(track_a, track_b, outcome)

        new_elo_a = int(new_elo_a)
        new_elo_b = int(new_elo_b)

        if last_result:
            last_result = last_result.replace('.0', '')

        track_a['elo'] = new_elo_a
        track_a['matches_count'] = (track_a.get('matches_count') or 0) + 1
        track_b['elo'] = new_elo_b
        track_b['matches_count'] = (track_b.get('matches_count') or 0) + 1

        cache_key = f'music_cache_{genre}_{year}'
        session['music_last_result'] = last_result
        session[cache_key] = tracks_dict
        session.modified = True

        scores_to_update = {
            p1_id: {'elo': new_elo_a},
            p2_id: {'elo': new_elo_b}
        }

        threading.Thread(
            target=_save_user_vote_async,
            args=(user_id, genre, year, scores_to_update, winner_id, loser_id),
            daemon=True
        ).start()

    # On nettoie le duel en cours pour forcer un nouveau tirage après le vote
    session.pop('music_current_duel', None)
    return redirect(url_for('music.duel', genre=genre, year=year))

@music_bp.route('/classement')
def classement():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    genre = request.args.get('genre') or session.get('music_current_genre', 'kpop')
    try:
        year = int(request.args.get('year') or session.get('music_current_year', 2024))
    except (ValueError, TypeError):
        year = 2024

    raw_ranking = fetch_user_tracks_from_db(user_id, genre, year)
    
    # On force la conversion explicite de chaque ligne en dictionnaire standard
    ranking = []
    for row in raw_ranking:
        if isinstance(row, dict):
            ranking.append(row)
        else:
            ranking.append(dict(row))

    ranking.sort(key=lambda x: (x.get('elo', 1000), x.get('matches_count', 0)), reverse=True)

    profile = session.get('user_profile') or session.get('sunwi_user')
    return render_template(
        'music_leaderboard.html',
        ranking=ranking,
        genre=genre,
        year=year,
        user=profile
    )

@music_bp.route('/get_preview/<track_id>')
def get_preview(track_id):
    """Récupère une URL de preview fraîche depuis Deezer côté serveur (contourne CORS et évite les 403)."""
    try:
        res = requests.get(f'https://api.deezer.com/track/{track_id}', timeout=4)
        data = res.json()
        if data and 'preview' in data:
            return jsonify({'preview': data['preview']})
    except Exception as e:
        print(f"⚠️ Erreur récupération preview Deezer ({track_id}) : {e}")
    return jsonify({'error': 'Preview indisponible'}), 404