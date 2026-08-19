from flask import Blueprint, render_template, request, session, redirect, url_for, send_from_directory, current_app
import os
from db import get_db_connection
from elo_engine import compute_and_update_vote, save_vote_async_generic, select_matchup

lol_bp = Blueprint('lol', __name__, url_prefix='/lol')

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

def fetch_user_champions_from_db(user_id, role=None):
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    
    user_id_str = str(user_id) if user_id is not None else None
    
    if role:
        query = """
            SELECT 
                c.champion_id, c.name, c.title, c.role,
                COALESCE(uls.elo, 1000) as elo,
                COALESCE(uls.matches_count, 0) as matches_count
            FROM lol_champions c
            LEFT JOIN user_lol_scores uls 
                ON c.champion_id = uls.champion_id AND uls.user_id = %s
            WHERE LOWER(c.role) = LOWER(%s);
        """
        cur.execute(query, (user_id_str, role))
    else:
        query = """
            SELECT 
                c.champion_id, c.name, c.title, c.role,
                COALESCE(uls.elo, 1000) as elo,
                COALESCE(uls.matches_count, 0) as matches_count
            FROM lol_champions c
            LEFT JOIN user_lol_scores uls 
                ON c.champion_id = uls.champion_id AND uls.user_id = %s;
        """
        cur.execute(query, (user_id_str,))
        
    columns = [desc[0] for desc in cur.description]
    champions = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return champions

def get_cached_champions(user_id, role=None):
    cache_key = f'lol_champions_cache_{role or "all"}'
    if cache_key not in session or not session[cache_key]:
        champions = fetch_user_champions_from_db(user_id, role)
        session[cache_key] = {str(c['champion_id']): c for c in champions}
        session.modified = True
    return session[cache_key]

def db_save_lol_vote(cur, user_id, p1_id, p2_id, new_p1_elo, new_p2_elo, winner_id, loser_id):
    upsert_sql = """
        INSERT INTO user_lol_scores (user_id, champion_id, elo, matches_count)
        VALUES (%s, %s, %s, 1)
        ON CONFLICT (user_id, champion_id) DO UPDATE SET
            elo = EXCLUDED.elo,
            matches_count = user_lol_scores.matches_count + 1;
    """
    cur.execute(upsert_sql, (str(user_id), str(p1_id), new_p1_elo))
    cur.execute(upsert_sql, (str(user_id), str(p2_id), new_p2_elo))

    cur.execute("""
        INSERT INTO user_votes (user_id, module_id, winner_id, loser_id)
        VALUES (%s, 'lol', %s, %s);
    """, (str(user_id), str(winner_id), str(loser_id)))

@lol_bp.route('/')
@lol_bp.route('/<role>')
def lol_hub(role=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    session['current_lol_role'] = role
    champions_dict = get_cached_champions(user_id, role)
    champions_list = list(champions_dict.values())

    if len(champions_list) < 2:
        return "Pas assez de champions dans cette catégorie pour lancer un duel.", 400

    champ1, champ2 = select_matchup(champions_list)
    last_result = session.pop('lol_last_result', None)

    return render_template('lol.html', p1=champ1, p2=champ2, last_result=last_result, current_role=role)

@lol_bp.route('/classement', endpoint='classement')
@lol_bp.route('/leaderboard', endpoint='leaderboard')
@lol_bp.route('/classement/<role>', endpoint='classement_role')
def classement(role=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    active_role = role or session.get('current_lol_role')
    champions = fetch_user_champions_from_db(user_id, active_role)
    champions.sort(key=lambda x: (x['elo'], x['matches_count']), reverse=True)
    return render_template('lol_leaderboard.html', ranking=champions, current_role=active_role)

@lol_bp.route('/vote', methods=['POST'])
def vote():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    p1_id = str(request.form.get('p1_id'))
    p2_id = str(request.form.get('p2_id'))
    outcome = float(request.form.get('outcome', 0.5))

    active_role = session.get('current_lol_role')
    cache_key = f'lol_champions_cache_{active_role or "all"}'
    
    champions_dict = get_cached_champions(user_id, active_role)
    p1 = champions_dict.get(p1_id)
    p2 = champions_dict.get(p2_id)

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

        session['lol_last_result'] = last_result
        session[cache_key] = champions_dict
        session.modified = True

        save_vote_async_generic(
            db_save_lol_vote, 
            user_id, p1_id, p2_id, int(new_p1_elo), int(new_p2_elo), winner_id, loser_id
        )

    return redirect(url_for('lol.lol_hub', role=active_role) if active_role else url_for('lol.lol_hub'))

@lol_bp.route('/champion_icon/<champion_id>')
def champion_icon(champion_id):
    img_dir = os.path.join(current_app.root_path, 'static', 'images', 'lol')
    for ext in ['.png', '.jpg', '.webp', '.jpeg']:
        filename = f"{champion_id}{ext}"
        if os.path.exists(os.path.join(img_dir, filename)):
            return send_from_directory(img_dir, filename)
            
    # Redirection automatique vers le CDN Data Dragon de Riot si le fichier local n'existe pas
    return redirect(f"https://ddragon.leagueoflegends.com/cdn/14.1.1/img/champion/{champion_id}.png")