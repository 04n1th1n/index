"""Crea la fila id=1 de `hotel_data` con un estado inicial vacio.

Complemento de test_supabase.py: ese diagnostica, este escribe. Usa las mismas
credenciales (SUPABASE_URL / SUPABASE_KEY) y el mismo cliente que api.py.

Por defecto inserta el estado vacio que espera el frontend:

    {"rooms": [], "history": [], "totalRevenue": 0, "operationalTasks": []}

Uso:
    $env:SUPABASE_URL="https://xxxx.supabase.co"
    $env:SUPABASE_KEY="eyJ..."

    python seed_supabase.py              # muestra que haria, sin escribir
    python seed_supabase.py --write      # inserta la fila
    python seed_supabase.py --write --generate
                                         # inserta los 100 apartamentos ya generados
    python seed_supabase.py --write --force
                                         # sobrescribe una fila id=1 que ya exista

Sin --write no toca la base de datos: es un ensayo. Si la fila id=1 ya existe con
apartamentos dentro, el script se niega a escribir salvo que pases --force,
porque un estado vacio borraria el hotel.
"""
import json
import os
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
TABLE = "hotel_data"
ROW_ID = 1

WRITE = "--write" in sys.argv
FORCE = "--force" in sys.argv
GENERATE = "--generate" in sys.argv
VERBOSE = "-v" in sys.argv or "--traceback" in sys.argv

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def fail(message: str, hint: str = "") -> None:
    print(f"[FALLO] {message}")
    if hint:
        print(f"  {hint}")
    if VERBOSE and sys.exc_info()[0] is not None:
        print()
        traceback.print_exc(file=sys.stdout)
    sys.exit(1)


def load_dotenv() -> None:
    """Parser minimo de .env, igual que en test_supabase.py."""
    if not ENV_FILE.exists():
        return
    for raw in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def connect():
    """Mismo par de variables y mismo create_client que api.py."""
    section("1. CONEXION")
    load_dotenv()
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    missing = [n for n, v in (("SUPABASE_URL", url), ("SUPABASE_KEY", key)) if not v]
    if missing:
        fail(
            f"faltan variables de entorno: {', '.join(missing)}",
            "copialas de Render > Environment antes de ejecutar.",
        )

    try:
        from supabase import create_client
    except ImportError:
        fail(
            "el paquete `supabase` no esta instalado en este interprete",
            f"interprete: {sys.executable} — activa el venv del proyecto.",
        )

    print(f"  SUPABASE_URL : {url}")
    print(f"  SUPABASE_KEY : {key[:8]}...{key[-4:]}  ({len(key)} caracteres)")
    try:
        client = create_client(url, key)
    except Exception as exc:
        fail(f"create_client() lanzo {type(exc).__name__}: {exc}")
    print("  [OK] Cliente creado.")
    return client


def build_state() -> dict:
    """El estado a insertar: vacio por defecto, o los 100 apartamentos con --generate."""
    state = {"rooms": [], "history": [], "totalRevenue": 0, "operationalTasks": []}
    if not GENERATE:
        return state

    # Reutiliza la generacion de main.py en vez de duplicarla, para que no se
    # desincronice. __new__ sin __init__ a proposito: el constructor llama a
    # _save() y reescribiria data.json, que aqui no queremos tocar.
    try:
        from main import HotelManager
    except ImportError as exc:
        fail(f"no se pudo importar HotelManager desde main.py: {exc}")

    manager = object.__new__(HotelManager)
    state["rooms"] = [room.to_dict() for room in manager._generate_departments()]
    # `operationalTasks` se queda vacio: las tareas de ejemplo solo existen en el
    # JS de index.html (generarTareasEjemplo), no en main.py.
    return state


def inspect_existing(client) -> tuple:
    """Mira la fila id=1 antes de escribir. Devuelve (existe, apartamentos)."""
    section(f"2. ESTADO ACTUAL DE LA FILA id={ROW_ID}")
    try:
        result = client.table(TABLE).select("*").eq("id", ROW_ID).execute()
    except Exception as exc:
        fail(
            f"la consulta lanzo {type(exc).__name__}: {exc}",
            "ejecuta test_supabase.py para el diagnostico detallado.",
        )

    rows = result.data or []
    if not rows:
        print(f"  No existe la fila id={ROW_ID}. Se puede insertar sin riesgo.")
        return False, 0

    data = rows[0].get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = None
    rooms = data.get("rooms") if isinstance(data, dict) else None
    count = len(rooms) if isinstance(rooms, list) else 0

    print(f"  La fila id={ROW_ID} YA EXISTE.")
    print(f"  Claves en `data`: {sorted(data.keys()) if isinstance(data, dict) else '(ninguna)'}")
    print(f"  Apartamentos guardados: {count}")
    return True, count


