import os
import re
import requests
import psycopg2
from dotenv import load_dotenv

load_dotenv()

IMAGE_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images', 'genshin')
DATABASE_URL = os.getenv("DATABASE_URL")

WIKI_API_URL = "https://genshin-impact.fandom.com/api.php"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def slugify(name):
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    return name

def get_official_playable_characters():
    """Récupère la liste exacte des personnages jouables via l'API MediaWiki Fandom."""
    playable = {}
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
            break

        data = res.json()
        members = data.get("query", {}).get("categorymembers", [])

        for m in members:
            title = m["title"]
            if not title.startswith("Category:") and not title.startswith("Traveler"):
                cid = slugify(title)
                playable[cid] = title

        if "continue" in data:
            cmcontinue = data["continue"]["cmcontinue"]
        else:
            break

    return playable

def cleanup_and_populate():
    print("📡 Récupération de la liste officielle des personnages jouables...")
    playable_dict = get_official_playable_characters()
    print(f"🎯 {len(playable_dict)} personnages jouables officiels identifiés.\n")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Supprimer de la BDD les personnages non jouables
    cur.execute("SELECT character_id FROM genshin_characters;")
    db_chars = [row[0] for row in cur.fetchall()]

    to_delete = [cid for cid in db_chars if cid not in playable_dict]

    if to_delete:
        print(f"🧹 Nettoyage BDD : Suppression de {len(to_delete)} entités non jouables/PNJs...")
        cur.execute("DELETE FROM genshin_characters WHERE character_id = ANY(%s);", (to_delete,))
        conn.commit()

    # 2. Supprimer les fichiers images orphelins dans static/images/genshin/
    if os.path.exists(IMAGE_DIR):
        for filename in os.listdir(IMAGE_DIR):
            if filename.endswith(".png"):
                cid = filename[:-4]
                if cid not in playable_dict:
                    os.remove(os.path.join(IMAGE_DIR, filename))
                    print(f"🗑️ Image supprimée : {filename}")

    # 3. Récupérer les images pour les personnages jouables manquants
    downloaded = 0
    for cid, name in playable_dict.items():
        local_path = os.path.join(IMAGE_DIR, f"{cid}.png")

        if not os.path.exists(local_path):
            print(f"📥 Téléchargement de l'icône pour jouable : '{name}'...", end=" ", flush=True)

            formatted_name = name.replace(" ", "_")
            possible_files = [
                f"File:Character_{formatted_name}_Icon.png",
                f"File:{formatted_name}_Icon.png",
                f"File:UI_AvatarIcon_{formatted_name}.png"
            ]

            success = False
            for file_title in possible_files:
                params = {
                    "action": "query",
                    "titles": file_title,
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "format": "json"
                }
                try:
                    res = requests.get(WIKI_API_URL, headers=HEADERS, params=params, timeout=5)
                    if res.status_code == 200:
                        pages = res.json().get("query", {}).get("pages", {})
                        for p in pages.values():
                            if "imageinfo" in p and len(p["imageinfo"]) > 0:
                                img_url = p["imageinfo"][0]["url"]
                                img_data = requests.get(img_url, headers=HEADERS, timeout=5).content
                                with open(local_path, 'wb') as f:
                                    f.write(img_data)
                                print("✅ Ok")
                                success = True
                                downloaded += 1
                                break
                except Exception:
                    pass
                if success:
                    break

            if not success:
                print("⚠️ Image introuvable")

    cur.close()
    conn.close()

    print("\n" + "="*50)
    print("✨ BASE ET DOSSIER D'IMAGES PURGÉS AVEC SUCCÈS !")
    print(f"📊 Résultat final : {len(playable_dict)} personnages jouables enregistrés.")
    print("="*50)

if __name__ == '__main__':
    cleanup_and_populate()