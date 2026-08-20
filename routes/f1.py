from flask import Blueprint, render_template, request, session, redirect, url_for, send_from_directory, current_app
import os
from db import get_db_connection
from elo_engine import compute_and_update_vote, save_vote_async_generic, select_matchup

f1_bp = Blueprint('f1', __name__, url_prefix='/f1')

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

def fetch_user_drivers_from_db(user_id, era_filter=None):
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    
    user_id_str = str(user_id) if user_id is not None else None
    
    where_clause = ""
    params = [user_id_str]

    if era_filter == 'legends':
        where_clause = "WHERE d.is_legend = TRUE"
    elif era_filter == 'modern':
        where_clause = "WHERE d.is_modern_era = TRUE"

    query = f"""
        SELECT 
            d.driver_id, d.name, d.nationality, d.code, d.permanent_number, d.wins, d.url,
            COALESCE(ufs.elo, 1000) as elo,
            COALESCE(ufs.matches_count, 0) as matches_count
        FROM f1_drivers d
        LEFT JOIN user_f1_scores ufs 
            ON d.driver_id = ufs.driver_id AND ufs.user_id = %s
        {where_clause};
    """
    cur.execute(query, tuple(params))
        
    columns = [desc[0] for desc in cur.description]
    drivers = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return drivers

def get_cached_drivers(user_id, era_filter=None):
    cache_key = f'f1_drivers_cache_{era_filter or "all"}'
    if cache_key not in session or not session[cache_key]:
        drivers = fetch_user_drivers_from_db(user_id, era_filter)
        session[cache_key] = {str(d['driver_id']): d for d in drivers}
        session.modified = True
    return session[cache_key]

def db_save_f1_vote(cur, user_id, p1_id, p2_id, new_p1_elo, new_p2_elo, winner_id, loser_id):
    upsert_sql = """
        INSERT INTO user_f1_scores (user_id, driver_id, elo, matches_count)
        VALUES (%s, %s, %s, 1)
        ON CONFLICT (user_id, driver_id) DO UPDATE SET
            elo = EXCLUDED.elo,
            matches_count = user_f1_scores.matches_count + 1;
    """
    cur.execute(upsert_sql, (str(user_id), str(p1_id), new_p1_elo))
    cur.execute(upsert_sql, (str(user_id), str(p2_id), new_p2_elo))

    cur.execute("""
        INSERT INTO user_votes (user_id, module_id, winner_id, loser_id)
        VALUES (%s, 'f1', %s, %s);
    """, (str(user_id), str(winner_id), str(loser_id)))

@f1_bp.route('/')
@f1_bp.route('/<era_filter>')
def f1_hub(era_filter=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    session['current_f1_filter'] = era_filter
    drivers_dict = get_cached_drivers(user_id, era_filter)
    drivers_list = list(drivers_dict.values())

    if len(drivers_list) < 2:
        return "Pas assez de pilotes dans cette sélection pour lancer un duel.", 400

    driver1, driver2 = select_matchup(drivers_list)
    last_result = session.pop('f1_last_result', None)

    return render_template('f1.html', p1=driver1, p2=driver2, last_result=last_result, current_filter=era_filter)

@f1_bp.route('/classement', endpoint='classement')
@f1_bp.route('/leaderboard', endpoint='leaderboard')
@f1_bp.route('/classement/<era_filter>', endpoint='classement_filter')
def classement(era_filter=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    active_filter = era_filter or session.get('current_f1_filter')
    drivers = fetch_user_drivers_from_db(user_id, active_filter)
    drivers.sort(key=lambda x: (x['elo'], x['matches_count'], x['wins']), reverse=True)
    return render_template('f1_leaderboard.html', ranking=drivers, current_filter=active_filter)

@f1_bp.route('/vote', methods=['POST'])
def vote():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    p1_id = str(request.form.get('p1_id'))
    p2_id = str(request.form.get('p2_id'))
    outcome = float(request.form.get('outcome', 0.5))

    active_filter = session.get('current_f1_filter')
    cache_key = f'f1_drivers_cache_{active_filter or "all"}'
    
    drivers_dict = get_cached_drivers(user_id, active_filter)
    p1 = drivers_dict.get(p1_id)
    p2 = drivers_dict.get(p2_id)

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

        session['f1_last_result'] = last_result
        session[cache_key] = drivers_dict
        session.modified = True

        save_vote_async_generic(
            db_save_f1_vote, 
            user_id, p1_id, p2_id, int(new_p1_elo), int(new_p2_elo), winner_id, loser_id
        )

    return redirect(url_for('f1.f1_hub', era_filter=active_filter) if active_filter else url_for('f1.f1_hub'))

@f1_bp.route('/driver_photo/<driver_id>')
def driver_photo(driver_id):
    img_dir = os.path.join(current_app.root_path, 'static', 'images', 'f1')
    for ext in ['.png', '.jpg', '.webp', '.jpeg']:
        filename = f"{driver_id}{ext}"
        if os.path.exists(os.path.join(img_dir, filename)):
            return send_from_directory(img_dir, filename)
            
    # Fallback générique
    return send_from_directory(os.path.join(current_app.root_path, 'static', 'images'), 'default_driver.png')

@f1_bp.route('/clear_cache')
def clear_f1_cache():
    for key in list(session.keys()):
        if key.startswith('f1_drivers_cache_'):
            session.pop(key, None)
    session.modified = True
    return "Cache F1 nettoyé ! <a href='/f1/'>Retour aux duels</a>"