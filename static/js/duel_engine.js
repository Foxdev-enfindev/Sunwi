/**
 * Moteur universel de duel Sunwi
 * Extrait strictement du comportement de spotify_duel
 */

function triggerVoteAnimation(winnerKey) {
    const cardA = document.getElementById('card-a');
    const cardB = document.getElementById('card-b');
    const vsZone = document.getElementById('vsZone');

    if (vsZone) vsZone.classList.add('voting-in-progress');

    if (winnerKey === 'a') {
        if (cardA) cardA.classList.add('voted-winner');
        if (cardB) cardB.classList.add('voted-loser');
    } else if (winnerKey === 'b') {
        if (cardB) cardB.classList.add('voted-winner');
        if (cardA) cardA.classList.add('voted-loser');
    } else {
        if (cardA) cardA.classList.add('voted-winner');
        if (cardB) cardB.classList.add('voted-winner');
    }
}

function handleDuelVote(event, winnerKey, formId) {
    if (event) {
        event.stopPropagation();
        event.preventDefault(); // Empêche la soumission double
    }
    
    triggerVoteAnimation(winnerKey);
    
    setTimeout(() => {
        const form = document.getElementById(formId);
        if (form) form.submit();
    }, 150);
}