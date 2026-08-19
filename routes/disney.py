from flask import Blueprint, render_template, request, session, redirect, url_for, send_from_directory, current_app
import os
from db import get_db_connection
from elo_engine import compute_and_update_vote, save_vote_async_generic, select_matchup

disney_bp = Blueprint('disney', __name__, url_prefix='/disney')

def get_current_user_id():
    sunwi_user = session.get('sunwi_user')
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
                session['sunwi_user']['id'] = res[0]
                return res[0]
    return None

def fetch_user_movies_from_db(user_id, studio=None):
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    
    # Conversion de user_id en chaîne de caractères pour correspondre au VARCHAR de PostgreSQL
    user_id_str = str(user_id) if user_id is not None else None
    
    if studio:
        query = """
            SELECT 
                m.movie_id, m.fr_title, m.en_title, m.release_year, m.studio, m.poster_url,
                COALESCE(uds.elo, 1000) as elo,
                COALESCE(uds.matches_count, 0) as matches_count
            FROM disney_movies m
            LEFT JOIN user_disney_scores uds 
                ON m.movie_id = uds.movie_id AND uds.user_id = %s
            WHERE LOWER(m.studio) = LOWER(%s);
        """
        cur.execute(query, (user_id_str, studio))
    else:
        query = """
            SELECT 
                m.movie_id, m.fr_title, m.en_title, m.release_year, m.studio, m.poster_url,
                COALESCE(uds.elo, 1000) as elo,
                COALESCE(uds.matches_count, 0) as matches_count
            FROM disney_movies m
            LEFT JOIN user_disney_scores uds 
                ON m.movie_id = uds.movie_id AND uds.user_id = %s;
        """
        cur.execute(query, (user_id_str,))
        
    columns = [desc[0] for desc in cur.description]
    movies = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return movies

def get_cached_movies(user_id, studio=None):
    cache_key = f'disney_movies_cache_{studio or "all"}'
    if cache_key not in session or not session[cache_key]:
        movies = fetch_user_movies_from_db(user_id, studio)
        session[cache_key] = {str(m['movie_id']): m for m in movies}
        session.modified = True
    return session[cache_key]

def db_save_disney_vote(cur, user_id, p1_id, p2_id, new_p1_elo, new_p2_elo, winner_id, loser_id):
    upsert_sql = """
        INSERT INTO user_disney_scores (user_id, movie_id, elo, matches_count)
        VALUES (%s, %s, %s, 1)
        ON CONFLICT (user_id, movie_id) DO UPDATE SET
            elo = EXCLUDED.elo,
            matches_count = user_disney_scores.matches_count + 1;
    """
    cur.execute(upsert_sql, (str(user_id), int(p1_id), new_p1_elo))
    cur.execute(upsert_sql, (str(user_id), int(p2_id), new_p2_elo))

    cur.execute("""
        INSERT INTO user_votes (user_id, module_id, winner_id, loser_id)
        VALUES (%s, 'disney', %s, %s);
    """, (str(user_id), str(winner_id), str(loser_id)))

@disney_bp.route('/')
@disney_bp.route('/<studio>')
def disney_hub(studio=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    session['current_disney_studio'] = studio
    movies_dict = get_cached_movies(user_id, studio)
    movies_list = list(movies_dict.values())

    if len(movies_list) < 2:
        return "Pas assez de films dans cette catégorie pour lancer un duel.", 400

    movie1, movie2 = select_matchup(movies_list)
    last_result = session.pop('disney_last_result', None)

    return render_template('disney.html', p1=movie1, p2=movie2, last_result=last_result, current_studio=studio)

@disney_bp.route('/classement', endpoint='classement')
@disney_bp.route('/leaderboard', endpoint='leaderboard')
@disney_bp.route('/classement/<studio>', endpoint='classement_studio')
def classement(studio=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    active_studio = studio or session.get('current_disney_studio')
    movies = fetch_user_movies_from_db(user_id, active_studio)
    movies.sort(key=lambda x: (x['elo'], x['matches_count'], x['release_year'] or 0), reverse=True)
    return render_template('disney_leaderboard.html', ranking=movies, current_studio=active_studio)

@disney_bp.route('/vote', methods=['POST'])
def vote():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    p1_id = str(request.form.get('p1_id'))
    p2_id = str(request.form.get('p2_id'))
    outcome = float(request.form.get('outcome', 0.5))

    active_studio = session.get('current_disney_studio')
    cache_key = f'disney_movies_cache_{active_studio or "all"}'
    
    movies_dict = get_cached_movies(user_id, active_studio)
    p1 = movies_dict.get(p1_id)
    p2 = movies_dict.get(p2_id)

    if p1 and p2:
        item_a = {
            'id': p1_id,
            'name': p1['fr_title'],
            'elo': p1['elo'],
            'matches_count': p1['matches_count']
        }
        item_b = {
            'id': p2_id,
            'name': p2['fr_title'],
            'elo': p2['elo'],
            'matches_count': p2['matches_count']
        }

        new_p1_elo, new_p2_elo, winner_id, loser_id, last_result = compute_and_update_vote(item_a, item_b, outcome)

        p1['elo'] = int(new_p1_elo)
        p1['matches_count'] += 1
        p2['elo'] = int(new_p2_elo)
        p2['matches_count'] += 1

        session['disney_last_result'] = last_result
        session[cache_key] = movies_dict
        session.modified = True

        save_vote_async_generic(
            db_save_disney_vote, 
            user_id, p1_id, p2_id, int(new_p1_elo), int(new_p2_elo), winner_id, loser_id
        )

    return redirect(url_for('disney.disney_hub', studio=active_studio) if active_studio else url_for('disney.disney_hub'))

@disney_bp.route('/movie_poster/<int:movie_id>')
def movie_poster(movie_id):
    img_dir = os.path.join(current_app.root_path, 'static', 'images', 'disney')
    for ext in ['.jpg', '.png', '.webp', '.jpeg']:
        filename = f"{movie_id}{ext}"
        if os.path.exists(os.path.join(img_dir, filename)):
            return send_from_directory(img_dir, filename)
            
    return redirect('https://via.placeholder.com/300x450?text=Disney')