import os
import requests
from dotenv import load_dotenv
from db import get_db_connection

load_dotenv()

def populate_lol_data():
    # 1. Récupération de la dernière version de DataDragon
    version_url = "https://ddragon.leagueoflegends.com/api/versions.json"
    versions = requests.get(version_url).json()
    latest_version = versions[0]
    print(f"📦 Version DataDragon détectée : {latest_version}")

    # 2. Récupération des données des champions en français
    champions_url = f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/fr_FR/champion.json"
    data = requests.get(champions_url).json()['data']

    # 3. Création du dossier local d'images
    img_dir = os.path.join(os.path.dirname(__file__), 'static', 'images', 'lol')
    os.makedirs(img_dir, exist_ok=True)

    conn = get_db_connection()
    if not conn:
        print("❌ Erreur de connexion à la BDD")
        return

    cur = conn.cursor()
    count = 0

    for champ_key, champ_data in data.items():
        champ_id = champ_data['id']      # ex: "Aatrox", "LeeSin"
        name = champ_data['name']        # ex: "Aatrox", "Lee Sin"
        title = champ_data['title']      # ex: "l'Épée des darkin"
        tags = champ_data.get('tags', [])
        primary_role = tags[0] if tags else 'Fighter'

        # Insertion ou mise à jour en BDD
        cur.execute("""
            INSERT INTO lol_champions (champion_id, name, title, role)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (champion_id) DO UPDATE SET
                name = EXCLUDED.name,
                title = EXCLUDED.title,
                role = EXCLUDED.role;
        """, (champ_id, name, title, primary_role))

        # Téléchargement de l'icône du champion
        img_url = f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/img/champion/{champ_id}.png"
        img_path = os.path.join(img_dir, f"{champ_id}.png")

        if not os.path.exists(img_path):
            img_res = requests.get(img_url)
            if img_res.status_code == 200:
                with open(img_path, 'wb') as f:
                    f.write(img_res.content)

        count += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"✅ {count} champions insérés en BDD et icônes stockées dans static/images/lol/")

if __name__ == '__main__':
    populate_lol_data()