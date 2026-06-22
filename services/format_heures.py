"""Formatage des durées en heures décimales vers une notation horaire « H h MM ».

Les heures RTT sont stockées en décimal (Numeric(6,2)) : la saisie se fait au
quart d'heure (multiple de 0,25 h) et l'acquisition hebdomadaire peut produire
des décimales quelconques (ex. 16,10 h). Pour l'affichage, on convertit en
heures + minutes, sans ambiguïté :

    5.25 -> "5 h 15"   (5 h et 15 min)
    5.5  -> "5 h 30"
    7.0  -> "7 h"      (minutes nulles : on n'affiche pas " 00")
    0.25 -> "0 h 15"
    0    -> "0 h"
    -2.5 -> "-2 h 30"  (solde négatif autorisé : report de déficit)
"""

# Multiple d'heure autorisé à la saisie (quart d'heure).
PAS_HEURES_RTT = 0.25


def format_heures_min(valeur):
    """Convertit un nombre d'heures décimal en chaîne « H h MM » (FR).

    Arrondi à la minute la plus proche. Retourne la valeur telle quelle (str)
    si elle n'est pas numérique, pour rester sans danger côté template.
    """
    if valeur is None:
        return "0 h"
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return str(valeur)

    signe = "-" if v < 0 else ""
    total_minutes = int(round(abs(v) * 60))
    heures, minutes = divmod(total_minutes, 60)

    if minutes == 0:
        return f"{signe}{heures} h"
    return f"{signe}{heures} h {minutes:02d}"


def est_multiple_quart(valeur) -> bool:
    """True si `valeur` est un multiple strict de 0,25 (tolérance flottante)."""
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return False
    return abs(round(v / PAS_HEURES_RTT) - (v / PAS_HEURES_RTT)) < 1e-9
