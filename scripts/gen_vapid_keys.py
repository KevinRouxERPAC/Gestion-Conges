#!/usr/bin/env python3
"""Genere une paire de cles VAPID pour Web Push. A executer une fois : pip install py-vapid puis python scripts/gen_vapid_keys.py.
Les fichiers .pem sont crees a la racine du projet (ou l'app les charge)."""
import os

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

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
private_path = os.path.join(BASE_DIR, "vapid_private.pem")
public_path = os.path.join(BASE_DIR, "vapid_public.pem")

vapid = Vapid01()
vapid.generate_keys()
vapid.save_key(private_path)
vapid.save_public_key(public_path)

pub_bytes = vapid.public_key.public_bytes(
    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
)
pub_b64 = b64urlencode(pub_bytes)
if isinstance(pub_b64, bytes):
    pub_b64 = pub_b64.decode("ascii")

print("Cles sauvegardees dans", private_path, "et", public_path)
print()
print("Variables d'environnement a definir :")
print("  VAPID_PRIVATE_KEY=vapid_private.pem")
print("  VAPID_PUBLIC_KEY=" + pub_b64)