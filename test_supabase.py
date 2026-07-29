"""Diagnostico de la conexion a Supabase y del contenido de `hotel_data` id=1.

Responde tres preguntas, en este orden, sin adivinar:

  1. Hay credenciales y se puede crear el cliente?
  2. Existe realmente la fila id=1, y que hay dentro de su columna `data`?
  3. Ese contenido cumple el contrato que espera index.html?

No escribe nada en la base de datos: solo hace SELECT.

Uso:
    # PowerShell, con las mismas credenciales que Render
    $env:SUPABASE_URL="https://xxxx.supabase.co"
    $env:SUPABASE_KEY="eyJ..."
    python test_supabase.py

Tambien lee un archivo .env junto a este script si existe (formato CLAVE=valor).
Las variables de entorno reales tienen prioridad sobre el .env.

Con `-v` anade el traceback completo de cualquier error.
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

# Claves que index.html espera recibir de GET /api/state (ver HotelState en api.py).
EXPECTED_KEYS = ("rooms", "history", "totalRevenue", "operationalTasks")

# La consola de Windows usa cp1252 por defecto y reventaria al imprimir acentos.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


VERBOSE = "-v" in sys.argv or "--traceback" in sys.argv


def dump_traceback() -> None:
    """Traceback completo solo con -v, y a stdout: en stderr se intercala con el
    diagnostico y lo vuelve ilegible."""
    if VERBOSE:
        print()
        traceback.print_exc(file=sys.stdout)
    else:
        print("  (ejecuta con -v para ver el traceback completo)")


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def preview(value, limit: int = 600) -> str:
    """repr() recortado, para ver el dato tal cual sin inundar la consola."""
    text = repr(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [recortado, {len(text)} caracteres en total]"


def load_dotenv() -> None:
    """Parser minimo de .env: no anade dependencias a requirements.txt."""
    if not ENV_FILE.exists():
        return
    print(f"[i] Leyendo {ENV_FILE.name} (las variables de entorno reales tienen prioridad)")
    for raw in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def read_credentials() -> tuple:
    """Devuelve (url, key) o termina explicando exactamente que falta."""
    section("1. CREDENCIALES")
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")

    missing = [n for n, v in (("SUPABASE_URL", url), ("SUPABASE_KEY", key)) if not v]
    if missing:
        print(f"[FALLO] Faltan variables de entorno: {', '.join(missing)}")
        print()
        print("  Esto NO significa que la base de datos este vacia: significa que este")
        print("  script no sabe a que proyecto conectarse. Copialas desde Render >")
        print("  tu servicio > Environment, o desde Supabase > Project Settings > API.")
        print()
        print('  $env:SUPABASE_URL="https://xxxx.supabase.co"')
        print('  $env:SUPABASE_KEY="eyJ..."')
        sys.exit(2)

    # Nunca imprimir la clave completa: puede acabar en un log o en una captura.
    print(f"  SUPABASE_URL : {url}")
    print(f"  SUPABASE_KEY : {key[:8]}...{key[-4:]}  ({len(key)} caracteres)")

    if not url.startswith("https://"):
        print("  [AVISO] La URL no empieza por https:// — suele estar mal copiada.")
    if len(key) < 40:
        print("  [AVISO] La clave parece truncada: las de Supabase son JWT largos.")
    return url, key


def connect(url: str, key: str):
    section("2. CONEXION")
    try:
        from supabase import create_client
    except ImportError:
        print("[FALLO] El paquete `supabase` no esta instalado en este interprete.")
        print(f"  Interprete actual: {sys.executable}")
        print("  Activa el venv del proyecto o instala: pip install -r requirements.txt")
        sys.exit(2)

    try:
        client = create_client(url, key)
    except Exception as exc:
        print(f"[FALLO] create_client() lanzo {type(exc).__name__}: {exc}")
        print()
        print("  Causa habitual: SUPABASE_KEY incompleta, o URL y clave de proyectos")
        print("  distintos. Aqui la conexion falla ANTES de tocar la tabla.")
        sys.exit(1)

    print("  [OK] Cliente creado. Ojo: create_client() no hace ninguna llamada de red,")
    print("       asi que esto todavia no prueba que las credenciales sean validas.")
    return client


def count_rows(client) -> None:
    """Cuenta filas de la tabla. Aqui es donde falla una clave o una RLS mal puesta."""
    section(f"3. LA TABLA `{TABLE}`")
    try:
        result = client.table(TABLE).select("id", count="exact").execute()
    except Exception as exc:
        print(f"[FALLO] La consulta lanzo {type(exc).__name__}: {exc}")
        print()
        print("  Interpretacion segun el mensaje de arriba:")
        print('   - "Invalid API key"         -> SUPABASE_KEY incorrecta o de otro proyecto.')
        print(f'   - "relation ... does not exist" o 42P01 -> la tabla `{TABLE}` no existe.')
        print("   - permission denied / RLS   -> la politica RLS no permite leer con esta clave.")
        print("   - getaddrinfo / timeout     -> SUPABASE_URL erronea o sin red.")
        print()
        dump_traceback()
        sys.exit(1)

    ids = [row.get("id") for row in (result.data or [])]
    total = result.count if result.count is not None else len(ids)
    print(f"  [OK] Consulta aceptada: la conexion y los permisos de lectura funcionan.")
    print(f"  Filas visibles con esta clave: {total}")
    print(f"  IDs presentes: {ids if ids else '(ninguno)'}")

    if total == 0:
        print()
        print(f"  [ATENCION] La tabla `{TABLE}` esta vacia, o la RLS oculta todas sus filas.")
        print("  Una RLS restrictiva devuelve 0 filas sin error, igual que una tabla vacia:")
        print("  para distinguirlo, cuenta las filas en el editor SQL de Supabase.")


def read_row(client):
    """Lee la fila id=1 completa: `select('*')`, no solo `data`.

    api.py pide solo la columna `data`, con lo que no puede distinguir "no hay
    fila" de "la fila existe pero `data` es NULL". Aqui traemos todo para verlo.
    """
    section(f"4. LA FILA id={ROW_ID}, TAL CUAL LLEGA")
    try:
        result = client.table(TABLE).select("*").eq("id", ROW_ID).execute()
    except Exception as exc:
        print(f"[FALLO] La consulta lanzo {type(exc).__name__}: {exc}")
        dump_traceback()
        sys.exit(1)

    rows = result.data
    print(f"  type(result.data) : {type(rows).__name__}")
    print(f"  result.data       : {preview(rows)}")

    if not rows:
        print()
        print(f"  [ATENCION] No existe ninguna fila con id={ROW_ID}.")
        print("  api.py trata este caso como estado vacio y devuelve rooms: [] con 200 OK,")
        print("  sin ningun error. Es exactamente el sintoma de una pagina en blanco.")
        return None

    row = rows[0]
    print(f"  Columnas de la fila: {list(row.keys())}")
    for name, value in row.items():
        if name == "data":
            continue
        print(f"    {name} = {preview(value, 120)}")

    if "data" not in row:
        print()
        print("  [ATENCION] La fila no tiene columna `data`. api.py lee exactamente")
        print("  `select('data')`, asi que sin esa columna nunca vera nada.")
        return None

    data = row["data"]
    print()
    print(f"  type(data) : {type(data).__name__}")
    print(f"  data       : {preview(data, 1500)}")

    if data is None:
        print()
        print("  [ATENCION] La fila existe pero `data` es NULL. api.py lo convierte en {}")
        print("  (`rows[0].get('data') or {}`) y devuelve el estado vacio sin avisar.")
        return None

    # Si la columna es `text` en vez de `json`/`jsonb`, llega como str.
    if isinstance(data, str):
        print()
        print("  [AVISO] `data` llega como texto, no como objeto. La columna probablemente")
        print("  es `text` en lugar de `json`/`jsonb`. api.py llamaria .get() sobre un str")
        print("  y fallaria con AttributeError. Intento interpretarlo como JSON:")
        try:
            data = json.loads(data)
            print(f"    [OK] Es JSON valido -> {type(data).__name__}")
        except json.JSONDecodeError as exc:
            print(f"    [FALLO] No es JSON valido: {exc}")
            return None

    if not isinstance(data, dict):
        print()
        print(f"  [ATENCION] `data` es {type(data).__name__}, y api.py espera un objeto JSON.")
        return None

    return data


def check_contract(data: dict) -> None:
    """Compara lo guardado con lo que index.html espera recibir."""
    section("5. CONTRATO CON EL FRONTEND")
    print(f"  Claves de nivel superior en `data`: {sorted(data.keys())}")
    print()

    for key in EXPECTED_KEYS:
        if key not in data:
            default = "0" if key == "totalRevenue" else "[]"
            print(f"  [FALTA]  {key:16} -> api.py devolvera el valor por defecto ({default})")
            continue
        value = data[key]
        detalle = f"{len(value)} elementos" if isinstance(value, list) else repr(value)
        print(f"  [OK]     {key:16} -> {type(value).__name__}, {detalle}")

    extra = sorted(set(data.keys()) - set(EXPECTED_KEYS))
    if extra:
        print()
        print(f"  [AVISO] Claves que api.py no reenvia al frontend: {extra}")
        print("  Pydantic descarta las claves no declaradas en HotelState al guardar,")
        print("  y get_state() solo devuelve las cuatro esperadas. Si `guestHistory`")
        print("  aparece aqui, viene de un respaldo de data.json (formato distinto).")

    section("6. CONCLUSION")
    rooms = data.get("rooms")
    if not isinstance(rooms, list):
        print(f"  `rooms` es {type(rooms).__name__}, y debe ser una lista.")
        print("  El frontend no puede dibujar nada: pantalla en blanco.")
        return
    if not rooms:
        print("  `rooms` existe pero esta VACIA. La base de datos no tiene apartamentos.")
        print("  La conexion funciona; el problema es que no hay datos que mostrar.")
        print("  Solucion: guarda el estado una vez desde la web (POST /api/update),")
        print("  o inserta la fila a mano en Supabase.")
        return

    print(f"  Hay {len(rooms)} apartamentos guardados. La base de datos NO esta vacia")
    print("  y la lectura funciona, asi que la pantalla en blanco viene de otro sitio:")
    print("  revisa la consola del navegador (F12), el 401 de HTTP Basic, o la forma")
    print("  de cada apartamento. Primer apartamento tal cual esta guardado:")
    print()
    print("  " + json.dumps(rooms[0], ensure_ascii=False, indent=2).replace("\n", "\n  "))

    primero = rooms[0]
    if isinstance(primero, dict):
        # index.html lee camelCase; un respaldo en snake_case se dibuja a medias.
        snake = [k for k in ("checkin_date", "checkout_date") if k in primero]
        if snake:
            print()
            print(f"  [AVISO] Claves en snake_case: {snake}. index.html lee `checkinDate` /")
            print("  `checkoutDate` (camelCase), asi que ignoraria esas fechas.")


def main() -> None:
    print("Diagnostico de Supabase — Aparthotel Paros")
    print(f"Tabla `{TABLE}`, fila id={ROW_ID}")
    load_dotenv()

    url, key = read_credentials()
    client = connect(url, key)
    count_rows(client)
    data = read_row(client)

    if data is None:
        section("6. CONCLUSION")
        print("  No se pudo leer un estado utilizable de la fila id=1 (ver el motivo arriba).")
        print("  La conexion en si funciona: la consulta fue aceptada por Supabase.")
        print("  Por eso el frontend no ve datos y no aparece ningun error.")
        sys.exit(1)

    check_contract(data)


if __name__ == "__main__":
    main()
