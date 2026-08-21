import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Liste des modifications spécifiques à appliquer
CUSTOM_UPDATES = [
    {"id": "aether", "name": "Aether", "element": "Adaptive", "weapon": "Sword"},
    {"id": "lumine", "name": "Lumine", "element": "Adaptive", "weapon": "Sword"},
    {"id": "aino", "name": "Aino", "element": "Hydro", "weapon": "Claymore"},
    {"id": "alyosha", "name": "Alyosha", "element": "Electro", "weapon": "Polearm"},
    {"id": "columbina", "name": "Columbina", "element": "Hydro", "weapon": "Catalyst"},
    {"id": "illuga", "name": "Illuga", "element": "Geo", "weapon": "Polearm"},
    {"id": "jahoda", "name": "Jahoda", "element": "Anemo", "weapon": "Bow"},
    {"id": "manekin", "name": "Manekin", "element": "Adaptive", "weapon": "Sword"},
    {"id": "wonderland-manekin", "name": "Wonderland Manekin", "element": "Adaptive", "weapon": "Sword"},
    {"id": "nefer", "name": "Nefer", "element": "Dendro", "weapon": "Catalyst"},
    {"id": "yumemizuki-mizuki", "name": "Yumemizuki Mizuki", "element": "Anemo", "weapon": "Catalyst"}
]

def update_custom_characters():
    if not DATABASE_URL:
        raise ValueError("❌ DATABASE_URL introuvable dans .env")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    upsert_sql = """
        INSERT INTO genshin_characters (character_id, name, title, element, weapon)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (character_id) DO UPDATE SET
            name = EXCLUDED.name,
            element = EXCLUDED.element,
            weapon = EXCLUDED.weapon;
    """

    updated = 0
    for char in CUSTOM_UPDATES:
        cur.execute(upsert_sql, (char["id"], char["name"], "", char["element"], char["weapon"]))
        updated += 1
        print(f"✅ {char['name']} ({char['id']}) -> {char['element']} | {char['weapon']}")

    conn.commit()
    cur.close()
    conn.close()

    print("\n" + "="*50)
    print(f"🚀 BDD Neon mise à jour : {updated} personnages mis à jour / ajoutés !")
    print("="*50)

if __name__ == '__main__':
    update_custom_characters()