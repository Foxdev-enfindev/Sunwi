import os
import requests
from dotenv import load_dotenv
from db import get_db_connection

load_dotenv()

def import_all_pokemon():
    print("🔄 Récupération de la liste des Pokémon depuis PokéAPI (avec les noms français)...")
    url = "https://pokeapi.co/api/v2/pokemon?limit=1050"
    response = requests.get(url)
    if response.status_code != 200:
        print("❌ Erreur lors de la récupération de l'API.")
        return

    data = response.json()
    conn = get_db_connection()
    if not conn:
        print("❌ Erreur de connexion à la base de données.")
        return
        
    cur = conn.cursor()
    count = 0

    for item in data['results']:
        poke_detail = requests.get(item['url']).json()
        poke_id = poke_detail['id']
        
        # Récupération des données d'espèces (pour le nom français et la génération)
        species_url = poke_detail['species']['url']
        species_res = requests.get(species_url).json()
        
        # Recherche du nom en français
        name = poke_detail['name'].capitalize() # Fallback en anglais si non trouvé
        for entry in species_res.get('names', []):
            if entry['language']['name'] == 'fr':
                name = entry['name']
                break
        
        # Récupération des types (1 ou 2)
        types = [t['type']['name'] for t in poke_detail['types']]
        type1 = types[0]
        type2 = types[1] if len(types) > 1 else None
        
        # Sprites normal et shiny
        sprites = poke_detail['sprites']
        sprite_url = sprites.get('front_default')
        shiny_url = sprites.get('front_shiny')
        
        # Génération
        generation = species_res.get('generation', {}).get('name', 'unknown')

        # Insertion ou mise à jour en base
        cur.execute("""
            INSERT INTO pokemon_players (pokemon_id, name, generation, type1, type2, sprite_url, shiny_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pokemon_id) DO UPDATE SET
                name = EXCLUDED.name,
                generation = EXCLUDED.generation,
                type1 = EXCLUDED.type1,
                type2 = EXCLUDED.type2,
                sprite_url = EXCLUDED.sprite_url,
                shiny_url = EXCLUDED.shiny_url;
        """, (poke_id, name, generation, type1, type2, sprite_url, shiny_url))
        
        count += 1
        print(f"[{count}] Importé : {name} ({type1} / {type2 or 'aucun'})")

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Importation avec les noms en français terminée avec succès !")

if __name__ == '__main__':
    import_all_pokemon()