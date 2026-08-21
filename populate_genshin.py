import os
import re
import time
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

IMAGE_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images', 'genshin')
DATABASE_URL = os.getenv("DATABASE_URL")

# API MediaWiki officielle de Fandom (bypass le blocage 403)
WIKI_API_URL = "https://genshin-impact.fandom.com/api.php"

HEADERS = {
    "User-Agent": "SunwiApp/1.0 (Contact: admin@sunwi.com)"
}

def get_db_connection():
    if not DATABASE_URL:
        raise ValueError("❌ DATABASE_URL introuvable dans .env")
    return psycopg2.connect(DATABASE_URL)

def setup_directory():
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)
        print(f"📁 Dossier créé : {IMAGE_DIR}\n")

def slugify(name):
    """Convertit un nom de personnage en ID (ex: Hu Tao -> hu-tao)."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    return name

def get_all_playable_characters():
    """Récupère tous les membres de la catégorie 'Playable Characters' via l'API MediaWiki."""
    characters = []
    cmcontinue = ""

    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": "Category:Playable_Characters",
            "cmlimit": "max",
            "format": "json"
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        res = requests.get(WIKI_API_URL, headers=HEADERS, params=params)
        if res.status_code != 200:
            print(f"❌ Erreur API Fandom : HTTP {res.status_code}")
            break

        data = res.json()
        members = data.get("query", {}).get("categorymembers", [])
        
        for member in members:
            title = member["title"]
            # Exclure le Voyageur / Traveler et les sous-pages de catégories
            if not title.startswith("Category:") and not title.startswith("Traveler"):
                characters.append(title)

        if "continue" in data:
            cmcontinue = data["continue"]["cmcontinue"]
        else:
            break

    return characters

def populate():
    setup_directory()

    print("📡 Interrogation de l'API MediaWiki Fandom...")
    char_titles = get_all_playable_characters()
    total = len(char_titles)
    
    if total == 0:
        print("❌ Aucun personnage trouvé.")
        return

    print(f"🔍 {total} personnages trouvés. Début de l'enregistrement...\n")

    conn = get_db_connection()
    cur = conn.cursor()

    upsert_sql = """
        INSERT INTO genshin_characters (character_id, name, title, element, weapon)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (character_id) DO UPDATE SET
            name = EXCLUDED.name,
            title = EXCLUDED.title,
            element = EXCLUDED.element,
            weapon = EXCLUDED.weapon;
    """

    success = 0
    failed = 0

    for idx, char_name in enumerate(char_titles, start=1):
        char_id = slugify(char_name)

        # 1. Sauvegarde en BDD
        try:
            # On initialise avec des valeurs par défaut, la BDD conserve les données
            cur.execute(upsert_sql, (char_id, char_name, "", "Anemo", "Sword"))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[{idx}/{total}] ❌ Échec BDD {char_name} : {e}")
            failed += 1
            continue

        # 2. Récupération de l'image (icône) via l'API d'image
        local_img = os.path.join(IMAGE_DIR, f"{char_id}.png")
        img_status = "Image existante"

        if not os.path.exists(local_img):
            # Tente de récupérer l'image d'icône officielle
            img_name = f"File:Character_{char_name.replace(' ', '_')}_Icon.png"
            img_params = {
                "action": "query",
                "titles": img_name,
                "prop": "imageinfo",
                "iiprop": "url",
                "format": "json"
            }
            try:
                time.sleep(0.1)
                img_res = requests.get(WIKI_API_URL, headers=HEADERS, params=img_params)
                pages = img_res.json().get("query", {}).get("pages", {})
                
                img_url = None
                for p in pages.values():
                    if "imageinfo" in p and len(p["imageinfo"]) > 0:
                        img_url = p["imageinfo"][0]["url"]

                if img_url:
                    r = requests.get(img_url, headers=HEADERS, timeout=10)
                    if r.status_code == 200:
                        with open(local_img, 'wb') as f:
                            f.write(r.content)
                        img_status = "Image DL"
                    else:
                        img_status = "Échec DL"
                else:
                    # Fallback sur l'API d'icône genshin.jmp.blue si l'image Fandom n'est pas trouvée
                    fallback_res = requests.get(f"https://genshin.jmp.blue/characters/{char_id}/icon", timeout=5)
                    if fallback_res.status_code == 200:
                        with open(local_img, 'wb') as f:
                            f.write(fallback_res.content)
                        img_status = "Image DL (Fallback)"
                    else:
                        img_status = "Pas d'image"
            except Exception:
                img_status = "Erreur DL"

        print(f"[{idx}/{total}] ✅ {char_name} ({img_status})")
        success += 1

    cur.close()
    conn.close()

    print("\n" + "="*50)
    print(f"📊 BILAN FINAL : {success} personnages traités, {failed} échecs.")
    print("="*50)

if __name__ == '__main__':
    populate()