def write_row(client, state: dict, exists: bool) -> None:
    section("3. ESCRITURA")
    payload = {"id": ROW_ID, "data": state}
    resumen = ", ".join(
        f"{k}: {len(v) if isinstance(v, list) else v}" for k, v in state.items()
    )
    print(f"  Fila a escribir -> id={ROW_ID}, data = {{{resumen}}}")

    if not WRITE:
        print()
        print("  [ENSAYO] No se ha escrito nada. Repite con --write para insertarla.")
        return

    try:
        if exists:
            # upsert: la fila ya existe, un insert chocaria con la clave primaria.
            client.table(TABLE).upsert(payload).execute()
            print("  [OK] Fila sobrescrita (upsert).")
        else:
            client.table(TABLE).insert(payload).execute()
            print("  [OK] Fila insertada.")
    except Exception as exc:
        message = str(exc)
        hint = "ejecuta test_supabase.py para el diagnostico completo."
        if "duplicate key" in message or "23505" in message:
            hint = "la fila ya existia; vuelve a ejecutar y usara upsert."
        elif "permission" in message.lower() or "row-level security" in message.lower():
            hint = (
                "la RLS permite leer pero no escribir con esta clave. Anade una "
                "politica de INSERT/UPDATE en `hotel_data`, o usa la service_role key."
            )
        fail(f"la escritura lanzo {type(exc).__name__}: {exc}", hint)

    verify(client)


def verify(client) -> None:
    """Lee de vuelta: confirmar que lo escrito esta ahi de verdad."""
    section("4. VERIFICACION (releyendo de la base de datos)")
    try:
        result = client.table(TABLE).select("data").eq("id", ROW_ID).execute()
    except Exception as exc:
        fail(f"no se pudo releer la fila: {type(exc).__name__}: {exc}")

    rows = result.data or []
    if not rows:
        fail(
            f"tras escribir, la fila id={ROW_ID} sigue sin aparecer",
            "sintoma clasico de una RLS que permite escribir pero no leer.",
        )

    stored = rows[0].get("data")
    if isinstance(stored, str):
        stored = json.loads(stored)

    rooms = stored.get("rooms", []) if isinstance(stored, dict) else []
    print(f"  Claves recuperadas : {sorted(stored.keys()) if isinstance(stored, dict) else stored}")
    print(f"  rooms              : {len(rooms)} apartamentos")
    print(f"  history            : {len(stored.get('history', []))} entradas")
    print(f"  totalRevenue       : {stored.get('totalRevenue')}")
    print(f"  operationalTasks   : {len(stored.get('operationalTasks', []))} tareas")

    section("LISTO")
    print(f"  La fila id={ROW_ID} existe y GET /api/state ya la lee.")
    if not rooms:
        print()
        print("  Aviso: `rooms` esta vacia, que es lo que api.py ya devolvia cuando la")
        print("  fila no existia. El frontend recibe exactamente la misma respuesta que")
        print("  antes, asi que esto por si solo no cambia lo que se ve en pantalla.")
        print("  Para dejar los 100 apartamentos ya cargados: --write --generate")


def main() -> None:
    print("Seed de Supabase — Aparthotel Paros")
    print(f"Tabla `{TABLE}`, fila id={ROW_ID}")
    print(f"Modo: {'ESCRITURA' if WRITE else 'ENSAYO (sin --write no se escribe nada)'}"
          f"{' + GENERATE' if GENERATE else ''}{' + FORCE' if FORCE else ''}")

    client = connect()
    state = build_state()
    exists, existing_rooms = inspect_existing(client)

    # No sobrescribir un hotel con datos por accidente: seria irreversible.
    if exists and existing_rooms > 0 and not FORCE:
        section("ABORTADO")
        print(f"  La fila id={ROW_ID} ya contiene {existing_rooms} apartamentos.")
        nuevos = len(state["rooms"])
        print(f"  Escribir encima los dejaria en {nuevos}: se perderian los datos actuales.")
        print()
        print("  Si de verdad quieres reemplazarlos, repite con --force.")
        print("  Antes conviene guardar una copia: la sobrescritura no se puede deshacer.")
        sys.exit(1)

    write_row(client, state, exists)


if __name__ == "__main__":
    main()
