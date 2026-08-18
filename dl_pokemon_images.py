import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def download_images():
    conn = get_db_connection()
    if not conn:
        print("❌ Erreur : Impossible de se connecter à la base de données.")
        return

    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT pokemon_id, name, sprite_url, shiny_url FROM pokemon_players;")
    except Exception as e:
        print(f"❌ Erreur lors de la requête SQL : {e}")
        cur.close()
        conn.close()
        return

    pokemons = cur.fetchall()
    cur.close()
    conn.close()

    total = len(pokemons)
    if total == 0:
        print("⚠️ Aucun Pokémon trouvé dans la table pokemon_players.")
        return

    base_dir = os.path.join('static', 'images', 'pokemon')
    normal_dir = os.path.join(base_dir, 'normal')
    shiny_dir = os.path.join(base_dir, 'shiny')

    os.makedirs(normal_dir, exist_ok=True)
    os.makedirs(shiny_dir, exist_ok=True)

    print(f"🚀 Début du téléchargement pour {total} Pokémon...\n")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    success_count = 0
    fail_count = 0

    for index, p in enumerate(pokemons, start=1):
        p_id = p.get('pokemon_id')
        p_name = p.get('name', 'Inconnu')
        normal_url = p.get('sprite_url')
        shiny_url = p.get('shiny_url')

        if normal_url:
            normal_path = os.path.join(normal_dir, f"{p_id}.png")
            if not os.path.exists(normal_path):
                try:
                    resp = requests.get(normal_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        with open(normal_path, 'wb') as f:
                            f.write(resp.content)
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1

        if shiny_url:
            shiny_path = os.path.join(shiny_dir, f"{p_id}.png")
            if not os.path.exists(shiny_path):
                try:
                    resp = requests.get(shiny_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        with open(shiny_path, 'wb') as f:
                            f.write(resp.content)
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1

        success_count += 1
        percent = (index / total) * 100
        print(f"[{index}/{total}] ({percent:.1f}%) Téléchargé : ID {p_id} - {p_name}")

    print(f"\n✨ Téléchargement terminé ! Succès : {success_count}, Erreurs : {fail_count}")
    print(f"📁 Les images sont enregistrées dans : {base_dir}")

if __name__ == '__main__':
    download_images()