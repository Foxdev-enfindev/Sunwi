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

function setAudioMode(mode) {
    // 1. Appel vers la route Spotify si disponible
    const status = (mode === 'silent') ? 1 : 0;
    
    fetch('/spotify/set_silent_mode/' + status, { method: 'POST' })
        .then(res => {
            if (res.ok) return res.json();
            // Fallback si la route /set_audio_mode globale est utilisée
            return fetch('/set_audio_mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: mode })
            }).then(r => r.json());
        })
        .then(() => {
            window.location.reload();
        })
        .catch(err => {
            console.error('Erreur changement mode audio :', err);
            // Rechargement secours au cas où
            window.location.reload();
        });
}