import os
import csv
from dotenv import load_dotenv
from db import get_db_connection

load_dotenv()

CSV_FILE = 'nba2k.csv'

def import_kaggle_and_clean():
    if not os.path.exists(CSV_FILE):
        print(f"❌ Le fichier {CSV_FILE} est introuvable à la racine du projet.")
        return

    conn = get_db_connection()
    if not conn:
        print("❌ Erreur de connexion à la BDD")
        return

    cur = conn.cursor()
    updated_count = 0

    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Détection dynamique des colonnes Nom, Note et Position
        name_col = next((col for col in reader.fieldnames if col.lower().strip() in ['full_name', 'name', 'player', 'player_name']), None)
        rating_col = next((col for col in reader.fieldnames if col.lower().strip() in ['rating', 'overall', 'ovr', 'overall_rating']), None)
        pos_col = next((col for col in reader.fieldnames if col.lower().strip() in ['position', 'pos', 'primary_position', 'position_1']), None)

        if not name_col or not rating_col:
            print(f"❌ Colonnes manquantes. Colonnes trouvées : {reader.fieldnames}")
            cur.close()
            conn.close()
            return

        print(f"📊 Colonnes détectées -> Nom: '{name_col}', Note: '{rating_col}', Position: '{pos_col}'")

        for row in reader:
            player_name = row[name_col].strip()
            try:
                rating = int(row[rating_col])
            except (ValueError, TypeError):
                continue

            # Récupération de la position (par défaut 'Joueur' si colonne introuvable)
            position = row[pos_col].strip() if pos_col and row[pos_col] else 'Joueur'

            # Mise à jour de la note ET de la position
            cur.execute("""
                UPDATE nba_players
                SET overall = %s,
                    position = %s
                WHERE LOWER(name) = LOWER(%s);
            """, (rating, position, player_name))
            
            if cur.rowcount > 0:
                updated_count += 1

    print(f"✅ {updated_count} joueurs mis à jour avec leur vraie note et leur poste !")

    # Purge des scores et suppression des joueurs absents de 2K
    cur.execute("""
        DELETE FROM user_nba_scores 
        WHERE player_id IN (SELECT player_id FROM nba_players WHERE overall = 80);
    """)
    cur.execute("""
        DELETE FROM nba_players 
        WHERE overall = 80;
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("🧹 Nettoyage terminé !")

if __name__ == '__main__':
    import_kaggle_and_clean()