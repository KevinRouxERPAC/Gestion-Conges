import os
import sys
import json
import time

_script_dir = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _script_dir:
    os.chdir(_script_dir)

def _log(msg):
    print(msg, flush=True)
    sys.stdout.flush()
    sys.stderr.flush()


# region agent log (debug-a810eb)
def _agent_boot_log(message, data):
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "debug-a810eb.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        payload = {
            "sessionId": "a810eb",
            "runId": os.environ.get("AGENT_DEBUG_RUN_ID", "pre-fix"),
            "hypothesisId": "H5",
            "location": "run_wsgi.py:boot",
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


# endregion agent log (debug-a810eb)

_log("[run_wsgi] Demarrage...")
_agent_boot_log("run_wsgi start", {"cwd": os.getcwd(), "scriptDir": _script_dir})



from app import create_app
from waitress import serve

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("HTTP_PLATFORM_PORT", os.environ.get("PORT", "5000")))
    host = os.environ.get("HOST", "127.0.0.1")
    _agent_boot_log("waitress serve call", {"host": host, "port": port})
    _log("Waitress (production) : http://%s:%s" % (host, port))
    _log("Pour deux utilisateurs : onglet normal (RH) + navigation privee (salarie).")
    serve(app, host=host, port=port, threads=6)
