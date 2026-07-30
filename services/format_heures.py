"""Formatage des durées en heures décimales pour l'affichage utilisateur.

Les heures RTT sont stockées en décimal (Numeric(6,2)) : la saisie se fait au
quart d'heure (multiple de 0,25 h) et l'acquisition hebdomadaire peut produire
des décimales quelconques (ex. 16,10 h). L'affichage standard de l'application
est en centièmes d'heure :

    5.25 -> "5,25 h"
    7.0  -> "7,00 h"
    0    -> "0,00 h"
    -2.5 -> "-2,50 h"  (solde négatif autorisé : report de déficit)
"""

# Multiple d'heure autorisé à la saisie (quart d'heure).
PAS_HEURES_RTT = 0.25


def format_heures_cent(valeur):
    """Convertit un nombre d'heures décimal en chaîne FR au centième (sans unité).

    Retourne la valeur telle quelle (str) si elle n'est pas numérique, pour rester
    sans danger côté template.
    """
    if valeur is None:
        return "0,00"
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return str(valeur)

    signe = "-" if v < 0 else ""
    return f"{signe}{abs(v):.2f}".replace(".", ",")


def format_heures_min(valeur):
    """Convertit un nombre d'heures décimal en chaîne « x,xx h » (FR)."""
    return f"{format_heures_cent(valeur)} h"


def format_jours(valeur):
    """Formate un nombre de jours pour l'affichage FR.

    Retire le « .0 » des entiers et utilise la virgule décimale :

        2.0  -> "2"
        1.5  -> "1,5"
        -15.0 -> "-15"

    Destiné aux messages adressés à l'utilisateur (flash). Applique la même règle
    que le filtre Jinja `nb_jours` (cf. app.py), qui s'appuie sur cette fonction.
    """
    if valeur is None:
        return "0"
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return str(valeur)
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}".replace(".", ",")


def est_multiple_quart(valeur) -> bool:
    """True si `valeur` est un multiple strict de 0,25 (tolérance flottante)."""
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return False
    return abs(round(v / PAS_HEURES_RTT) - (v / PAS_HEURES_RTT)) < 1e-9
