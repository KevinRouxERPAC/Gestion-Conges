#!/usr/bin/env python3
"""Vérifie la configuration Web Push (clés VAPID, module)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print('VAPID vapid_private.pem:', 'OK' if os.path.isfile(os.path.join(base, 'vapid_private.pem')) else 'MANQUANT')
from app import create_app
app = create_app()
with app.app_context():
    from services.webpush import _vapid_private_key
    print('Cle chargee:', 'OK' if _vapid_private_key() else 'NON')
    with app.test_client() as c:
        r = c.get('/notifications/vapid-public')
        d = r.get_json()
        print('Endpoint vapid-public:', 'OK' if (r.status_code == 200 and d.get('vapid_public_key')) else 'NON')
print('Verification terminee.')
