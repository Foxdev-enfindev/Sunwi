from flask import Blueprint, render_template, request, session, redirect, url_for
from db import get_db_connection
from elo_engine import compute_and_update_vote, save_vote_async_generic, select_matchup
import requests
from flask import Response

football_bp = Blueprint('football', __name__, url_prefix='/football')

# Correspondance entre les slugs d'URL et les noms exacts en base de données
LEAGUE_MAPPING = {
    'ligue1': "Ligue 1 McDonald's",
    'laliga': "LALIGA EA SPORTS",
    'premier_league': "Premier League",
    'serie_a': "Serie A Enilive",
    'bundesliga': "Bundesliga",
    'nba': "NBA"
}

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

def fetch_user_players_from_db(user_id, league_key=None):
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    
    db_league_name = LEAGUE_MAPPING.get(league_key) if league_key else None
    
    if db_league_name:
        query = """
            SELECT 
                p.player_id, p.name, p.overall, p.position, p.club, p.nationality, p.league, p.photo_url,
                COALESCE(ufs.elo, 1000) as elo,
                COALESCE(ufs.matches_count, 0) as matches_count
            FROM football_players_scores p
            LEFT JOIN user_football_scores ufs 
                ON p.player_id = ufs.player_id AND ufs.user_id = %s
            WHERE p.league = %s;
        """
        cur.execute(query, (user_id, db_league_name))
    else:
        query = """
            SELECT 
                p.player_id, p.name, p.overall, p.position, p.club, p.nationality, p.league, p.photo_url,
                COALESCE(ufs.elo, 1000) as elo,
                COALESCE(ufs.matches_count, 0) as matches_count
            FROM football_players_scores p
            LEFT JOIN user_football_scores ufs 
                ON p.player_id = ufs.player_id AND ufs.user_id = %s;
        """
        cur.execute(query, (user_id,))
        
    columns = [desc[0] for desc in cur.description]
    players = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return players

def get_cached_players(user_id, league_key=None):
    cache_key = f'football_players_cache_{league_key or "all"}'
    if cache_key not in session or not session[cache_key]:
        players = fetch_user_players_from_db(user_id, league_key)
        session[cache_key] = {str(p['player_id']): p for p in players}
        session.modified = True
    return session[cache_key]

def db_save_football_vote(cur, user_id, p1_id, p2_id, new_p1_elo, new_p2_elo, winner_id, loser_id):
    upsert_sql = """
        INSERT INTO user_football_scores (user_id, player_id, elo, matches_count)
        VALUES (%s, %s, %s, 1)
        ON CONFLICT (user_id, player_id) DO UPDATE SET
            elo = EXCLUDED.elo,
            matches_count = user_football_scores.matches_count + 1;
    """
    cur.execute(upsert_sql, (user_id, str(p1_id), new_p1_elo))
    cur.execute(upsert_sql, (user_id, str(p2_id), new_p2_elo))

    cur.execute("""
        INSERT INTO user_votes (user_id, module_id, winner_id, loser_id)
        VALUES (%s, 'football', %s, %s);
    """, (user_id, str(winner_id), str(loser_id)))

@football_bp.route('/')
@football_bp.route('/<league>')
def football_hub(league=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    session['current_football_league'] = league
    players_dict = get_cached_players(user_id, league)
    players_list = list(players_dict.values())

    if len(players_list) < 2:
        return "Pas assez de joueurs dans ce championnat pour lancer un duel.", 400

    player1, player2 = select_matchup(players_list)
    
    last_result = session.pop('football_last_result', None)

    return render_template('football.html', p1=player1, p2=player2, last_result=last_result, current_league=league)

@football_bp.route('/classement', endpoint='classement')
@football_bp.route('/leaderboard', endpoint='leaderboard')
@football_bp.route('/classement/<league>', endpoint='classement_league')
def classement(league=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    active_league = league or session.get('current_football_league')
    players = fetch_user_players_from_db(user_id, active_league)
    players.sort(key=lambda x: (x['elo'], x['matches_count'], x['overall']), reverse=True)
    return render_template('football_leaderboard.html', ranking=players, current_league=active_league)

@football_bp.route('/vote', methods=['POST'])
def vote():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    p1_id = str(request.form.get('p1_id'))
    p2_id = str(request.form.get('p2_id'))
    outcome = float(request.form.get('outcome', 0.5))

    active_league = session.get('current_football_league')
    cache_key = f'football_players_cache_{active_league or "all"}'
    
    players_dict = get_cached_players(user_id, active_league)
    p1 = players_dict.get(p1_id)
    p2 = players_dict.get(p2_id)

    if p1 and p2:
        # On isole les données dans de nouveaux dictionnaires pour éviter la mutation par référence
        item_a = {
            'id': p1_id,
            'name': p1['name'],
            'elo': p1['elo'],
            'matches_count': p1['matches_count']
        }
        item_b = {
            'id': p2_id,
            'name': p2['name'],
            'elo': p2['elo'],
            'matches_count': p2['matches_count']
        }

        new_p1_elo, new_p2_elo, winner_id, loser_id, last_result = compute_and_update_vote(item_a, item_b, outcome)

        # Mise à jour propre du cache de session
        p1['elo'] = int(new_p1_elo)
        p1['matches_count'] += 1
        p2['elo'] = int(new_p2_elo)
        p2['matches_count'] += 1

        session['football_last_result'] = last_result
        session[cache_key] = players_dict
        session.modified = True

        save_vote_async_generic(
            db_save_football_vote, 
            user_id, p1_id, p2_id, int(new_p1_elo), int(new_p2_elo), winner_id, loser_id
        )

    return redirect(url_for('football.football_hub', league=active_league) if active_league else url_for('football.football_hub'))
@football_bp.route('/player_photo/<player_id>')
def player_photo(player_id):
    conn = get_db_connection()
    if not conn:
        return "", 404
    cur = conn.cursor()
    cur.execute("SELECT photo_url FROM football_players_scores WHERE player_id = %s;", (player_id,))
    res = cur.fetchone()
    cur.close()
    conn.close()

    if not res or not res[0]:
        print(f"Pas d'URL trouvée en base pour le joueur {player_id}")
        return "", 404

    target_url = res[0]
    print(f"Tentative de proxy pour l'URL : {target_url}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://sofifa.com/'
        }
        resp = requests.get(target_url, headers=headers, timeout=5)
        print(f"Statut reçu du CDN : {resp.status_code}")
        if resp.status_code == 200:
            return Response(resp.content, content_type=resp.headers.get('content-type', 'image/png'))
    except Exception as e:
        print(f"Erreur proxy exception : {e}")

    return "", 404