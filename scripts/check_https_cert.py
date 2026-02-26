#!/usr/bin/env python3
"""
Vérifier le certificat HTTPS présenté par un serveur (IIS, nginx, etc.).

Usage (depuis la racine du projet) :
  python scripts/check_https_cert.py
  python scripts/check_https_cert.py https://conges.erpac.com
  python scripts/check_https_cert.py https://localhost:443

Affiche : émetteur, sujet, dates de validité, noms (SAN), et erreurs éventuelles.
"""
import ssl
import socket
import sys
from urllib.parse import urlparse


def check_cert(url: str, timeout: int = 10) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 443)
    if parsed.scheme != "https":
        print("Attention : l'URL n'est pas en HTTPS, le certificat ne sera pas celui du serveur web.")
        print()

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # On affiche sans exiger une chaîne valide

    print("Connexion à {}:{} ...".format(host, port))
    cert_dict = None
    cert_der = None
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert_dict = ssock.getpeercert()
                cert_der = ssock.getpeercert(binary_form=True)
    except ssl.SSLError as e:
        print("Erreur SSL:", e)
        return
    except socket.timeout:
        print("Délai d'attente dépassé.")
        return
    except OSError as e:
        print("Erreur connexion:", e)
        return

    if cert_dict:
        subject = dict(x[0] for x in cert_dict.get("subject", []))
        issuer = dict(x[0] for x in cert_dict.get("issuer", []))
        not_before = cert_dict.get("notBefore", "")
        not_after = cert_dict.get("notAfter", "")
        san = cert_dict.get("subjectAltName", [])

        print()
        print("=== Certificat utilise pour HTTPS ===")
        print("Sujet (CN):", subject.get("commonName", "—"))
        print("Emetteur (CA):", issuer.get("organizationName", "—"), "|", issuer.get("commonName", "—"))
        print("Valide du :", not_before)
        print("Valide au  :", not_after)
        if san:
            print("Noms (SAN) :", ", ".join(str(v) for k, v in san))
        print()
        return

    # Fallback: ouvrir une connexion qui récupère le cert en binaire et décode
    context2 = ssl.create_default_context()
    context2.check_hostname = False
    context2.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with context2.wrap_socket(sock, server_hostname=host) as ssock:
            cert_der = ssock.getpeercert(binary_form=True)
    if not cert_der:
        print("Aucun certificat renvoye.")
        return

    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        print("Certificat recu (binaire). Pour afficher les details, installez: pip install cryptography")
        print("Ou verifiez dans le navigateur (cadenas) ou avec: openssl s_client -connect {}:{} -servername {}".format(host, port, host))
        return

    from cryptography.x509.oid import NameOID

    cert = x509.load_der_x509_certificate(cert_der, default_backend())
    subject = cert.subject
    issuer = cert.issuer
    cn_attrs = subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    issuer_cn_attrs = issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
    issuer_o_attrs = issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
    cn = cn_attrs[0].value if cn_attrs else "—"
    issuer_cn = issuer_cn_attrs[0].value if issuer_cn_attrs else "—"
    issuer_o = issuer_o_attrs[0].value if issuer_o_attrs else "—"

    print()
    print("=== Certificat utilise pour HTTPS ===")
    print("Sujet (CN):", cn)
    print("Emetteur (CA):", issuer_o, "|", issuer_cn)
    print("Valide du :", cert.not_valid_before_utc)
    print("Valide au  :", cert.not_valid_after_utc)
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        print("Noms (SAN) :", ", ".join(str(san)))
    except Exception:
        pass
    print()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://localhost"
    if not url.startswith("https://"):
        url = "https://" + url
    check_cert(url)

