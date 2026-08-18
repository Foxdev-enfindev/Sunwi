import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Chargement des variables d'environnement depuis le fichier .env
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def fix_music_previews():
    if not DATABASE_URL:
        print("❌ DATABASE_URL manquante dans le fichier .env.")
        return

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Récupération des titres en base
    cur.execute("SELECT track_id, genre, year, name, artist FROM top100_tracks;")
    tracks = cur.fetchall()

    print(f"🔄 Analyse de {len(tracks)} titres...")
    updated_count = 0

    for track in tracks:
        query = f"{track['name']} {track['artist']}"
        try:
            # Recherche sur l'API publique Deezer
            res = requests.get('https://api.deezer.com/search', params={'q': query}, timeout=5)
            data = res.json()

            if data.get('data'):
                deezer_preview = data['data'][0].get('preview')
                if deezer_preview:
                    cur.execute("""
                        UPDATE top100_tracks 
                        SET preview_url = %s 
                        WHERE track_id = %s AND genre = %s AND year = %s;
                    """, (deezer_preview, track['track_id'], track['genre'], track['year']))
                    updated_count += 1
        except Exception as e:
            print(f"⚠️ Erreur sur {query} : {e}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Terminé ! {updated_count} URLs d'extraits audio mises à jour avec Deezer.")

if __name__ == '__main__':
    fix_music_previews()