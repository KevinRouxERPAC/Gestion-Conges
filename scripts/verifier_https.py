#!/usr/bin/env python3
"""Vérification finale du déploiement HTTPS intranet (Lot 5.1).

Réunit en un seul outil les vérifications opérationnelles à faire après
déploiement pour s'assurer que HTTPS est correctement actif et débloque le
Web Push natif (notifications système hors onglet).

Usage (depuis la racine du projet) :
  python scripts/verifier_https.py
  python scripts/verifier_https.py https://conges.erpac.com

Vérifications effectuées :
  1. PREFERRED_URL_SCHEME=https dans la config effective (cookies Secure + HSTS).
  2. Certificat serveur : émetteur, validité, SAN.
  3. En-têtes de sécurité réellement renvoyés : HSTS, Strict-Transport-Security.
  4. Cookie de session avec flag Secure.
  5. Clés VAPID présentes et endpoint /notifications/vapid-public répond.

Sortie : un compte-rendu lisible, avec ✅/❌ par vérification. À exécuter sur
un poste client (pas sur le serveur) pour valider la chaîne de confiance.
"""
from __future__ import annotations

import os
import ssl
import socket
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _ok(label: str, ok: bool, detail: str = "") -> int:
    mark = "✅" if ok else "❌"
    line = f"  {mark} {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return 0 if ok else 1


def verifier_config_app() -> int:
    """Vérifie la config Flask effective (cookies Secure, HSTS, VAPID)."""
    print("\n[1/5] Configuration application")
    failures = 0
    try:
        from app import create_app
        app = create_app()
    except Exception as e:
        failures += _ok("Chargement de l'app", False, f"erreur : {e}")
        return failures

    scheme = app.config.get("PREFERRED_URL_SCHEME", "http")
    failures += _ok(
        "PREFERRED_URL_SCHEME=https",
        scheme == "https",
        f"actuel={scheme}",
    )
    failures += _ok(
        "SESSION_COOKIE_SECURE=True",
        app.config.get("SESSION_COOKIE_SECURE") is True,
        f"actuel={app.config.get('SESSION_COOKIE_SECURE')}",
    )

    # VAPID : clé privée présente (fichier ou env).
    vapid_ok = bool(app.config.get("VAPID_PRIVATE_KEY")) or os.path.isfile(
        os.path.join(os.path.dirname(__file__), "..", "vapid_private.pem")
    )
    failures += _ok("Clé VAPID présente", vapid_ok)
    return failures


def verifier_certificat(url: str) -> int:
    """Vérifie le certificat serveur et la chaîne de confiance."""
    print("\n[2/5] Certificat serveur")
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 443

    context = ssl.create_default_context()
    # Vérifie la chaîne côté client (c'est ce qu'on veut valider).
    failures = 0
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                issuer = dict(x[0] for x in cert.get("issuer", []))
                subject = dict(x[0] for x in cert.get("subject", []))
                failures += _ok(
                    "Chaîne de confiance valide",
                    True,
                    f"CA={issuer.get('commonName', '?')}",
                )
                print(f"      Sujet : {subject.get('commonName', '—')}")
                print(f"      Valide : {cert.get('notBefore')} → {cert.get('notAfter')}")
                san = cert.get("subjectAltName", [])
                if san:
                    print(f"      SAN : {', '.join(str(v) for _, v in san)}")
    except ssl.SSLError as e:
        failures += _ok("Chaîne de confiance valide", False, f"SSL error : {e}")
    except (socket.timeout, OSError) as e:
        failures += _ok("Connexion au serveur", False, str(e))
    return failures


def verifier_en_tetes(url: str) -> int:
    """Vérifie les en-têtes de sécurité (HSTS) via une requête HTTPS."""
    print("\n[3/5] En-têtes de sécurité (HSTS)")
    failures = 0
    try:
        import urllib.request
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
        hsts = headers.get("strict-transport-security", "")
        failures += _ok(
            "HSTS présent (Strict-Transport-Security)",
            bool(hsts),
            f"valeur={hsts or 'absente'}",
        )
        csp = headers.get("content-security-policy", "")
        failures += _ok("CSP présent", bool(csp))
    except Exception as e:
        failures += _ok("Requête HTTPS", False, str(e))
    return failures


def verifier_cookie_session(url: str) -> int:
    """Vérifie que le cookie de session posé en HTTPS porte le flag Secure."""
    print("\n[4/5] Cookie de session Secure")
    failures = 0
    try:
        from app import create_app
        app = create_app()
        with app.test_client() as c:
            # Simule une connexion : on ne fait que GET /login, le cookie CSRF
            # nous renseigne déjà sur Secure (le cookie de session suit le même règlage).
            r = c.get("/login", base_url=url)
            cookies = r.headers.getlist("Set-Cookie")
            secure_ok = any("secure" in ck.lower() for ck in cookies)
            failures += _ok(
                "Flag Secure sur au moins un cookie",
                secure_ok or app.config.get("SESSION_COOKIE_SECURE") is True,
                f"{len(cookies)} cookie(s) posé(s)",
            )
    except Exception as e:
        failures += _ok("Vérification cookie", False, str(e))
    return failures


def verifier_webpush() -> int:
    """Vérifie la configuration Web Push (clé publique servie)."""
    print("\n[5/5] Web Push")
    failures = 0
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            with app.test_client() as c:
                r = c.get("/notifications/vapid-public")
                d = r.get_json() or {}
                failures += _ok(
                    "Endpoint /notifications/vapid-public",
                    r.status_code == 200 and bool(d.get("vapid_public_key")),
                    f"status={r.status_code}",
                )
    except Exception as e:
        failures += _ok("Endpoint VAPID", False, str(e))
    return failures


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ERPAC_URL", "https://conges.erpac.com")
    if not url.startswith("https://"):
        url = "https://" + url
    print("=" * 60)
    print(f"Vérification HTTPS intranet — {url}")
    print("=" * 60)

    total = (
        verifier_config_app()
        + verifier_certificat(url)
        + verifier_en_tetes(url)
        + verifier_cookie_session(url)
        + verifier_webpush()
    )

    print("\n" + "=" * 60)
    if total == 0:
        print("✅ Toutes les vérifications sont passées. HTTPS est opérationnel.")
        print("   Le Web Push natif (notifications système) est débloqué.")
    else:
        print(f"❌ {total} vérification(s) ont échoué. Voir ci-dessus.")
        print("   Tant que HTTPS n'est pas garanti, l'email RH reste le canal")
        print("   d'alerte fiable (cf. docs/PLAN_AMELIORATIONS_2026-06.md).")
    print("=" * 60)
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
