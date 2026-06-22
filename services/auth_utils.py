import bcrypt


# Liste blanche des rôles autorisés. Toute valeur hors de ce set doit être rejetée
# avant d'être persistée (évite la création d'un compte "admin" via POST forgé).
VALID_ROLES = frozenset({"rh", "salarie", "responsable"})

# Politique de mot de passe minimaliste, alignée sur les recommandations courantes
# pour une appli intranet (longueur > complexité forcée).
PASSWORD_MIN_LENGTH = 8

# Hash bcrypt constant d'un mot de passe factice. Sert à égaliser le temps de
# réponse du login lorsqu'un identifiant n'existe pas : on exécute toujours un
# `check_password` (réel ou factice) pour éviter l'énumération de comptes par
# timing (un identifiant inconnu répondrait sinon plus vite, faute de hachage).
DUMMY_HASH = "$2b$12$MJvk0HFcb7XTe2fOshIGZu16aJYnTMCeQYwhsm284ELrJQIfWpQ3y"


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password, hashed):
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def normaliser_role(role: str) -> str | None:
    """Retourne le rôle normalisé s'il est valide, sinon None."""
    if not role:
        return None
    r = role.strip().lower()
    return r if r in VALID_ROLES else None


def valider_mot_de_passe(password: str) -> str | None:
    """Retourne un message d'erreur si le mot de passe ne respecte pas la politique, sinon None."""
    if password is None:
        return "Mot de passe obligatoire."
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Mot de passe trop court ({PASSWORD_MIN_LENGTH} caractères minimum)."
    return None
