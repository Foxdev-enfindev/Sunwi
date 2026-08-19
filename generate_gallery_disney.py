import os
from dotenv import load_dotenv

load_dotenv()
from db import get_db_connection

def generate_html_gallery():
    conn = get_db_connection()
    if not conn:
        print("Erreur de connexion à la base de données")
        return
    
    cur = conn.cursor()
    cur.execute("SELECT movie_id, fr_title, release_year FROM disney_movies ORDER BY movie_id;")
    movies = cur.fetchall()
    cur.close()
    conn.close()

    img_dir = os.path.join(os.path.dirname(__file__), 'static', 'images', 'disney')
    extensions = ['.jpg', '.png', '.webp', '.jpeg']

    html_content = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Vérification Affiches Disney</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; }
        .card { background: #1e293b; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #334155; }
        .card img { width: 100%; height: 210px; object-fit: cover; border-radius: 4px; background: #000; }
        .title { font-size: 0.85rem; font-weight: bold; margin-top: 6px; height: 36px; display: flex; align-items: center; justify-content: center; }
        .id { color: #38bdf8; font-size: 0.8rem; font-weight: bold; margin-bottom: 4px; }
        .missing { border: 2px solid #ef4444; }
    </style>
</head>
<body>
    <h2>Galerie d'inspection des affiches</h2>
    <div class="grid">
"""

    for movie_id, title, year in movies:
        img_path = None
        for ext in extensions:
            if os.path.exists(os.path.join(img_dir, f"{movie_id}{ext}")):
                img_path = f"static/images/disney/{movie_id}{ext}"
                break
        
        is_missing = img_path is None
        card_class = "card missing" if is_missing else "card"
        img_src = img_path if img_path else "https://via.placeholder.com/150x210?text=MANQUANT"

        html_content += f"""
        <div class="{card_class}">
            <div class="id">#{movie_id} ({year or 'N/A'})</div>
            <img src="{img_src}" alt="{title}">
            <div class="title">{title}</div>
        </div>"""

    html_content += """
    </div>
</body>
</html>"""

    with open("disney_gallery.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("✅ Fichier 'disney_gallery.html' généré. Double-clique dessus pour l'ouvrir !")

if __name__ == '__main__':
    generate_html_gallery()