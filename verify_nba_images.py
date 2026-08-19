import os
import requests
from dotenv import load_dotenv
from db import get_db_connection

load_dotenv()

def verify_and_fix_nba_images():
    conn = get_db_connection()
    if not conn:
        print("❌ Impossible de se connecter à la BDD.")
        return

    cur = conn.cursor()
    cur.execute("SELECT player_id, name FROM nba_players;")
    players = cur.fetchall()
    cur.close()
    conn.close()

    total_players = len(players)
    img_dir = os.path.join(os.path.dirname(__file__), 'static', 'images', 'nba')
    os.makedirs(img_dir, exist_ok=True)

    print(f"🔍 Vérification des images pour {total_players} joueurs NBA...\n")

    missing_players = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    for player_id, name in players:
        # Vérification des formats d'images courants
        has_image = any(
            os.path.exists(os.path.join(img_dir, f"{player_id}{ext}"))
            for ext in ['.png', '.jpg', '.webp', '.jpeg']
        )

        if not has_image:
            # Tentative de récupération automatique
            img_url = f"https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190/{player_id}.png"
            img_path = os.path.join(img_dir, f"{player_id}.png")
            
            try:
                res = requests.get(img_url, headers=headers, timeout=5)
                if res.status_code == 200 and len(res.content) > 1000:
                    with open(img_path, 'wb') as f:
                        f.write(res.content)
                    print(f"✅ Image récupérée pour : {name} ({player_id})")
                else:
                    missing_players.append((player_id, name))
            except Exception:
                missing_players.append((player_id, name))

    print("\n" + "="*40)
    if missing_players:
        print(f"⚠️ {len(missing_players)} / {total_players} joueurs n'ont pas d'image en local :")
        for pid, pname in missing_players:
            print(f"  • [{pid}] {pname}")
        print("\n💡 Note : Pour ces joueurs, l'application basculera automatiquement sur le CDN officiel via le fallback de la route /nba/player_photo/.")
    else:
        print(f"🎉 Parfait ! 100 % des joueurs ({total_players}/{total_players}) ont leur image enregistrée dans static/images/nba/.")
    print("="*40)

if __name__ == '__main__':
    verify_and_fix_nba_images()