import os
import re
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')
TMDB_API_KEY = os.environ.get('TMDB_API_KEY') # Optionnel mais idéal pour récupérer les affiches propres

def get_db_connection():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def parse_disney_file(filepath):
    if not os.path.exists(filepath):
        print(f"❌ Erreur : Le fichier {filepath} est introuvable.")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = content.strip().split('\n\n')
    movies = []

    for block in blocks:
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue
        
        title_line_idx = 0
        for i, line in enumerate(lines):
            if re.search(r'\(\d{4}\)', line):
                title_line_idx = i
                break
        
        title_match = re.search(r'^(.*?)\s*\((\d{4})\)$', lines[title_line_idx])
        if not title_match:
            continue
            
        fr_title = title_match.group(1).strip()
        year = int(title_match.group(2))

        en_title = fr_title
        next_idx = title_line_idx + 1
        if next_idx < len(lines) and not 'min.' in lines[next_idx] and not 'Sortie' in lines[next_idx] and not 'Long-métrage' in lines[next_idx] and not 'Film' in lines[next_idx]:
            if not re.match(r'^\d+[\.,]\d+', lines[next_idx]):
                en_title = lines[next_idx]

        is_pixar = "Pixar" in block

        movies.append({
            'fr_title': fr_title,
            'en_title': en_title,
            'year': year,
            'studio': 'Pixar' if is_pixar else 'Disney'
        })

    return movies

def fetch_tmdb_poster_url(title, year):
    """Interroge l'API TMDB pour récupérer l'URL de l'affiche officielle"""
    if not TMDB_API_KEY:
        return None
    try:
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={requests.utils.quote(title)}&year={year}"
        resp = requests.get(search_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('results', [])
            if results:
                poster_path = results[0].get('poster_path')
                if poster_path:
                    return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except Exception:
        pass
    return None

def import_and_download():
    conn = get_db_connection()
    if not conn:
        print("❌ Erreur : Impossible de se connecter à la base de données.")
        return

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Création des tables si elles n'existent pas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS disney_movies (
            movie_id SERIAL PRIMARY KEY,
            fr_title VARCHAR(255) NOT NULL,
            en_title VARCHAR(255),
            release_year INT,
            studio VARCHAR(50) DEFAULT 'Disney',
            poster_url TEXT,
            local_poster_path VARCHAR(255)
        );
    """)
    conn.commit()

    movies = parse_disney_file('disney_list.txt')
    total = len(movies)
    if total == 0:
        print("⚠️ Aucun film à importer.")
        cur.close()
        conn.close()
        return

    poster_dir = os.path.join('static', 'images', 'disney')
    os.makedirs(poster_dir, exist_ok=True)

    print(f"🚀 Début de l'importation et du téléchargement des affiches pour {total} films...\n")

    success_count = 0
    fail_count = 0

    for index, m in enumerate(movies, start=1):
        # 1. Insertion ou récupération du film en BDD
        cur.execute("""
            INSERT INTO disney_movies (fr_title, en_title, release_year, studio)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING movie_id;
        """, (m['fr_title'], m['en_title'], m['year'], m['studio']))
        
        row = cur.fetchone()
        if row:
            movie_id = row['movie_id']
        else:
            # S'il existe déjà, on récupère son ID
            cur.execute("SELECT movie_id FROM disney_movies WHERE fr_title = %s AND release_year = %s;", (m['fr_title'], m['year']))
            movie_id = cur.fetchone()['movie_id']
        
        conn.commit()

        # 2. Gestion de l'affiche locale
        local_path = os.path.join(poster_dir, f"{movie_id}.jpg")
        relative_path = f"images/disney/{movie_id}.jpg"

        if not os.path.exists(local_path):
            # Tente de récupérer l'URL de l'affiche via TMDB si la clé est présente
            poster_url = fetch_tmdb_poster_url(m['en_title'], m['year'])
            if poster_url:
                try:
                    img_resp = requests.get(poster_url, timeout=10)
                    if img_resp.status_code == 200:
                        with open(local_path, 'wb') as f:
                            f.write(img_resp.content)
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1
            else:
                fail_count += 1
        else:
            success_count += 1 # Déjà présent

        # Mise à jour du chemin local en BDD
        cur.execute("UPDATE disney_movies SET local_poster_path = %s WHERE movie_id = %s;", (relative_path, movie_id))
        conn.commit()

        percent = (index / total) * 100
        print(f"[{index}/{total}] ({percent:.1f}%) Traité : {m['fr_title']} ({m['year']})")

    cur.close()
    conn.close()
    print(f"\n✨ Importation et téléchargement terminés ! Affiches prêtes : {success_count}, Échecs d'affiche : {fail_count}")

if __name__ == '__main__':
    import_and_download()