"""Prueba de ESCRITURA contra `hotel_data`: reproduce el 502 de POST /api/update.

api.py ya incluye el error de Supabase en el detail del 502 (`f"No se pudo guardar:
{exc}"`, y str() de un APIError trae code, message, hint y details), asi que si
puedes ver el cuerpo de la respuesta 502 no necesitas este script. Sirve cuando solo
tienes el codigo de estado: repite la misma escritura desde tu maquina y traduce el
error a su causa concreta.

Es NO DESTRUCTIVO: escribe en una fila de prueba propia (id=999999 por defecto,
NO la id=1 de tu hotel) y la borra al terminar.

Uso:
    $env:SUPABASE_URL="https://xxxx.supabase.co"
    $env:SUPABASE_KEY="eyJ..."
    python test_write_supabase.py

    python test_write_supabase.py --row-id 1
        Escribe sobre la fila REAL id=1. Solo si quieres reproducir el fallo
        exacto de api.py; pide confirmacion porque puede sobrescribir el hotel.

Las cuatro pruebas, en orden, para aislar donde se rompe:
    1. SELECT  — la lectura funciona? (si esto pasa, la clave y la tabla estan bien)
    2. INSERT  — la RLS permite escribir?
    3. UPSERT  — es lo que hace api.py; falla aparte si `id` no es clave primaria
    4. DELETE  — limpieza
"""
import json
import os
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
TABLE = "hotel_data"
TEST_ROW_ID = 999999  # fila desechable; no es la id=1 del hotel

VERBOSE = "-v" in sys.argv or "--traceback" in sys.argv

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def parse_row_id() -> int:
    if "--row-id" not in sys.argv:
        return TEST_ROW_ID
    try:
        value = int(sys.argv[sys.argv.index("--row-id") + 1])
    except (IndexError, ValueError):
        print("[FALLO] --row-id necesita un numero entero.")
        sys.exit(2)
    return value


ROW_ID = parse_row_id()
IS_REAL_ROW = ROW_ID == 1


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# Codigos SQLSTATE de PostgreSQL y de PostgREST, traducidos a la causa concreta.
ERROR_CODES = {
    "42501": (
        "PERMISOS RLS",
        "La politica de Row Level Security no permite esta escritura con esta clave. "
        "Es la causa mas comun de un 502 en /api/update cuando GET /api/state si "
        "funciona: hay politica de SELECT pero no de INSERT/UPDATE.",
        "En Supabase > Authentication > Policies > hotel_data, anade politicas de "
        "INSERT y UPDATE para el rol que usa tu clave. Alternativa: usar la "
        "service_role key en SUPABASE_KEY (solo en el backend, nunca en el navegador).",
    ),
    "42P01": (
        "LA TABLA NO EXISTE",
        f"No hay ninguna tabla `{TABLE}` en el esquema public.",
        f"Creala en Supabase, o corrige el nombre en TABLE (api.py linea 15). "
        "Cuidado con mayusculas y con haberla creado en otro esquema.",
    ),
    "42P10": (
        "`id` NO ES CLAVE PRIMARIA",
        "El upsert usa ON CONFLICT sobre `id`, y eso exige una restriccion UNIQUE o "
        "PRIMARY KEY en esa columna. Sin ella el SELECT funciona pero el upsert de "
        "api.py falla siempre: encaja con un 502 solo al guardar.",
        f"En Supabase > Table editor > {TABLE}, marca `id` como Primary Key "
        "(o anade una restriccion UNIQUE).",
    ),
    "23505": (
        "CLAVE DUPLICADA",
        "Ya existe una fila con ese id y la operacion era un INSERT puro.",
        "Esperado en la prueba de INSERT si la fila ya existia; api.py usa upsert, "
        "que no deberia dar este error.",
    ),
    "23502": (
        "COLUMNA NOT NULL SIN VALOR",
        "La tabla tiene una columna NOT NULL sin valor por defecto que este envio no "
        "rellena. api.py solo manda `id` y `data`.",
        "Dale un DEFAULT a esa columna o hazla nullable. El nombre aparece en Details.",
    ),
    "42703": (
        "COLUMNA INEXISTENTE",
        "La tabla no tiene alguna de las columnas enviadas (`id` o `data`).",
        f"Comprueba en el Table editor que `{TABLE}` tiene exactamente `id` y `data`. "
        "api.py escribe esos dos nombres literales.",
    ),
    "PGRST204": (
        "COLUMNA AUSENTE EN EL ESQUEMA",
        "PostgREST no encuentra una de las columnas enviadas en su cache de esquema.",
        "Suele ser una columna recien creada: en Supabase, recarga el esquema "
        "(Settings > API > Reload schema cache) y reintenta.",
    ),
    "PGRST301": (
        "CLAVE INVALIDA O EXPIRADA",
        "PostgREST rechaza el JWT de SUPABASE_KEY.",
        "Copia otra vez la clave desde Supabase > Project Settings > API. "
        "Verifica que no este truncada y que sea del mismo proyecto que la URL.",
    ),
}


