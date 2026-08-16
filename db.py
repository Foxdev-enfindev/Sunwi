# db.py
import os
import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_global_db():
    if not DATABASE_URL:
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Utilisateurs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                display_name VARCHAR(100),
                google_id VARCHAR(100) UNIQUE,
                password_hash VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Métadonnées statiques des joueurs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS football_players_scores (
                player_id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                overall INT NOT NULL,
                position VARCHAR(20),
                club VARCHAR(100),
                nationality VARCHAR(100),
                league VARCHAR(100),
                photo_url TEXT
            );
        """)

        # Scores Elo INDIVIDUELS par utilisateur
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_football_scores (
                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                player_id VARCHAR(50) REFERENCES football_players_scores(player_id) ON DELETE CASCADE,
                elo INT DEFAULT 1000,
                matches_count INT DEFAULT 0,
                PRIMARY KEY (user_id, player_id)
            );
        """)

        # Traçabilité des votes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_votes (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                module_id VARCHAR(50) NOT NULL,
                winner_id VARCHAR(100) NOT NULL,
                loser_id VARCHAR(100) NOT NULL,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Erreur initialisation BDD : {e}")