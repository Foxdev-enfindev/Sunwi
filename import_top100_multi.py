import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET')

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def get_deezer_preview(track_name, artist_name):
    """Recherche l'extrait 30s sur Deezer si Spotify ne l'a pas."""
    try:
        query = f'artist:"{artist_name}" track:"{track_name}"'
        url = f"https://api.deezer.com/search?q={requests.utils.quote(query)}"
        res = requests.get(url, timeout=5).json()
        
        items = res.get('data', [])
        if items and items[0].get('preview'):
            return items[0]['preview']
            
        # Deuxième essai plus souple sans guillemets si rien n'est trouvé
        query_soft = f'{artist_name} {track_name}'
        url_soft = f"https://api.deezer.com/search?q={requests.utils.quote(query_soft)}"
        res_soft = requests.get(url_soft, timeout=5).json()
        items_soft = res_soft.get('data', [])
        
        if items_soft and items_soft[0].get('preview'):
            return items_soft[0]['preview']
    except Exception as e:
        print(f"⚠️ Erreur récupération Deezer pour {track_name} : {e}")
    
    return ''

def import_top100_genre_years(genre_name='kpop', years=range(2020, 2026)):
    if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET or not DATABASE_URL:
        print("❌ Erreur : Variables d'environnement introuvables dans le .env.")
        return

    sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
        client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET
    ))

    conn = get_db()
    cur = conn.cursor()

    for yr in years:
        print(f"\n🚀 Importation {genre_name.upper()} — Année {yr}...")
        
        queries = [f'kpop year:{yr}', f'k-pop year:{yr}']
        tracks_found = []
        seen_ids = set()

        for q in queries:
            if len(tracks_found) >= 100:
                break
                
            offset = 0
            while len(tracks_found) < 100 and offset < 300:
                try:
                    results = sp.search(q=q, type='track', limit=10, offset=offset, market='FR')
                    items = results.get('tracks', {}).get('items', []) if results else []
                except Exception as e:
                    print(f"⚠️ Erreur API Spotify (offset {offset}) : {e}")
                    break

                if not items:
                    break

                for track in items:
                    if not track or not track.get('id'):
                        continue
                    
                    track_id = track['id']
                    if track_id in seen_ids:
                        continue

                    track_name = track.get('name', 'Inconnu')
                    artists = ", ".join([a['name'] for a in track.get('artists', [])]) or 'Inconnu'
                    
                    # 1. Vérification preview Spotify
                    preview_url = track.get('preview_url')
                    
                    # 2. Secours via Deezer si Spotify n'a pas d'extrait
                    if not preview_url:
                        preview_url = get_deezer_preview(track_name, artists)

                    # Si toujours aucun extrait trouvé, on passe au morceau suivant
                    if not preview_url:
                        continue

                    seen_ids.add(track_id)
                    images = track.get('album', {}).get('images', [])

                    tracks_found.append({
                        'id': track_id,
                        'name': track_name,
                        'artist': artists,
                        'year': yr,
                        'country': 'KR',
                        'genre': genre_name,
                        'cover_url': images[0]['url'] if images else '',
                        'preview_url': preview_url
                    })

                    if len(tracks_found) >= 100:
                        break

                offset += 10

        # Insertion / Upsert dans Neon SQL
        for t in tracks_found:
            cur.execute("""
                INSERT INTO top100_tracks (track_id, name, artist, year, country, genre, cover_url, preview_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (track_id, genre, year) DO UPDATE SET
                    name = EXCLUDED.name,
                    artist = EXCLUDED.artist,
                    cover_url = EXCLUDED.cover_url,
                    preview_url = EXCLUDED.preview_url;
            """, (t['id'], t['name'], t['artist'], t['year'], t['country'], t['genre'], t['cover_url'], t['preview_url']))

        conn.commit()
        print(f"✅ {len(tracks_found)} titres validés avec extrait 30s pour {yr}.")

    cur.close()
    conn.close()
    print("\n🎉 Importation globale terminée avec succès !")

if __name__ == '__main__':
    import_top100_genre_years(genre_name='kpop', years=range(2020, 2026))