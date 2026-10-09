import os
from pathlib import Path

# Load REACT_APP_BACKEND_URL from frontend/.env and MONGO_URL/DB_NAME from backend/.env
def _load(envpath):
    try:
        for ln in Path(envpath).read_text().splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)
    except Exception:
        pass

_load("/app/frontend/.env")
_load("/app/backend/.env")
