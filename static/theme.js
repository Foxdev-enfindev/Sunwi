// static/theme.js
const availableAccentColors = ['green', 'cyan', 'pink', 'orange', 'purple', 'yellow'];

// Initialisation au chargement du DOM
document.addEventListener('DOMContentLoaded', () => {
    const savedBgMode = localStorage.getItem('sunwi_bg_mode') || 'dark';
    document.documentElement.setAttribute('data-bg-mode', savedBgMode);

    let savedAccent = localStorage.getItem('sunwi_theme') || 'green';
    if (savedAccent === 'random') {
        savedAccent = availableAccentColors[Math.floor(Math.random() * availableAccentColors.length)];
    }
    document.documentElement.setAttribute('data-theme', savedAccent);
});

function setBgMode(mode) {
    document.documentElement.setAttribute('data-bg-mode', mode);
    localStorage.setItem('sunwi_bg_mode', mode);
}

function setAccentColor(color) {
    localStorage.setItem('sunwi_theme', color);
    
    let finalColor = color;
    if (color === 'random') {
        finalColor = availableAccentColors[Math.floor(Math.random() * availableAccentColors.length)];
    }
    
    document.documentElement.setAttribute('data-theme', finalColor);

    fetch('/spotify/set_theme/' + color, { method: 'POST' })
        .catch(err => console.error('Erreur sauvegarde thème :', err));
}