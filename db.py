# db.py
import os
import psycopg2
from dotenv import load_dotenv

# Charge les variables du .env dès l'importation de db.py
load_dotenv()

def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return None
    return psycopg2.connect(database_url, sslmode='require')

def init_global_db():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Utilisateurs[cite: 5]
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
        
        # Métadonnées statiques des joueurs[cite: 5]
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

        # Scores Elo INDIVIDUELS par utilisateur[cite: 5]
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_football_scores (
                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                player_id VARCHAR(50) REFERENCES football_players_scores(player_id) ON DELETE CASCADE,
                elo INT DEFAULT 1000,
                matches_count INT DEFAULT 0,
                PRIMARY KEY (user_id, player_id)
            );
        """)

        # Métadonnées statiques des Pokémon
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pokemon_players (
                pokemon_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                generation VARCHAR(50),
                type1 VARCHAR(50) NOT NULL,
                type2 VARCHAR(50),
                sprite_url TEXT,
                shiny_url TEXT
            );
        """)

        # Scores Elo INDIVIDUELS des Pokémon par utilisateur
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_pokemon_scores (
                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                pokemon_id INT REFERENCES pokemon_players(pokemon_id) ON DELETE CASCADE,
                elo INT DEFAULT 1000.0,
                matches_count INT DEFAULT 0,
                PRIMARY KEY (user_id, pokemon_id)
            );
        """)

        # Traçabilité des votes[cite: 5]
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