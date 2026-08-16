from flask import Blueprint, render_template, request, session, redirect, url_for
from db import get_db_connection
from elo_engine import compute_and_update_vote, save_vote_async_generic, select_matchup

football_bp = Blueprint('football', __name__, url_prefix='/football')

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

def fetch_user_players_from_db(user_id):
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            p.player_id, p.name, p.overall, p.position, p.club, p.nationality, p.league, p.photo_url,
            COALESCE(ufs.elo, 1000) as elo,
            COALESCE(ufs.matches_count, 0) as matches_count
        FROM football_players_scores p
        LEFT JOIN user_football_scores ufs 
            ON p.player_id = ufs.player_id AND ufs.user_id = %s;
    """, (user_id,))
    
    columns = [desc[0] for desc in cur.description]
    players = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return players

def get_cached_players(user_id):
    if 'football_players_cache' not in session or not session['football_players_cache']:
        players = fetch_user_players_from_db(user_id)
        session['football_players_cache'] = {str(p['player_id']): p for p in players}
        session.modified = True
    return session['football_players_cache']

def db_save_football_vote(cur, user_id, p1_id, p2_id, new_p1_elo, new_p2_elo, winner_id, loser_id):
    """Requête SQL exécutée en arrière-plan."""
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
def football_hub():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    players_dict = get_cached_players(user_id)
    players_list = list(players_dict.values())

    if len(players_list) < 2:
        return "Pas assez de joueurs dans la base de données.", 400

    player1, player2 = select_matchup(players_list)
    
    # 1. Récupère et retire le dernier résultat stocké
    last_result = session.pop('football_last_result', None)

    # 2. Transmet impérativement last_result au template
    return render_template('football.html', p1=player1, p2=player2, last_result=last_result)

@football_bp.route('/classement', endpoint='classement')
@football_bp.route('/leaderboard', endpoint='leaderboard')
def classement():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    players = fetch_user_players_from_db(user_id)
    players.sort(key=lambda x: (x['elo'], x['matches_count'], x['overall']), reverse=True)
    return render_template('football_leaderboard.html', ranking=players)

@football_bp.route('/vote', methods=['POST'])
def vote():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    p1_id = str(request.form.get('p1_id'))
    p2_id = str(request.form.get('p2_id'))
    outcome = float(request.form.get('outcome', 0.5))

    players_dict = get_cached_players(user_id)
    p1, p2 = players_dict.get(p1_id), players_dict.get(p2_id)

    if p1 and p2:
        p1['id'], p2['id'] = p1_id, p2_id

        # 1. Calcul Elo + mise à jour mémoire + génération bannière en UNE seule ligne
        new_p1_elo, new_p2_elo, winner_id, loser_id, last_result = compute_and_update_vote(p1, p2, outcome)

        session['football_last_result'] = last_result
        session['football_players_cache'] = players_dict
        session.modified = True

        # 2. Sauvegarde BDD en arrière-plan
        save_vote_async_generic(
            db_save_football_vote, 
            user_id, p1_id, p2_id, new_p1_elo, new_p2_elo, winner_id, loser_id
        )

    return redirect(url_for('football.football_hub'))