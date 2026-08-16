import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def fix_player_photos():
    if not DATABASE_URL:
        print("❌ DATABASE_URL manquante dans le .env")
        return

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()

    cur.execute("SELECT player_id FROM football_players_scores;")
    players = cur.fetchall()

    updated = 0
    for (player_id,) in players:
        clean_id = ''.join(filter(str.isdigit, str(player_id)))
        
        if len(clean_id) >= 5:
            pid = clean_id.zfill(6)
            photo_url = f"https://cdn.sofifa.net/players/{pid[:3]}/{pid[3:]}/24_120.png"
        else:
            photo_url = "https://cdn.sofifa.net/player_0.png"

        cur.execute("""
            UPDATE football_players_scores 
            SET photo_url = %s 
            WHERE player_id = %s;
        """, (photo_url, player_id))
        updated += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ {updated} photos mises à jour avec succès dans Neon !")

if __name__ == '__main__':
    fix_player_photos()