def explain(exc: Exception) -> None:
    """Imprime el error de Supabase entero y su causa concreta."""
    print(f"  Excepcion Python : {type(exc).__module__}.{type(exc).__name__}")

    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None)
    hint = getattr(exc, "hint", None)
    details = getattr(exc, "details", None)

    if code or message:
        print(f"  Codigo Supabase  : {code}")
        print(f"  Mensaje          : {message}")
        print(f"  Hint             : {hint}")
        print(f"  Details          : {details}")
        raw = getattr(exc, "json", None)
        if callable(raw):
            try:
                print(f"  JSON crudo       : {json.dumps(raw(), ensure_ascii=False)}")
            except Exception:
                pass
    else:
        # No es un APIError: fallo de red, DNS o TLS antes de llegar a PostgREST.
        print(f"  Mensaje          : {exc}")

    print()
    diagnostico = ERROR_CODES.get(str(code)) if code else None
    if diagnostico is None:
        texto = f"{code} {message} {exc}".lower()
        if "invalid api key" in texto or "invalid_api_key" in texto:
            diagnostico = ERROR_CODES["PGRST301"]
        elif "row-level security" in texto or "violates row-level" in texto:
            diagnostico = ERROR_CODES["42501"]
        elif "getaddrinfo" in texto or "connect" in texto or "timeout" in texto:
            diagnostico = (
                "NO SE ALCANZA EL SERVIDOR",
                "La peticion no llego a Supabase: DNS, red o SUPABASE_URL erronea. "
                "El proceso ni siquiera obtuvo un error de base de datos.",
                "Revisa SUPABASE_URL y que el proyecto no este pausado "
                "(los proyectos gratuitos se suspenden por inactividad).",
            )

    if diagnostico:
        titulo, causa, solucion = diagnostico
        print(f"  >>> CAUSA: {titulo}")
        print(f"      {causa}")
        print(f"      Solucion: {solucion}")
    else:
        print("  >>> Codigo no reconocido por este script.")
        print("      Busca el codigo de arriba en la documentacion de PostgREST/Postgres.")

    if VERBOSE:
        print()
        traceback.print_exc(file=sys.stdout)


def load_dotenv() -> None:
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
    section("0. CREDENCIALES Y CLIENTE")
    load_dotenv()
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    missing = [n for n, v in (("SUPABASE_URL", url), ("SUPABASE_KEY", key)) if not v]
    if missing:
        print(f"[FALLO] Faltan variables de entorno: {', '.join(missing)}")
        print("  Deben ser las MISMAS que tienes en Render > Environment.")
        print('  $env:SUPABASE_URL="https://xxxx.supabase.co"')
        print('  $env:SUPABASE_KEY="eyJ..."')
        sys.exit(2)

    print(f"  SUPABASE_URL : {url}")
    print(f"  SUPABASE_KEY : {key[:8]}...{key[-4:]}  ({len(key)} caracteres)")
    # El tipo de clave decide si la RLS aplica: service_role la salta por completo.
    tipo = "desconocido"
    if "service_role" in key:
        tipo = "service_role (salta la RLS)"
    elif "anon" in key:
        tipo = "anon (la RLS SI aplica)"
    print(f"  Tipo de clave: {tipo}")

    try:
        from supabase import create_client
    except ImportError:
        print(f"[FALLO] `supabase` no esta instalado en {sys.executable}")
        sys.exit(2)

    try:
        return create_client(url, key)
    except Exception as exc:
        print()
        print("[FALLO] create_client() no pudo crear el cliente:")
        explain(exc)
        sys.exit(1)


