# elo_engine.py
import random
import threading
from db import get_db_connection

def get_k_factor(matches_count):
    """K-factor dynamique individuel selon le nombre de duels joués."""
    if matches_count < 10:
        return 50
    elif matches_count <= 30:
        return 32
    return 16

def calculate_new_ratings(rating_a, rating_b, score_a, matches_a=0, matches_b=0):
    """
    Score_a = 1 si A gagne, 0 si B gagne, 0.5 pour un match nul.
    Retourne (new_rating_a, new_rating_b).
    """
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 - expected_a

    k_a = get_k_factor(matches_a)
    k_b = get_k_factor(matches_b)

    new_a = round(rating_a + k_a * (score_a - expected_a))
    new_b = round(rating_b + k_b * ((1 - score_a) - expected_b))

    return new_a, new_b

def calculate_new_elo(winner_elo, winner_matches, loser_elo, loser_matches):
    """Wrapper réutilisable pour calculer le nouvel Elo d'un vainqueur et d'un perdant."""
    return calculate_new_ratings(winner_elo, loser_elo, score_a=1, matches_a=winner_matches, matches_b=loser_matches)

def select_matchup(items):
    """
    Matchmaking hybride :
    - 20% du temps : Tirage 100% aléatoire.
    - 80% du temps : Sélection d'un 1er élément, puis choix d'un 2nd dans une plage de ±150 Elo.
    """
    if len(items) < 2:
        return None, None

    # 20% d'aléatoire pur pour faire bouger le classement global
    if random.random() < 0.2:
        return random.sample(items, 2)

    # 80% de proximité Elo avec tolérance élargie
    item1 = random.choice(items)
    other_items = [i for i in items if i != item1]

    # Filtrage : tous les candidats à ±150 points Elo d'écart
    elo_range = 150
    candidates = [i for i in other_items if abs(i['elo'] - item1['elo']) <= elo_range]

    # Sécurité : si moins de 3 candidats sont dans la plage ±150,
    # on retombe sur les 10 plus proches absolus pour éviter d'être bloqué aux extrêmes
    if len(candidates) < 3:
        other_items.sort(key=lambda x: abs(x['elo'] - item1['elo']))
        candidates = other_items[:min(10, len(other_items))]

    # Tirage au sort du 2ème élément parmi les candidats valides
    item2 = random.choice(candidates)

    return item1, item2

def compute_and_update_vote(item_a, item_b, outcome):
    """
    Calcule les nouveaux Elo, détermine le gagnant/perdant, met à jour la mémoire
    et génère le message de résultat pour la bannière.
    """
    elo_a, matches_a = item_a.get('elo', 1000), item_a.get('matches_count', 0)
    elo_b, matches_b = item_b.get('elo', 1000), item_b.get('matches_count', 0)

    name_a = item_a.get('name') or item_a.get('title') or 'Élément A'
    name_b = item_b.get('name') or item_b.get('title') or 'Élément B'

    new_elo_a, new_elo_b = calculate_new_ratings(
        rating_a=elo_a, rating_b=elo_b, score_a=outcome, matches_a=matches_a, matches_b=matches_b
    )

    delta_a = new_elo_a - elo_a
    delta_b = new_elo_b - elo_b

    # Génération du message pour la bannière
    if outcome == 1.0:
        winner_id, loser_id = item_a.get('id'), item_b.get('id')
        last_result = f"Victoire de {name_a} (+{delta_a} Elo) face à {name_b} ({delta_b} Elo)"
    elif outcome == 0.0:
        winner_id, loser_id = item_b.get('id'), item_a.get('id')
        last_result = f"Victoire de {name_b} (+{delta_b} Elo) face à {name_a} ({delta_a} Elo)"
    else:
        winner_id, loser_id = item_a.get('id'), item_b.get('id')
        str_a = f"+{delta_a}" if delta_a >= 0 else f"{delta_a}"
        str_b = f"+{delta_b}" if delta_b >= 0 else f"{delta_b}"
        last_result = f"Match nul entre {name_a} ({str_a} Elo) et {name_b} ({str_b} Elo)"

    # Mise à jour en mémoire (session)
    item_a['elo'] = new_elo_a
    item_a['matches_count'] = matches_a + 1
    item_b['elo'] = new_elo_b
    item_b['matches_count'] = matches_b + 1

    # 5 valeurs retournées
    return new_elo_a, new_elo_b, winner_id, loser_id, last_result

def save_vote_async_generic(query_function, *args):
    """
    Exécute n'importe quelle fonction d'écriture SQL en arrière-plan dans un thread séparé.
    Garantit zéro latence côté interface utilisateur.
    """
    def _async_task():
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                query_function(cur, *args)
                conn.commit()
                cur.close()
            except Exception as e:
                print(f"⚠️ Erreur BDD asynchrone : {e}")
            finally:
                conn.close()

    threading.Thread(target=_async_task, daemon=True).start()