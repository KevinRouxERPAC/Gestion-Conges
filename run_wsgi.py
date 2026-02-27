import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _script_dir:
    os.chdir(_script_dir)

def _log(msg):
    print(msg, flush=True)
    sys.stdout.flush()
    sys.stderr.flush()

_log("[run_wsgi] Demarrage...")

from app import create_app
from waitress import serve

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("HTTP_PLATFORM_PORT", os.environ.get("PORT", "5000")))
    host = os.environ.get("HOST", "127.0.0.1")
    _log("Waitress (production) : http://%s:%s" % (host, port))
    _log("Pour deux utilisateurs : onglet normal (RH) + navigation privee (salarie).")
    serve(app, host=host, port=port, threads=6)