def try_select(client) -> bool:
    section("1. SELECT — funciona la lectura?")
    try:
        result = client.table(TABLE).select("id").execute()
    except Exception as exc:
        print("[FALLO] La lectura tambien falla:")
        explain(exc)
        print()
        print("  El problema no es exclusivo de la escritura. Arregla esto primero.")
        return False
    ids = [r.get("id") for r in (result.data or [])]
    print(f"  [OK] Lectura correcta. Filas visibles: {len(ids)} — ids: {ids}")
    print("  La clave es valida, la tabla existe y hay permiso de SELECT.")
    return True


def try_insert(client, payload: dict) -> bool:
    section(f"2. INSERT — permite la RLS escribir? (fila id={ROW_ID})")
    try:
        client.table(TABLE).insert(payload).execute()
    except Exception as exc:
        code = str(getattr(exc, "code", ""))
        if code == "23505":
            print(f"  [i] Ya existia una fila id={ROW_ID}: el INSERT no aplica.")
            print("      Lo que importa es el UPSERT de abajo, que es lo que hace api.py.")
            return True
        print("[FALLO] El INSERT ha sido rechazado:")
        explain(exc)
        return False
    print("  [OK] INSERT aceptado: hay permiso de escritura.")
    return True


def try_upsert(client, payload: dict) -> bool:
    section(f"3. UPSERT — la operacion exacta de api.py (fila id={ROW_ID})")
    print("  Equivale a: supabase.table('hotel_data').upsert({'id': ..., 'data': ...})")
    try:
        client.table(TABLE).upsert(payload).execute()
    except Exception as exc:
        print()
        print("[FALLO] Aqui esta el 502. Este es el error que api.py se traga:")
        explain(exc)
        return False
    print("  [OK] UPSERT aceptado.")
    return True


def cleanup(client) -> None:
    section("4. LIMPIEZA")
    if IS_REAL_ROW:
        print(f"  Fila id={ROW_ID} conservada: es la fila real del hotel, no se borra.")
        return
    try:
        client.table(TABLE).delete().eq("id", ROW_ID).execute()
    except Exception as exc:
        print(f"  [AVISO] No se pudo borrar la fila de prueba id={ROW_ID}:")
        explain(exc)
        print()
        print(f"  Borrala a mano: delete from {TABLE} where id = {ROW_ID};")
        return
    print(f"  [OK] Fila de prueba id={ROW_ID} eliminada. La base queda como estaba.")


def main() -> None:
    print("Prueba de escritura en Supabase — Aparthotel Paros")
    print(f"Tabla `{TABLE}`, fila de prueba id={ROW_ID}")

    if IS_REAL_ROW:
        print()
        print("  [ATENCION] --row-id 1 escribe sobre la fila REAL del hotel y")
        print("  sobrescribiria los datos que tenga. Solo para reproducir el fallo exacto.")
        respuesta = input("  Escribe 'si' para continuar: ").strip().lower()
        if respuesta != "si":
            print("  Cancelado. Sin --row-id usa la fila de prueba id=999999.")
            sys.exit(0)

    client = connect()
    if not try_select(client):
        sys.exit(1)

    # Payload con la misma forma que envia api.py: un unico blob JSON en `data`.
    payload = {
        "id": ROW_ID,
        "data": {"rooms": [], "history": [], "totalRevenue": 0, "operationalTasks": []},
    }

    inserted = try_insert(client, payload)
    upserted = try_upsert(client, payload)
    cleanup(client)

    section("RESUMEN")
    print(f"  SELECT : OK")
    print(f"  INSERT : {'OK' if inserted else 'FALLO'}")
    print(f"  UPSERT : {'OK' if upserted else 'FALLO'}   <- lo que usa POST /api/update")
    print()
    if upserted:
        print("  La escritura funciona desde aqui. Si Render sigue dando 502, entonces")
        print("  las variables de entorno de Render NO son las que acabas de usar:")
        print("  comparalas en Render > Environment (una clave truncada al copiarla")
        print("  es el caso tipico).")
    else:
        print("  Reproducido el fallo: la causa esta en el bloque CAUSA de arriba.")
    sys.exit(0 if upserted else 1)


if __name__ == "__main__":
    main()
