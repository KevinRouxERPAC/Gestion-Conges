from datetime import date, timedelta


def calculer_paques(annee):
    """Calcul de la date de PÃ¢ques par l'algorithme de Meeus/Jones/Butcher."""
    a = annee % 19
    b = annee // 100
    c = annee % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    jour = ((h + l - 7 * m + 114) % 31) + 1
    return date(annee, mois, jour)


def get_jours_feries(annee):
    """Retourne la liste des jours fÃ©riÃ©s franÃ§ais pour une annÃ©e donnÃ©e."""
    paques = calculer_paques(annee)
    lundi_paques = paques + timedelta(days=1)
    ascension = paques + timedelta(days=39)
    lundi_pentecote = paques + timedelta(days=50)

    feries = [
        (date(annee, 1, 1), "Jour de l'An"),
        (lundi_paques, "Lundi de PÃ¢ques"),
        (date(annee, 5, 1), "FÃªte du Travail"),
        (date(annee, 5, 8), "Victoire 1945"),
        (ascension, "Ascension"),
        (lundi_pentecote, "Lundi de PentecÃ´te"),
        (date(annee, 7, 14), "FÃªte Nationale"),
        (date(annee, 8, 15), "Assomption"),
        (date(annee, 11, 1), "Toussaint"),
        (date(annee, 11, 11), "Armistice"),
        (date(annee, 12, 25), "NoÃ«l"),
    ]
    return feries
