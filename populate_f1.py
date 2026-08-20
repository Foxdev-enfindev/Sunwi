import csv
import os
from db import get_db_connection

# Noms des fichiers CSV extraits
DRIVERS_CSV = 'drivers.csv'
RACES_CSV = 'races.csv'
RESULTS_CSV = 'results.csv'

def create_f1_tables():
    conn = get_db_connection()
    if not conn:
        print("❌ Connexion BDD impossible")
        return
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS f1_drivers (
            driver_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            nationality VARCHAR(50),
            code VARCHAR(10),
            permanent_number VARCHAR(10),
            wins INT DEFAULT 0,
            is_legend BOOLEAN DEFAULT FALSE,
            is_modern_era BOOLEAN DEFAULT FALSE,
            url VARCHAR(255)
        );

        CREATE TABLE IF NOT EXISTS user_f1_scores (
            user_id VARCHAR(255),
            driver_id VARCHAR(50),
            elo INT DEFAULT 1000,
            matches_count INT DEFAULT 0,
            PRIMARY KEY (user_id, driver_id)
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def populate_f1():
    # Vérification de la présence des fichiers
    missing = [f for f in [DRIVERS_CSV, RACES_CSV, RESULTS_CSV] if not os.path.exists(f)]
    if missing:
        print(f"❌ Fichiers manquants dans le dossier : {', '.join(missing)}")
        print("Assure-toi de les avoir extraits dans le dossier racine du projet.")
        return

    create_f1_tables()

    # 1. Cartographie des raceId à partir de la saison 2000
    modern_race_ids = set()
    print("📖 Analyse de races.csv...")
    with open(RACES_CSV, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                if int(row['year']) >= 2000:
                    modern_race_ids.add(row['raceId'])
            except (ValueError, KeyError):
                pass

    # 2. Comptage des victoires et détection des pilotes de l'ère 2000+
    wins_counter = {}        # { driverId_int: nb_victoires }
    modern_driver_ids = set() # { driverId_int }

    print("📖 Analyse de results.csv...")
    with open(RESULTS_CSV, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            d_id = row['driverId']
            race_id = row['raceId']
            position = str(row.get('position', '')).strip()
            position_text = str(row.get('positionText', '')).strip()

            # Identification des engagés en course depuis 2000
            if race_id in modern_race_ids:
                modern_driver_ids.add(d_id)

            # Identification des victoires
            if position == '1' or position_text == '1':
                wins_counter[d_id] = wins_counter.get(d_id, 0) + 1

    # Isolement du Top 100 des vainqueurs de l'histoire pour is_legend
    sorted_winners = sorted(wins_counter.items(), key=lambda x: x[1], reverse=True)
    top_100_legend_ids = {d_id for d_id, wins in sorted_winners[:100]}

    print(f"📊 Bilan de l'analyse :")
    print(f" - Victoires recensées : {len(wins_counter)} vainqueurs différents.")
    print(f" - Légendes qualifiées (Top 100 victoires) : {len(top_100_legend_ids)} pilotes.")
    print(f" - Pilotes de l'ère 2000-2026 : {len(modern_driver_ids)} pilotes.")

    # 3. Injection et mise à jour PostgreSQL via drivers.csv
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    count = 0

    print("💾 Enregistrement en base de données...")
    with open(DRIVERS_CSV, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_id = row['driverId']
            driver_ref = row['driverRef']
            forename = row.get('forename', '')
            surname = row.get('surname', '')
            full_name = f"{forename} {surname}".strip()
            nat = row.get('nationality', '')
            code = row.get('code', '')
            num = row.get('number', '')
            url = row.get('url', '')

            # Nettoyage des valeurs nuls issues du CSV Ergast ('\N')
            code = '' if code == '\\N' else code
            num = '' if num == '\\N' else num

            wins = wins_counter.get(raw_id, 0)
            is_leg = raw_id in top_100_legend_ids
            is_mod = raw_id in modern_driver_ids

            # Conservation uniquement des pilotes répondant à l'un des deux filtres
            if is_leg or is_mod:
                cur.execute("""
                    INSERT INTO f1_drivers (driver_id, name, nationality, code, permanent_number, wins, is_legend, is_modern_era, url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (driver_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        nationality = EXCLUDED.nationality,
                        code = EXCLUDED.code,
                        permanent_number = EXCLUDED.permanent_number,
                        wins = EXCLUDED.wins,
                        is_legend = EXCLUDED.is_legend,
                        is_modern_era = EXCLUDED.is_modern_era,
                        url = EXCLUDED.url;
                """, (driver_ref, full_name, nat, code, num, wins, is_leg, is_mod, url))
                count += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ Migration réussie ! {count} pilotes F1 insérés avec succès.")

if __name__ == '__main__':
    populate_f1()