#!/usr/bin/env python3
"""Génère une paire de clés VAPID pour Web Push. À exécuter une fois : pip install py-vapid puis python gen_vapid_keys.py"""
try:
    from vapid import Vapid01
except ImportError:
    try:
        from py_vapid import Vapid01
    except ImportError:
        print("Installez : pip install py-vapid")
        raise SystemExit(1)

from cryptography.hazmat.primitives import serialization
try:
    from py_vapid.utils import b64urlencode
except ImportError:
    from vapid.utils import b64urlencode

vapid = Vapid01()
vapid.generate_keys()
vapid.save_key("vapid_private.pem")
vapid.save_public_key("vapid_public.pem")

# Clé publique au format base64url (pour le frontend / applicationServerKey)
pub_bytes = vapid.public_key.public_bytes(
    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
)
pub_b64 = b64urlencode(pub_bytes)
if isinstance(pub_b64, bytes):
    pub_b64 = pub_b64.decode("ascii")

print("Clés sauvegardées dans vapid_private.pem et vapid_public.pem")
print()
print("Variables d'environnement à définir :")
print("  VAPID_PRIVATE_KEY=vapid_private.pem")
print("  VAPID_PUBLIC_KEY=" + pub_b64)
