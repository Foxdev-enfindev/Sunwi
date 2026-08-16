# routes/main.py
from flask import Blueprint, render_template, request, jsonify, session

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def hub():
    modules = [
        {
            'id': 'football',
            'title': 'Football',
            'category': 'Sport',
            'badge': 'Disponible',
            'active': True,
            'url': '/football/'
        },
        {
            'id': 'spotify',
            'title': 'Musique (Spotify)',
            'category': 'Personnel',
            'badge': 'Disponible',
            'active': True,
            'url': '/spotify/'
        },
        {
            'id': 'disney',
            'title': 'Films Disney',
            'category': 'Cinéma',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        },
        {
            'id': 'pokemon',
            'title': 'Pokémon',
            'category': 'Gaming',
            'badge': 'Bientôt',
            'active': False,
            'url': '#'
        }
    ]

    category_order = ['Sport', 'Personnel', 'Cinéma', 'Gaming']

    grouped = {}
    for m in modules:
        grouped.setdefault(m['category'], []).append(m)

    # Utilisation de la clé 'modules' au lieu de 'items' pour éviter le conflit avec dict.items()
    ordered_categories = [
        {'name': cat, 'modules': grouped[cat]}
        for cat in category_order if cat in grouped
    ]

    return render_template('hub.html', categories=ordered_categories)