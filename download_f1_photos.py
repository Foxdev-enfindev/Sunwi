import os
import requests
import json
from db import get_db_connection

IMG_DIR = os.path.join('static', 'images', 'f1')

# URLs des dépôts d'images F1 communautaires
F1DB_IMG_BASE = "https://raw.githubusercontent.com/f1db/f1db-images/main/src/drivers"
MEDIAWIKI_COMMONS_API = "https://commons.wikimedia.org/w/api.php"

def fetch_wikimedia_commons_portrait(driver_name, headers):
    """Recherche un portrait officiel sur Wikimedia Commons via API"""
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"File:{driver_name} portrait F1",
        "gsrlimit": 1,
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "iiurlwidth": 500,
        "format": "json"
    }
    try:
        res = requests.get(MEDIAWIKI_COMMONS_API, params=params, headers=headers, timeout=5)
        if res.status_code == 200:
            pages = res.json().get('query', {}).get('pages', {})
            for p_id, p_data in pages.items():
                imageinfo = p_data.get('imageinfo', [])
                if imageinfo:
                    mime = imageinfo[0].get('mime', '')
                    if 'image' in mime:
                        return imageinfo[0].get('thumburl') or imageinfo[0].get('url')
    except Exception:
        pass
    return None

def fetch_f1db_image(driver_id, headers):
    """Tente de récupérer l'image depuis le repo F1DB"""
    for ext in ['jpg', 'png', 'svg']:
        url = f"{F1DB_IMG_BASE}/{driver_id}/driver.{ext}"
        try:
            res = requests.head(url, headers=headers, timeout=3)
            if res.status_code == 200:
                return url
        except Exception:
            pass
    return None

def download_driver_photos():
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)

    conn = get_db_connection()
    if not conn:
        print("❌ Connexion BDD impossible")
        return
    
    cur = conn.cursor()
    cur.execute("SELECT driver_id, name FROM f1_drivers;")
    drivers = cur.fetchall()
    cur.close()
    conn.close()

    headers = {'User-Agent': 'SunwiApp/4.0 (contact@sunwi.com)'}
    
    downloaded = 0
    skipped = 0
    failed = 0

    print(f"🏎️ Recherche ciblée sur F1DB et Wikimedia Commons...")

    for driver_id, name in drivers:
        existing = [ext for ext in ['.jpg', '.png', '.webp', '.jpeg'] if os.path.exists(os.path.join(IMG_DIR, f"{driver_id}{ext}"))]
        if existing:
            skipped += 1
            continue

        # 1. Tentative F1DB
        img_url = fetch_f1db_image(driver_id, headers)
        
        # 2. Secours Wikimedia Commons
        if not img_url:
            img_url = fetch_wikimedia_commons_portrait(name, headers)

        if img_url:
            try:
                img_res = requests.get(img_url, headers=headers, timeout=8)
                if img_res.status_code == 200:
                    file_path = os.path.join(IMG_DIR, f"{driver_id}.jpg")
                    with open(file_path, 'wb') as f:
                        f.write(img_res.content)
                    print(f"✅ [{driver_id}] Image récupérée : {name}")
                    downloaded += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        else:
            print(f"⚠️ [{driver_id}] Aucun portrait libre trouvé : {name}")
            failed += 1

    print(f"\n📊 Bilan : {downloaded} nouvelles photos, {skipped} déjà acquises, {failed} sans image.")

if __name__ == '__main__':
    download_driver_photos()