import os
import requests
from dotenv import load_dotenv
from nba_api.stats.endpoints.commonallplayers import CommonAllPlayers
from db import get_db_connection

# On tente d'importer tqdm pour la barre de progression, sinon on utilise un fallback natif
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

load_dotenv()

def populate_all_nba_players():
    print("🏀 Récupération des joueurs auprès de l'API NBA...")
    
    try:
        # Import de la classe exacte pour éviter la confusion avec le module
        from nba_api.stats.endpoints.commonallplayers import CommonAllPlayers
        
        # Instanciation de la classe
        players_endpoint = CommonAllPlayers(is_only_current_season=1)
        data = players_endpoint.get_dict()['resultSets'][0]
    except Exception as e:
        print(f"❌ Erreur lors du contact avec l'API NBA : {e}")
        return

    headers_list = data['headers']
    rows = data['rowSet']

    id_idx = headers_list.index('PERSON_ID')
    name_idx = headers_list.index('DISPLAY_FIRST_LAST')
    team_city_idx = headers_list.index('TEAM_CITY')
    team_name_idx = headers_list.index('TEAM_NAME')

    conn = get_db_connection()
    if not conn:
        print("❌ Erreur de connexion à la base de données")
        return

    cur = conn.cursor()
    img_dir = os.path.join(os.path.dirname(__file__), 'static', 'images', 'nba')
    os.makedirs(img_dir, exist_ok=True)

    http_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    total_players = len(rows)
    print(f"⚙️ Traitement et téléchargement des images pour {total_players} joueurs...\n")

    # Utilisation de tqdm si disponible
    iterator = tqdm(rows, desc="Progression", unit="joueur") if HAS_TQDM else rows

    for idx, row in enumerate(iterator, 1):
        player_id = str(row[id_idx])
        name = row[name_idx]
        
        city = row[team_city_idx] or ''
        team_name = row[team_name_idx] or ''
        full_team = f"{city} {team_name}".strip() if team_name else "Agent libre"

        # Insertion / Mise à jour BDD
        cur.execute("""
            INSERT INTO nba_players (player_id, name, position, team, overall)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (player_id) DO UPDATE SET
                name = EXCLUDED.name,
                team = EXCLUDED.team;
        """, (player_id, name, 'Joueur', full_team, 80))

        # Téléchargement de l'image si absente
        img_path = os.path.join(img_dir, f"{player_id}.png")
        if not os.path.exists(img_path):
            img_url = f"https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190/{player_id}.png"
            try:
                res = requests.get(img_url, headers=http_headers, timeout=5)
                if res.status_code == 200 and len(res.content) > 1000:
                    with open(img_path, 'wb') as f:
                        f.write(res.content)
            except Exception:
                pass

        # Fallback affichage texte si tqdm n'est pas installé
        if not HAS_TQDM and idx % 25 == 0:
            print(f"Avancement : {idx}/{total_players} joueurs traités ({int(idx/total_players*100)}%)")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ Terminé ! {total_players} joueurs NBA synchronisés dans la BDD et images sauvegardées.")

if __name__ == '__main__':
    populate_all_nba_players()