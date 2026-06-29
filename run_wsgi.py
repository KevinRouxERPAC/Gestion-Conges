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

# Charge .env.local si présent (dev uniquement, jamais commité).
_env_local = os.path.join(_script_dir, ".env.local")
if os.path.isfile(_env_local):
    with open(_env_local) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())
    _log("[run_wsgi] .env.local charge.")

from app import create_app
from waitress import serve

app = create_app()

# Planificateur in-app : synchro ERP chaque vendredi (APScheduler, thread de fond).
# Démarré ici (et non dans create_app) pour ne pas tourner lors des migrations
# Alembic, des tests ou des commandes CLI flask.
from services.erp.scheduler import demarrer_scheduler, arreter_scheduler
import atexit

demarrer_scheduler(app)
atexit.register(arreter_scheduler)

if __name__ == "__main__":
    port = int(os.environ.get("HTTP_PLATFORM_PORT", os.environ.get("PORT", "5000")))
    host = os.environ.get("HOST", "127.0.0.1")
    _log("Waitress (production) : http://%s:%s" % (host, port))
    _log("Pour deux utilisateurs : onglet normal (RH) + navigation privee (salarie).")
    serve(app, host=host, port=port, threads=6)
