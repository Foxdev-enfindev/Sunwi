import os
import csv
import re
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

def extract_photo_and_id(raw_url, index):
    ids = re.findall(r'\d+', raw_url)
    if ids:
        pid = max(ids, key=len)
        if len(pid) >= 5:
            pid_padded = pid.zfill(6)
            photo_url = f"https://cdn.sofifa.net/players/{pid_padded[:3]}/{pid_padded[3:]}/24_120.png"
            return pid, photo_url

    return f"player_{index}", "https://cdn.sofifa.net/player_0.png"

def is_female_player(row):
    """Détecte si la ligne correspond à une joueuse."""
    gender = (row.get('gender') or row.get('Gender') or row.get('sex') or '').lower()
    if gender in ['f', 'female', 'women', 'w']:
        return True
        
    league = (row.get('League') or row.get('league_name') or '').lower()
    club = (row.get('Team') or row.get('team_name') or '').lower()

    female_keywords = [
        'women', 'wsl', 'arkema', 'liga f', 'nwsl', 'frauen', 
        'super league', 'feminine', 'féminine', 'femenina', 'femenino', 
        'femminile', 'feminino', 'bpi', 'gpfbl'
    ]
    
    # Vérification sur la ligue et le nom du club
    if any(keyword in league for keyword in female_keywords):
        return True
    if any(keyword in club for keyword in female_keywords):
        return True

    return False

def import_top_500_men_players(csv_filepath='ea_fc_players.csv'):
    if not DATABASE_URL or not os.path.exists(csv_filepath):
        print("❌ Fichier introuvable ou DATABASE_URL manquante.")
        return

    players = []

    with open(csv_filepath, mode='r', encoding='utf-8-sig', errors='ignore') as file:
        reader = csv.DictReader(file)
        
        for index, row in enumerate(reader, start=1):
            if is_female_player(row):
                continue

            name = (row.get('Name') or '').strip()
            overall_raw = row.get('OVR') or '0'
            
            try:
                overall = int(overall_raw)
            except ValueError:
                continue

            raw_url = row.get('url') or ''
            player_id, photo_url = extract_photo_and_id(raw_url, index)

            position = (row.get('Position') or 'N/A').split(',')[0].strip()
            club = (row.get('Team') or 'Libre').strip()
            nationality = (row.get('Nation') or 'Inconnue').strip()
            league = (row.get('League') or 'Inconnue').strip()

            if name and overall > 0:
                players.append({
                    'player_id': player_id,
                    'name': name,
                    'overall': overall,
                    'position': position,
                    'club': club,
                    'nationality': nationality,
                    'league': league,
                    'photo_url': photo_url
                })

    players.sort(key=lambda x: x['overall'], reverse=True)
    top_500 = players[:500]

    print(f"⚽ {len(top_500)} joueurs masculins retenus pour le Top 500.")

    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()

        # Nettoyage complet
        cur.execute("TRUNCATE TABLE football_players_scores CASCADE;")

        insert_query = """
            INSERT INTO football_players_scores 
            (player_id, name, overall, position, club, nationality, league, photo_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """

        for p in top_500:
            cur.execute(insert_query, (
                p['player_id'], p['name'], p['overall'], p['position'],
                p['club'], p['nationality'], p['league'], p['photo_url']
            ))

        conn.commit()
        cur.close()
        conn.close()
        print("✅ Re-importation masculine terminée !")

    except Exception as e:
        print(f"⚠️ Erreur BDD : {e}")

if __name__ == '__main__':
    import_top_500_men_players()