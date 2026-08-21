from flask import Blueprint, render_template, request, session, redirect, url_for, send_from_directory, current_app
import os
from db import get_db_connection
from elo_engine import compute_and_update_vote, save_vote_async_generic, select_matchup

genshin_bp = Blueprint('genshin', __name__, url_prefix='/genshin')

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

def fetch_user_characters_from_db(user_id, element=None):
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    
    user_id_str = str(user_id) if user_id is not None else None
    
    if element:
        query = """
            SELECT 
                c.character_id, c.name, c.title, c.element, c.weapon,
                COALESCE(ugs.elo, 1000) as elo,
                COALESCE(ugs.matches_count, 0) as matches_count
            FROM genshin_characters c
            LEFT JOIN user_genshin_scores ugs 
                ON c.character_id = ugs.character_id AND ugs.user_id = %s
            WHERE LOWER(c.element) = LOWER(%s);
        """
        cur.execute(query, (user_id_str, element))
    else:
        query = """
            SELECT 
                c.character_id, c.name, c.title, c.element, c.weapon,
                COALESCE(ugs.elo, 1000) as elo,
                COALESCE(ugs.matches_count, 0) as matches_count
            FROM genshin_characters c
            LEFT JOIN user_genshin_scores ugs 
                ON c.character_id = ugs.character_id AND ugs.user_id = %s;
        """
        cur.execute(query, (user_id_str,))
        
    columns = [desc[0] for desc in cur.description]
    characters = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return characters

def get_cached_characters(user_id, element=None):
    cache_key = f'genshin_characters_cache_{element or "all"}'
    if cache_key not in session or not session[cache_key]:
        characters = fetch_user_characters_from_db(user_id, element)
        session[cache_key] = {str(c['character_id']): c for c in characters}
        session.modified = True
    return session[cache_key]

def db_save_genshin_vote(cur, user_id, p1_id, p2_id, new_p1_elo, new_p2_elo, winner_id, loser_id):
    upsert_sql = """
        INSERT INTO user_genshin_scores (user_id, character_id, elo, matches_count)
        VALUES (%s, %s, %s, 1)
        ON CONFLICT (user_id, character_id) DO UPDATE SET
            elo = EXCLUDED.elo,
            matches_count = user_genshin_scores.matches_count + 1;
    """
    cur.execute(upsert_sql, (str(user_id), str(p1_id), new_p1_elo))
    cur.execute(upsert_sql, (str(user_id), str(p2_id), new_p2_elo))

    cur.execute("""
        INSERT INTO user_votes (user_id, module_id, winner_id, loser_id)
        VALUES (%s, 'genshin', %s, %s);
    """, (str(user_id), str(winner_id), str(loser_id)))

@genshin_bp.route('/')
@genshin_bp.route('/<element>')
def genshin_hub(element=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    session['current_genshin_element'] = element
    characters_dict = get_cached_characters(user_id, element)
    characters_list = list(characters_dict.values())

    if len(characters_list) < 2:
        return "Pas assez de personnages dans cette catégorie pour lancer un duel.", 400

    char1, char2 = select_matchup(characters_list)
    last_result = session.pop('genshin_last_result', None)

    return render_template('genshin.html', p1=char1, p2=char2, last_result=last_result, current_element=element)

@genshin_bp.route('/classement', endpoint='classement')
@genshin_bp.route('/leaderboard', endpoint='leaderboard')
@genshin_bp.route('/classement/<element>', endpoint='classement_element')
def classement(element=None):
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    active_element = element or session.get('current_genshin_element')
    characters = fetch_user_characters_from_db(user_id, active_element)
    characters.sort(key=lambda x: (x['elo'], x['matches_count']), reverse=True)
    return render_template('genshin_leaderboard.html', ranking=characters, current_element=active_element)

@genshin_bp.route('/vote', methods=['POST'])
def vote():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    p1_id = str(request.form.get('p1_id'))
    p2_id = str(request.form.get('p2_id'))
    outcome = float(request.form.get('outcome', 0.5))

    active_element = session.get('current_genshin_element')
    cache_key = f'genshin_characters_cache_{active_element or "all"}'
    
    characters_dict = get_cached_characters(user_id, active_element)
    p1 = characters_dict.get(p1_id)
    p2 = characters_dict.get(p2_id)

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

        session['genshin_last_result'] = last_result
        session[cache_key] = characters_dict
        session.modified = True

        save_vote_async_generic(
            db_save_genshin_vote, 
            user_id, p1_id, p2_id, int(new_p1_elo), int(new_p2_elo), winner_id, loser_id
        )

    return redirect(url_for('genshin.genshin_hub', element=active_element) if active_element else url_for('genshin.genshin_hub'))

@genshin_bp.route('/character_icon/<character_id>')
def character_icon(character_id):
    img_dir = os.path.join(current_app.root_path, 'static', 'images', 'genshin')
    for ext in ['.png', '.jpg', '.webp', '.jpeg']:
        filename = f"{character_id}{ext}"
        if os.path.exists(os.path.join(img_dir, filename)):
            return send_from_directory(img_dir, filename)
            
    # Fallback automatique vers l'API genshin.jmp.blue si l'image locale est absente
    return redirect(f"https://genshin.jmp.blue/characters/{character_id}/icon")