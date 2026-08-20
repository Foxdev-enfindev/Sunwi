# migrate_tracks.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

def migrate_tracks_ownership():
    client_id = os.environ.get('SPOTIPY_CLIENT_ID') or os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIPY_CLIENT_SECRET') or os.environ.get('SPOTIFY_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("❌ SPOTIFY_CLIENT_ID ou SPOTIFY_CLIENT_SECRET manquant dans le .env")
        return

    sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
        client_id=client_id, 
        client_secret=client_secret
    ))

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL manquante dans le .env")
        return

    conn = psycopg2.connect(db_url, sslmode='require')
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Récupération des enregistrements sans user_id dans tracks_scores
    cur.execute("SELECT DISTINCT playlist_id FROM tracks_scores WHERE user_id IS NULL OR user_id = '';")
    playlists = cur.fetchall()

    print(f"🔄 {len(playlists)} playlist(s) distincte(s) à analyser dans tracks_scores...")

    for row in playlists:
        p_id = row['playlist_id']
        if not p_id:
            continue
        try:
            # Récupération du propriétaire via l'API Spotify
            playlist_info = sp.playlist(p_id, fields='owner.id')
            owner_id = playlist_info['owner']['id']

            # Mise à jour globale pour tous les morceaux de cette playlist dans tracks_scores
            cur.execute(
                "UPDATE tracks_scores SET user_id = %s WHERE playlist_id = %s AND (user_id IS NULL OR user_id = '');",
                (owner_id, p_id)
            )
            print(f"✅ Morceaux de la playlist {p_id} -> Lying to user_id {owner_id}")
        except Exception as e:
            print(f"⚠️ Erreur pour la playlist {p_id} dans tracks_scores : {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("🚀 Migration de tracks_scores terminée !")

if __name__ == "__main__":
    migrate_tracks_ownership()