"""
Point d'entrée WSGI pour déploiement (IIS HttpPlatformHandler ou tests en mode production).
Lance l'application Flask avec Waitress (compatible Windows, multi-requêtes).

Lancer en local pour tester comme en production :
  python run_wsgi.py

Pour tester avec deux utilisateurs (RH + salarié) :
  - Onglet 1 : ouvrez http://127.0.0.1:5000 (ou le port affiché), connectez-vous en RH.
  - Onglet 2 : ouvrez une fenêtre de navigation privée (Ctrl+Shift+N) ou un autre
    navigateur, allez sur la même URL, connectez-vous en salarié.
  Les deux sessions restent indépendantes.
"""
import os
import sys
import json
import time

# #region agent log
def _dlog(msg, hypothesis_id, data=None):
    entry = json.dumps({"sessionId": "e6ee59", "timestamp": int(time.time() * 1000), "location": "run_wsgi.py", "message": msg, "hypothesisId": hypothesis_id, "data": data or {}}) + "\n"
    for base in [os.path.dirname(os.path.abspath(__file__)), os.environ.get("TEMP", ""), os.environ.get("TMP", "")]:
        if not base:
            continue
        try:
            log_dir = os.path.join(base, "logs") if base == os.path.dirname(os.path.abspath(__file__)) else base
            if not os.path.isdir(log_dir) and log_dir != base:
                os.makedirs(log_dir, exist_ok=True)
            p = os.path.join(log_dir, "debug-e6ee59.log")
            with open(p, "a", encoding="utf-8") as f:
                f.write(entry)
            break
        except Exception:
            continue
# #endregion

# Log immédiat pour diagnostic 502 (IIS) : voir logs\stdout.log
def _log(msg):
    print(msg, flush=True)
    sys.stdout.flush()
    sys.stderr.flush()

_dlog("run_wsgi script started", "H1", {"cwd_before": os.getcwd()})
_log("[run_wsgi] Demarrage...")

# Sous IIS, le répertoire de travail doit être la racine du projet (DB, config, vapid_private.pem, etc.)
_script_dir = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _script_dir:
    os.chdir(_script_dir)
_log("[run_wsgi] CWD=%s" % os.getcwd())
_dlog("CWD set", "H2", {"cwd": os.getcwd()})

# #region agent log
_dlog("before create_app import", "H2", {})
# #endregion
from app import create_app
from waitress import serve

# #region agent log
try:
    _dlog("calling create_app", "H3", {})
    # #endregion
    app = create_app()
    # #region agent log
    _dlog("create_app done", "H3", {})
except Exception as e:
    _dlog("create_app failed", "H3", {"error": str(e), "type": type(e).__name__})
    raise
# #endregion

if __name__ == "__main__":
    # IIS transmet le port via HTTP_PLATFORM_PORT ; sinon PORT ou 5000 par défaut
    port = int(os.environ.get("HTTP_PLATFORM_PORT", os.environ.get("PORT", "5000")))
    host = os.environ.get("HOST", "127.0.0.1")
    # #region agent log
    _dlog("before serve", "H4", {"host": host, "port": port, "HTTP_PLATFORM_PORT": os.environ.get("HTTP_PLATFORM_PORT")})
    # #endregion
    _log("Waitress (production) : http://%s:%s" % (host, port))
    _log("Pour deux utilisateurs : onglet normal (RH) + navigation privee (salarie).")
    try:
        serve(app, host=host, port=port, threads=6)
    except Exception as e:
        err_msg = "Waitress bind/run error: %s (%s)" % (e, type(e).__name__)
        _log(err_msg)
        _dlog("serve failed", "H4", {"error": str(e), "type": type(e).__name__})
        raise
