import sys
import os
import secrets
import uvicorn
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from supabase import create_client

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
TABLE = "hotel_data"
ROW_ID = 1  # single row: the whole hotel state lives in one record

# PWA assets. Served through explicit routes, one per file, and never through a
# StaticFiles mount: mounting the project directory would expose data.json,
# api.py and any .env file. An allow-list is the whole point here — a path
# parameter joined onto a directory would let `..%2f` climb out of it.
ICONS_DIR = BASE_DIR / "icons"
ALLOWED_ICONS = {"icon-192.png", "icon-512.png"}


def _fatal(problem: str, fix: str) -> None:
    """Print a loud, unmissable error to the log and stop the process.

    Render only surfaces stdout/stderr, and a raw traceback is easy to lose in
    a long deploy log. Printing a labelled block and flushing it before exiting
    guarantees the real cause is visible, with no traceback noise on top.
    """
    print("", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("ERROR CRITICO: la aplicacion no puede arrancar", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"  Causa:   {problem}", file=sys.stderr)
    print(f"  Solucion: {fix}", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    sys.stderr.flush()
    # os._exit, not sys.exit: this runs while uvicorn is importing the module
    # inside its event loop, and a SystemExit would unwind through asyncio and
    # bury this message under ~30 lines of traceback. Nothing needs cleaning up
    # at import time and stderr is already flushed, so a hard stop is safe.
    # Exit code 1 marks the deploy as failed instead of leaving a zombie service.
    os._exit(1)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        # Esto imprimirá el error en los logs de Render ANTES de morir
        print(f"CRITICO: No se encontró la variable {name}")
        raise RuntimeError(f"Falta la variable de entorno {name}")
    return value

def _required_credential(name: str) -> str:
    """Basic auth credentials must be ASCII.

    HTTP Basic sends them base64-encoded and FastAPI decodes them as ASCII,
    so a password with accents would always be rejected with a confusing 401.
    Browsers disagree on how to encode non-ASCII here, so we refuse it at boot
    rather than let it fail silently at login.
    """
    value = _required_env(name)
    if not value.isascii():
        _fatal(
            f"{name} contiene caracteres no ASCII (tildes o ñ), "
            "que HTTP Basic no admite de forma confiable",
            f"cambia {name} en Render > Environment por uno solo con "
            "letras, numeros y guiones",
        )
    return value


SUPABASE_URL = _required_env("SUPABASE_URL")
SUPABASE_KEY = _required_env("SUPABASE_KEY")
APP_USER = _required_credential("APP_USER")
APP_PASSWORD = _required_credential("APP_PASSWORD")

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as exc:
    # Most common cause: a truncated or wrong SUPABASE_KEY. Without this the
    # log shows only "SupabaseException: Invalid API key" with no context.
    _fatal(
        f"no se pudo crear el cliente de Supabase: {exc}",
        "revisa que SUPABASE_URL y SUPABASE_KEY esten completas y "
        "correspondan al mismo proyecto",
    )

app = FastAPI(title="Aparthotel Paros")
basic_auth = HTTPBasic(realm="Aparthotel Paros")


def require_login(credentials: HTTPBasicCredentials = Depends(basic_auth)) -> str:
    """Basic auth on every route that touches hotel data."""
    # Compare as bytes: compare_digest rejects non-ASCII str, and the incoming
    # credentials are attacker-controlled. Constant time, so no length leak.
    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), APP_USER.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), APP_PASSWORD.encode("utf-8")
    )
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": 'Basic realm="Aparthotel Paros"'},
        )
    return credentials.username


class HotelState(BaseModel):
    """Web backup format — camelCase keys, same shape as data.json."""

    # A payload with no apartments would wipe the hotel: reject it outright.
    rooms: list = Field(min_length=1)
    history: list = []
    totalRevenue: float = 0
    operationalTasks: list = []


@app.get("/")
def read_root(_user: str = Depends(require_login)):
    return FileResponse(INDEX_FILE)


@app.get("/health")
def health():
    """Public, data-free endpoint for Render's monitoring."""
    return {"status": "ok"}


# ------------------------------------------------------------------
#  PWA assets
# ------------------------------------------------------------------
# These three routes are public, unlike everything else. They hold no hotel
# data, and requiring auth would break the install: the browser fetches the
# manifest without credentials by default, and a service worker that 401s on
# update silently stops updating. Auth still guards `/` and both /api routes,
# so the app itself remains locked.


@app.get("/manifest.json")
def manifest():
    if not (BASE_DIR / "manifest.json").is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "manifest.json no encontrado")
    return FileResponse(
        BASE_DIR / "manifest.json", media_type="application/manifest+json"
    )


@app.get("/service-worker.js")
def service_worker():
    path = BASE_DIR / "service-worker.js"
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "service-worker.js no encontrado")
    return FileResponse(
        path,
        media_type="application/javascript",
        headers={
            # Without no-cache the browser can keep serving a stale worker for
            # up to 24h, so a deploy would never reach the clients that need it.
            "Cache-Control": "no-cache",
            # Served from the root already, but being explicit documents that
            # the worker is meant to control the whole site.
            "Service-Worker-Allowed": "/",
        },
    )


@app.get("/icons/{name}")
def icon(name: str):
    # Allow-list, not a path join: `name` comes straight from the URL.
    if name not in ALLOWED_ICONS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Icono no encontrado")
    path = ICONS_DIR / name
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Icono no encontrado")
    return FileResponse(path, media_type="image/png")


# RUTA PARA LEER DATOS (cuando el usuario abre la página)
@app.get("/api/state")
def get_state(_user: str = Depends(require_login)):
    try:
        result = supabase.table(TABLE).select("data").eq("id", ROW_ID).execute()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Supabase no responde: {exc}"
        )

    rows = result.data or []
    stored = (rows[0].get("data") or {}) if rows else {}
    # Return the whole state, not just rooms, or the client loses its
    # billing history and revenue on every reload.
    return {
        "rooms": stored.get("rooms", []),
        "history": stored.get("history", []),
        "totalRevenue": stored.get("totalRevenue", 0),
        "operationalTasks": stored.get("operationalTasks", []),
    }


# RUTA PARA GUARDAR DATOS (check-in / check-out desde la web)
@app.post("/api/update")
def update_state(state: HotelState, _user: str = Depends(require_login)):
    try:
        supabase.table(TABLE).upsert(
            {"id": ROW_ID, "data": state.model_dump()}
        ).execute()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"No se pudo guardar: {exc}"
        )
    return {"status": "success"}
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)