import os
import shutil
from db import get_db_connection

IMG_DIR = os.path.join('static', 'images', 'f1')
DEFAULT_PNG_PATH = os.path.join('static', 'images', 'default_driver.png')
HTML_OUTPUT_PATH = 'f1_gallery.html'

def assign_default_images_and_generate_html():
    if not os.path.exists(DEFAULT_PNG_PATH):
        print(f"❌ Impossible de trouver {DEFAULT_PNG_PATH}")
        return

    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)

    conn = get_db_connection()
    if not conn:
        print("❌ Connexion BDD impossible")
        return
    
    cur = conn.cursor()
    cur.execute("SELECT driver_id, name, nationality, wins, is_legend, is_modern_era FROM f1_drivers ORDER BY wins DESC, name ASC;")
    drivers = cur.fetchall()
    cur.close()
    conn.close()

    default_assigned = 0
    gallery_items = []

    for driver_id, name, nationality, wins, is_legend, is_modern_era in drivers:
        # Vérification si une image personnalisée existe déjà
        existing = [ext for ext in ['.jpg', '.png', '.webp', '.jpeg'] if os.path.exists(os.path.join(IMG_DIR, f"{driver_id}{ext}"))]
        
        if existing:
            img_rel_path = f"static/images/f1/{driver_id}{existing[0]}"
            has_custom_photo = True
        else:
            # Copie de ton default_driver.png au nom du driver_id
            target_path = os.path.join(IMG_DIR, f"{driver_id}.png")
            shutil.copy(DEFAULT_PNG_PATH, target_path)
            img_rel_path = f"static/images/f1/{driver_id}.png"
            has_custom_photo = False
            default_assigned += 1

        gallery_items.append({
            'id': driver_id,
            'name': name,
            'nationality': nationality or 'Inconnue',
            'wins': wins or 0,
            'is_legend': is_legend,
            'is_modern': is_modern_era,
            'img_path': img_rel_path,
            'has_custom_photo': has_custom_photo
        })

    # Génération du fichier HTML autonome
    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Galerie des Pilotes F1 — Sunwi</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #0f172a; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }}
        .card-driver {{
            background: linear-gradient(145deg, #1e293b, #0f172a);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .card-driver:hover {{
            transform: translateY(-4px);
            border-color: rgba(255, 215, 0, 0.4);
        }}
        .driver-img {{
            height: 160px;
            object-fit: contain;
            background-color: #020617;
            width: 100%;
            padding: 10px;
        }}
        .badge-legend {{ background-color: #d97706; color: #fff; }}
        .badge-modern {{ background-color: #0284c7; color: #fff; }}
        .badge-default {{ background-color: #475569; color: #cbd5e1; }}
    </style>
</head>
<body class="p-4">
    <div class="container-fluid">
        <header class="mb-4 pb-3 border-bottom border-secondary d-flex justify-content-between align-items-center">
            <div>
                <h1 class="h2 text-warning fw-bold mb-1">🏎️ Galerie des Pilotes F1 — Sunwi</h1>
                <p class="text-secondary mb-0">{len(drivers)} pilotes référencés au total</p>
            </div>
            <div class="text-end">
                <span class="badge bg-success fs-6 me-2">{len(drivers) - default_assigned} photos personnalisées</span>
                <span class="badge badge-default fs-6">{default_assigned} images par défaut</span>
            </div>
        </header>

        <div class="row row-cols-2 row-cols-sm-3 row-cols-md-4 row-cols-lg-6 g-3">
"""

    for item in gallery_items:
        badges = []
        if item['is_legend']:
            badges.append('<span class="badge badge-legend">👑 Légende</span>')
        if item['is_modern']:
            badges.append('<span class="badge badge-modern">🏎️ 2000+</span>')
        if not item['has_custom_photo']:
            badges.append('<span class="badge badge-default">Défaut</span>')

        badges_html = " ".join(badges)

        html_content += f"""
            <div class="col">
                <div class="card-driver h-100 p-2 d-flex flex-column justify-content-between">
                    <div>
                        <img src="{item['img_path']}" alt="{item['name']}" class="driver-img rounded mb-2" loading="lazy">
                        <div class="fw-bold text-light text-truncate" title="{item['name']}">{item['name']}</div>
                        <div class="text-secondary small">{item['nationality']} • 🏆 {item['wins']}</div>
                    </div>
                    <div class="mt-2 d-flex flex-wrap gap-1">
                        {badges_html}
                    </div>
                </div>
            </div>
"""

    html_content += """
        </div>
    </div>
</body>
</html>
"""

    with open(HTML_OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✨ Opération terminée !")
    print(f" - {default_assigned} copilations de 'default_driver.png' créées.")
    print(f" - Galerie générée : {os.path.abspath(HTML_OUTPUT_PATH)}")

if __name__ == '__main__':
    assign_default_images_and_generate_html()