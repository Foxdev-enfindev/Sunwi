from flask import Blueprint, render_template, request, session, redirect, url_for
from db import get_db_connection
from elo_engine import compute_and_update_vote, save_vote_async_generic, select_matchup

pokemon_bp = Blueprint('pokemon', __name__, url_prefix='/pokemon')

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

def fetch_user_pokemon_from_db(user_id, generation=None, p_type=None):
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    
    query = """
        SELECT 
            p.pokemon_id, p.name, p.generation, p.type1, p.type2, 
            p.sprite_url, p.shiny_url, p.local_sprite_path,
            COALESCE(ups.elo, 1000) as elo,
            COALESCE(ups.matches_count, 0) as matches_count
        FROM pokemon_players p
        LEFT JOIN user_pokemon_scores ups 
            ON p.pokemon_id = ups.pokemon_id AND ups.user_id = %s
        WHERE 1=1
    """
    params = [user_id]
    
    if generation:
        query += " AND p.generation = %s"
        params.append(generation)
        
    if p_type:
        query += " AND (p.type1 = %s OR p.type2 = %s)"
        params.extend([p_type, p_type])
        
    cur.execute(query, tuple(params))
    
    columns = [desc[0] for desc in cur.description]
    pokemons = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return pokemons

def get_cached_pokemon(user_id, generation=None, p_type=None):
    cache_key = f'pokemon_cache_{generation or "all"}_{p_type or "all"}'
    if cache_key not in session or not session[cache_key]:
        pokemons = fetch_user_pokemon_from_db(user_id, generation, p_type)
        session[cache_key] = {str(p['pokemon_id']): p for p in pokemons}
        session.modified = True
    return session[cache_key]

def db_save_pokemon_vote(cur, user_id, p1_id, p2_id, new_p1_elo, new_p2_elo, winner_id, loser_id):
    upsert_sql = """
        INSERT INTO user_pokemon_scores (user_id, pokemon_id, elo, matches_count)
        VALUES (%s, %s, %s, 1)
        ON CONFLICT (user_id, pokemon_id) DO UPDATE SET
            elo = EXCLUDED.elo,
            matches_count = user_pokemon_scores.matches_count + 1;
    """
    cur.execute(upsert_sql, (user_id, str(p1_id), new_p1_elo))
    cur.execute(upsert_sql, (user_id, str(p2_id), new_p2_elo))

    cur.execute("""
        INSERT INTO user_votes (user_id, module_id, winner_id, loser_id)
        VALUES (%s, 'pokemon', %s, %s);
    """, (user_id, str(winner_id), str(loser_id)))

@pokemon_bp.route('/')
def pokemon_hub():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    generation = request.args.get('generation') or None
    p_type = request.args.get('type') or None

    session['pokemon_current_gen'] = generation
    session['pokemon_current_type'] = p_type

    pokemon_dict = get_cached_pokemon(user_id, generation, p_type)
    pokemon_list = list(pokemon_dict.values())

    if len(pokemon_list) < 2:
        return "Pas assez de Pokémon avec ces filtres dans la base de données.", 400

    pokemon1, pokemon2 = select_matchup(pokemon_list)
    last_result = session.pop('pokemon_last_result', None)

    return render_template('pokemon.html', p1=pokemon1, p2=pokemon2, last_result=last_result)

@pokemon_bp.route('/classement', endpoint='classement')
@pokemon_bp.route('/leaderboard', endpoint='leaderboard')
def classement():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    generation = request.args.get('generation') or session.get('pokemon_current_gen')
    p_type = request.args.get('type') or session.get('pokemon_current_type')

    pokemons = fetch_user_pokemon_from_db(user_id, generation, p_type)
    pokemons.sort(key=lambda x: (x['elo'], x['matches_count']), reverse=True)
    return render_template('pokemon_leaderboard.html', ranking=pokemons)

@pokemon_bp.route('/vote', methods=['POST'])
def vote():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('auth.google_login'))

    p1_id = str(request.form.get('p1_id'))
    p2_id = str(request.form.get('p2_id'))
    outcome = float(request.form.get('outcome', 0.5))

    generation = session.get('pokemon_current_gen')
    p_type = session.get('pokemon_current_type')
    cache_key = f'pokemon_cache_{generation or "all"}_{p_type or "all"}'

    pokemon_dict = get_cached_pokemon(user_id, generation, p_type)
    p1 = pokemon_dict.get(p1_id)
    p2 = pokemon_dict.get(p2_id)

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

        new_p1_elo = int(new_p1_elo)
        new_p2_elo = int(new_p2_elo)
        if last_result:
            last_result = last_result.replace('.0', '')

        p1['elo'] = new_p1_elo
        p1['matches_count'] += 1
        p2['elo'] = new_p2_elo
        p2['matches_count'] += 1

        session['pokemon_last_result'] = last_result
        session[cache_key] = pokemon_dict
        session.modified = True

        save_vote_async_generic(
            db_save_pokemon_vote, 
            user_id, p1_id, p2_id, new_p1_elo, new_p2_elo, winner_id, loser_id
        )

    args = {}
    if generation: args['generation'] = generation
    if p_type: args['type'] = p_type
    return redirect(url_for('pokemon.pokemon_hub', **args))