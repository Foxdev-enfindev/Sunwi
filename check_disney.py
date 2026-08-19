import os
from dotenv import load_dotenv

# Chargement explicite des variables d'environnement
load_dotenv()

from db import get_db_connection

def audit_disney_images():
    conn = get_db_connection()
    if not conn:
        print("❌ Impossible de se connecter à la base de données.")
        return

    cur = conn.cursor()
    cur.execute("SELECT movie_id, fr_title FROM disney_movies ORDER BY movie_id;")
    movies = cur.fetchall()
    cur.close()
    conn.close()

    img_dir = os.path.join(os.path.dirname(__file__), 'static', 'images', 'disney')
    
    if not os.path.exists(img_dir):
        print(f"❌ Le dossier {img_dir} n'existe pas !")
        return

    extensions = ['.jpg', '.png', '.webp', '.jpeg']
    missing = []
    found_count = 0

    print(f"--- Vérification des affiches Disney ({len(movies)} films en base) ---\n")

    for movie_id, title in movies:
        has_file = False
        for ext in extensions:
            if os.path.exists(os.path.join(img_dir, f"{movie_id}{ext}")):
                has_file = True
                found_count += 1
                break
        
        if not has_file:
            missing.append((movie_id, title))

    if missing:
        print("Affiches manquantes ou mal nommées :")
        for m_id, title in missing:
            print(f" - ID {m_id} : {title}")
    else:
        print("Toutes les affiches sont présentes !")

    print(f"\nRésumé : {found_count}/{len(movies)} affiches trouvées. {len(missing)} manquantes.")

if __name__ == '__main__':
    audit_disney_images()