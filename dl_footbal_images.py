import os
import requests
from db import get_db_connection

def download_all_player_images():
    # Création du dossier local s'il n'existe pas
    output_dir = os.path.join('static', 'images', 'football')
    os.makedirs(output_dir, exist_ok=True)

    conn = get_db_connection()
    if not conn:
        print("❌ Erreur de connexion à la base de données.")
        return
    
    cur = conn.cursor()
    cur.execute("SELECT player_id, photo_url FROM football_players_scores;")
    players = cur.fetchall()
    cur.close()
    conn.close()

    print(f"📥 Début du téléchargement de {len(players)} images de joueurs...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://sofifa.com/'
    }

    success_count = 0
    for player_id, photo_url in players:
        if not photo_url:
            continue
        
        file_path = os.path.join(output_dir, f"{player_id}.png")
        
        # Si l'image existe déjà localement, on évite de la retélécharger
        if os.path.exists(file_path):
            success_count += 1
            continue

        try:
            resp = requests.get(photo_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(resp.content)
                success_count += 1
            else:
                print(f"⚠️ Échec pour le joueur {player_id} (Statut: {resp.status_code})")
        except Exception as e:
            print(f"⚠️ Erreur pour le joueur {player_id}: {e}")

    print(f"✅ Téléchargement terminé ! {success_count}/{len(players)} images stockées dans '{output_dir}'.")

if __name__ == '__main__':
    download_all_player_images()