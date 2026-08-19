from flask import Blueprint, render_template, request, session, redirect, url_for, send_from_directory, current_app
import os
from db import get_db_connection
from elo_engine import compute_and_update_vote, save_vote_async_generic, select_matchup

nba_bp = Blueprint('nba', __name__, url_prefix='/nba')

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

def fetch_user_players_from_db(user_id, team=None):
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    
    user_id_str = str(user_id) if user_id is not None else None
    
    if team:
        query = """
            SELECT 
                p.player_id, p.name, p.position, p.team, p.overall,
                COALESCE(uns.elo, 1000) as elo,
                COALESCE(uns.matches_count, 0) as matches_count
            FROM nba_players p
            LEFT JOIN user_nba_scores uns 
                ON p.player_id = uns.player_id AND uns.user_id = %s
            WHERE LOWER(p.team) = LOWER(%s);
        """
        cur.execute(query, (user_id_str, team))
    else:
        query = """
            SELECT 
                p.player_id, p.name, p.position, p.team, p.overall,
                COALESCE(uns.elo, 1000) as elo,
                COALESCE(uns.matches_count, 0) as matches_count
            FROM nba_players p
            LEFT JOIN user_nba_scores uns 
                ON p.player_id = uns.player_id AND uns.user_id = %s;
        """
        cur.execute(query, (user_id_str,))
        
    columns = [desc[0] for desc in cur.description]
    players = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return players

def get_cached_players(user_id, team=None):
    cache_key = f'nba_players_cache_{team or "all"}'
    if cache_key not in session or not session[cache_key]:
        players = fetch_user_players_from_db(user_id, team)
        session[cache_key] = {str(p['player_id']): p for p in players}
        session.modified = True
    return session[cache_key]

def db_save_nba_vote(cur, user_id, p1_id, p2_id, new_p1_elo, new_p2_elo, winner_id, loser_id):
    upsert_sql = """
        INSERT INTO user_nba_scores (user_id, player_id, elo, matches_count)
        VALUES (%s, %s, %s, 1)
        ON CONFLICT (user_id, player_id) DO UPDATE SET
            elo = EXCLUDED.elo,
            matches_count = user_nba_scores.matches_count + 1;
    """
    cur.execute(upsert_sql, (str(user_id), str(p1_id), new_p1_elo))
    cur.execute(upsert_sql, (str(user_id), str(p2_id), new_p2_elo))

    cur.execute("""
        INSERT INTO user_votes (user_id, module_id, winner_id, loser_id)
        VALUES (%s, 'nba', %s, %s);
    """, (str(user_id), str(winner_id), str(loser_id)))

@nba_bp.route('/')
@nba_bp.route('/<team>')
def nba_hub(team=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    session['current_nba_team'] = team
    players_dict = get_cached_players(user_id, team)
    players_list = list(players_dict.values())

    if len(players_list) < 2:
        return "Pas assez de joueurs dans cette sélection pour lancer un duel.", 400

    player1, player2 = select_matchup(players_list)
    last_result = session.pop('nba_last_result', None)

    return render_template('nba.html', p1=player1, p2=player2, last_result=last_result, current_team=team)

@nba_bp.route('/classement', endpoint='classement')
@nba_bp.route('/leaderboard', endpoint='leaderboard')
@nba_bp.route('/classement/<team>', endpoint='classement_team')
def classement(team=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    active_team = team or session.get('current_nba_team')
    players = fetch_user_players_from_db(user_id, active_team)
    players.sort(key=lambda x: (x['elo'], x['matches_count'], x['overall']), reverse=True)
    return render_template('nba_leaderboard.html', ranking=players, current_team=active_team)

@nba_bp.route('/vote', methods=['POST'])
def vote():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    p1_id = str(request.form.get('p1_id'))
    p2_id = str(request.form.get('p2_id'))
    outcome = float(request.form.get('outcome', 0.5))

    active_team = session.get('current_nba_team')
    cache_key = f'nba_players_cache_{active_team or "all"}'
    
    players_dict = get_cached_players(user_id, active_team)
    p1 = players_dict.get(p1_id)
    p2 = players_dict.get(p2_id)

    if p1 and p2:
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

        p1['elo'] = int(new_p1_elo)
        p1['matches_count'] += 1
        p2['elo'] = int(new_p2_elo)
        p2['matches_count'] += 1

        session['nba_last_result'] = last_result
        session[cache_key] = players_dict
        session.modified = True

        save_vote_async_generic(
            db_save_nba_vote, 
            user_id, p1_id, p2_id, int(new_p1_elo), int(new_p2_elo), winner_id, loser_id
        )

    return redirect(url_for('nba.nba_hub', team=active_team) if active_team else url_for('nba.nba_hub'))

@nba_bp.route('/player_photo/<player_id>')
def player_photo(player_id):
    img_dir = os.path.join(current_app.root_path, 'static', 'images', 'nba')
    for ext in ['.png', '.jpg', '.webp', '.jpeg']:
        filename = f"{player_id}{ext}"
        if os.path.exists(os.path.join(img_dir, filename)):
            return send_from_directory(img_dir, filename)
            
    # Fallback CDN officiel NBA Headshots
    return redirect(f"https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190/{player_id}.png")
@nba_bp.route('/clear_cache')
def clear_nba_cache():
    for key in list(session.keys()):
        if key.startswith('nba_players_cache_'):
            session.pop(key, None)
    session.modified = True
    return "Cache NBA nettoyé ! <a href='/nba/'>Retour aux duels</a>"