"""Aparthotel Paros · Sistema de Gestión (consola).

Replica la funcionalidad del panel web index.html en una interfaz de menús de
texto. La persistencia usa data.json con el mismo formato que el respaldo del
panel web, por lo que los archivos son intercambiables entre ambas apps.
"""
import json
import os
from datetime import date, datetime, timedelta

from models import (
    Room, TYPES, TYPE_SHORT, TYPE_LABEL, PRICE_BY_TYPE,
    MONTHS_FULL, area_of, currency, format_date, normalize_text,
)

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


# ============================================================
#  HELPERS DE FECHA
# ============================================================
def today() -> date:
    return date.today()


def iso(d: date) -> str:
    return d.isoformat()


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def nights_between(checkin: str, checkout: str) -> int:
    d1, d2 = parse_iso(checkin), parse_iso(checkout)
    if not d1 or not d2:
        return 0
    return (d2 - d1).days


# ============================================================
#  GESTOR
# ============================================================
class HotelManager:
    def __init__(self):
        self.rooms = []
        self.history = []
        self.total_revenue = 0
        self.guest_history = {}
        if not self._load():
            self.rooms = self._generate_departments()
            self._save()

    # ---------- generación ----------
    def _generate_departments(self):
        """100 departamentos: 10 pisos x 10 unidades. Mismo patrón que el panel web."""
        rooms = []
        rid = 1
        for piso in range(1, 11):
            base = piso * 100
            for i in range(1, 11):
                numero = base + i
                tipo = TYPES[(i - 1) % 3]
                precio = PRICE_BY_TYPE[tipo]
                room = Room(id=rid, number=str(numero), type=tipo, price=precio)
                if i in (3, 7):
                    nights = (i % 3) + 1
                    dias_atras = nights + (i % 2)
                    checkin = today() - timedelta(days=dias_atras)
                    checkout = checkin + timedelta(days=nights)
                    room.status = "occupied"
                    room.guest = f"Huésped {numero}"
                    room.nights = nights
                    room.checkin_date = iso(checkin)
                    room.checkout_date = iso(checkout)
                    if i == 3:
                        room.notes = "🎂 Cliente frecuente, prefiere piso alto."
                    if i == 7:
                        room.notes = "🔧 Mantenimiento de aire acondicionado pendiente."
                rooms.append(room)
                rid += 1
        return rooms

    # ---------- persistencia ----------
    def _save(self):
        data = {
            "rooms": [r.to_dict() for r in self.rooms],
            "history": self.history,
            "totalRevenue": self.total_revenue,
            "guestHistory": self.guest_history,
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self, path=DATA_FILE):
        if not os.path.exists(path):
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            print("Aviso: no se pudieron leer los datos guardados; se empieza de cero.")
            return False
        rooms = data.get("rooms") or []
        if not rooms:
            return False
        self.rooms = [Room.from_dict(r) for r in rooms]
        self.history = data.get("history", [])
        self.total_revenue = data.get("totalRevenue", 0)
        self.guest_history = data.get("guestHistory") or {}
        return True

    # ---------- búsqueda de deptos ----------
    def find_by_number(self, number):
        number = str(number).strip()
        for r in self.rooms:
            if r.number == number:
                return r
        return None

    # ---------- historial por huésped ----------
    def _update_guest_history(self, guest, number, nights, total, checkin, checkout):
        if not guest:
            return
        key = guest.lower().strip()
        self.guest_history.setdefault(key, [])
        self.guest_history[key].append({
            "room": number, "nights": nights, "total": total,
            "checkin": checkin or iso(today()), "checkout": checkout or iso(today()),
        })
        if len(self.guest_history[key]) > 20:
            self.guest_history[key] = self.guest_history[key][-20:]

    def get_guest_history(self, guest):
        if not guest:
            return []
        return self.guest_history.get(guest.lower().strip(), [])

    # ---------- operaciones ----------
    def check_in(self, room, guest, checkin, checkout):
        nights = nights_between(checkin, checkout)
        room.status = "occupied"
        room.guest = guest
        room.nights = nights
        room.checkin_date = checkin
        room.checkout_date = checkout
        self._update_guest_history(guest, room.number, nights, nights * room.price, checkin, checkout)
        self._save()
        return nights

    def check_out(self, room, nights, total):
        self.history.append({
            "room": room.number, "guest": room.guest, "nights": nights, "total": total,
            "timestamp": datetime.now().isoformat(),
            "checkin": room.checkin_date, "checkout": room.checkout_date,
        })
        self.total_revenue += total
        # cerrar la última estancia del huésped en su historial
        key = (room.guest or "").lower().strip()
        if key and self.guest_history.get(key):
            last = self.guest_history[key][-1]
            if last.get("room") == room.number:
                last["checkout"] = room.checkout_date or iso(today())
                last["nights"] = nights
                last["total"] = total
        room.status = "available"
        room.guest = None
        room.nights = 1
        room.checkin_date = None
        room.checkout_date = None
        self._save()

    def reset(self):
        self.rooms = self._generate_departments()
        self.history = []
        self.total_revenue = 0
        self.guest_history = {}
        self._save()

    def export_backup(self, path):
        data = {
            "rooms": [r.to_dict() for r in self.rooms],
            "history": self.history,
            "totalRevenue": self.total_revenue,
            "guestHistory": self.guest_history,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def import_backup(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("rooms"):
            raise ValueError("Archivo inválido o sin datos")
        self.rooms = [Room.from_dict(r) for r in data["rooms"]]
        self.history = data.get("history", [])
        self.total_revenue = data.get("totalRevenue", 0)
        self.guest_history = data.get("guestHistory") or {}
        self._save()

    # ---------- estadísticas ----------
    def stats(self):
        total = len(self.rooms)
        occupied = sum(1 for r in self.rooms if r.is_occupied)
        available = total - occupied
        rate = round(occupied / total * 100) if total else 0
        return total, available, occupied, rate


# ============================================================
#  ENTRADA DE USUARIO
# ============================================================
def ask(prompt, default=None):
    val = input(prompt).strip()
    return val if val else (default if default is not None else "")


def ask_date(prompt, default_date):
    """Pide una fecha ISO; Enter usa el valor por defecto. Reintenta si es inválida."""
    while True:
        raw = input(f"{prompt} [{iso(default_date)}]: ").strip()
        if not raw:
            return iso(default_date)
        if parse_iso(raw):
            return raw
        print("  Fecha inválida. Usa el formato AAAA-MM-DD.")


def pause():
    input("\n(Enter para continuar) ")


# ============================================================
#  VISTAS
# ============================================================
def matches(room, status_f, type_f, area_f, term):
    if status_f != "all" and room.status != status_f:
        return False
    if type_f != "all" and room.type != type_f:
        return False
    a = area_of(room.type)
    if area_f == "small" and not (a < 80):
        return False
    if area_f == "medium" and not (80 <= a <= 105):
        return False
    if area_f == "large" and not (a > 105):
        return False
    if term:
        if term not in normalize_text(room.number) and term not in normalize_text(room.guest or ""):
            return False
    return True


SORTS = {
    "1": ("Número ↑", lambda r: int(r.number)),
    "2": ("Número ↓", lambda r: -int(r.number)),
    "3": ("Precio ↑", lambda r: r.price),
    "4": ("Precio ↓", lambda r: -r.price),
    "5": ("Superficie ↑", lambda r: area_of(r.type)),
    "6": ("Superficie ↓", lambda r: -area_of(r.type)),
}


def show_dashboard(mgr):
    total, available, occupied, rate = mgr.stats()
    bar_len = 30
    filled = round(rate / 100 * bar_len)
    print("\n" + "=" * 56)
    print("  APARTHOTEL PAROS · Panel general")
    print("=" * 56)
    print(f"  Total departamentos : {total}")
    print(f"  Disponibles         : {available}")
    print(f"  Ocupados            : {occupied}")
    print(f"  Ocupación           : {rate}%  [{'█' * filled}{'░' * (bar_len - filled)}]")
    print(f"  Ingresos totales    : {currency(mgr.total_revenue)}")
    print("-" * 56)
    print("  Resumen por tipo:")
    for t in TYPES:
        grp = [r for r in mgr.rooms if r.type == t]
        disp = sum(1 for r in grp if not r.is_occupied)
        ocup = sum(1 for r in grp if r.is_occupied)
        print(f"    {TYPE_LABEL[t]:<16} total {len(grp):>3}  ·  {disp} disp · {ocup} ocup")
    print("=" * 56)


def show_map(mgr):
    status_f, type_f, area_f, term = "all", "all", "all", ""
    sort_key, sort_label = SORTS["1"][1], SORTS["1"][0]
    status_names = {"all": "Todos", "available": "Disponibles", "occupied": "Ocupados"}
    type_names = {"all": "Todo tipo", "standard": "2 dorm", "suite": "3 dorm", "vip": "4 dorm"}
    area_names = {"all": "Todas", "small": "-80 m²", "medium": "80–105 m²", "large": "+105 m²"}

    while True:
        rooms = [r for r in mgr.rooms if matches(r, status_f, type_f, area_f, term)]
        rooms.sort(key=sort_key)
        print("\n" + "=" * 64)
        print(f"  MAPA · estado:{status_names[status_f]} tipo:{type_names[type_f]} "
              f"área:{area_names[area_f]} orden:{sort_label}" + (f" buscar:'{term}'" if term else ""))
        print("=" * 64)
        if not rooms:
            print("  Sin resultados con los filtros actuales.")
        else:
            floors = {}
            for r in rooms:
                floors.setdefault(r.floor, []).append(r)
            for floor in sorted(floors):
                grp = floors[floor]
                ocup = sum(1 for r in grp if r.is_occupied)
                frate = round(ocup / len(grp) * 100) if grp else 0
                alert = "  ¡ATENCIÓN: piso lleno!" if frate == 100 else ""
                print(f"\n  ── Piso {floor} · {frate}% ({ocup}/{len(grp)} ocupados){alert}")
                for r in grp:
                    mark = "●" if r.is_occupied else "○"
                    line = f"    {mark} {r.number}  {TYPE_SHORT[r.type]:<8} {currency(r.price):>9}/noche"
                    if r.is_occupied:
                        line += f"  · {r.guest}"
                        if r.checkout_date:
                            rem = (parse_iso(r.checkout_date) - today()).days
                            if rem <= 0:
                                line += "  [CHECK-OUT HOY]"
                            elif rem <= 2:
                                line += f"  [{rem} día(s) rest.]"
                    if r.notes:
                        line += "  📝"
                    print(line)
        print("\n  [e]stado  [t]ipo  [a]rea  [o]rden  [b]uscar  [l]impiar  [q]volver")
        op = input("  > ").strip().lower()
        if op == "q":
            return
        elif op == "e":
            status_f = cycle(["all", "available", "occupied"], status_f)
        elif op == "t":
            type_f = cycle(["all"] + TYPES, type_f)
        elif op == "a":
            area_f = cycle(["all", "small", "medium", "large"], area_f)
        elif op == "o":
            print("  " + "  ".join(f"{k}={v[0]}" for k, v in SORTS.items()))
            sel = input("  Orden #: ").strip()
            if sel in SORTS:
                sort_label, sort_key = SORTS[sel][0], SORTS[sel][1]
        elif op == "b":
            term = normalize_text(input("  Buscar (huésped o número): "))
        elif op == "l":
            status_f, type_f, area_f, term = "all", "all", "all", ""


def cycle(options, current):
    """Devuelve el siguiente valor de la lista (rotando)."""
    i = options.index(current) if current in options else -1
    return options[(i + 1) % len(options)]


def do_check_in(mgr):
    num = ask("\nNúmero de departamento para check-in: ")
    room = mgr.find_by_number(num)
    if not room:
        print("No existe ese departamento."); return
    if room.is_occupied:
        print("El departamento ya está ocupado."); return
    guest = ask("Nombre del huésped: ")
    if not guest:
        print("El nombre es obligatorio."); return
    hist = mgr.get_guest_history(guest)
    if hist:
        print(f"  📋 Historial de {guest} ({len(hist)} estancia(s) previa(s)):")
        for it in hist[-5:][::-1]:
            print(f"     Dpto. {it['room']} · {format_date(it.get('checkin'))} → "
                  f"{format_date(it.get('checkout'))} · {it['nights']} noche(s)")
    checkin = ask_date("Fecha de ingreso", today())
    default_out = parse_iso(checkin) + timedelta(days=1)
    while True:
        checkout = ask_date("Fecha de egreso", default_out)
        if nights_between(checkin, checkout) >= 1:
            break
        print("  El egreso debe ser posterior al ingreso.")
    nights = nights_between(checkin, checkout)
    print(f"  → {nights} noche(s) · Total: {currency(nights * room.price)}")
    if ask("Confirmar check-in (s/n): ").lower().startswith("s"):
        mgr.check_in(room, guest, checkin, checkout)
        print(f"✓ Check-in exitoso · Dpto. {room.number} — {guest} ({nights} noches)")
    else:
        print("Cancelado.")


def do_check_out(mgr):
    num = ask("\nNúmero de departamento para check-out: ")
    room = mgr.find_by_number(num)
    if not room:
        print("No existe ese departamento."); return
    if not room.is_occupied:
        print("El departamento no está ocupado."); return
    nights = room.nights or 1
    print(f"  Huésped: {room.guest}")
    print(f"  Ingreso: {format_date(room.checkin_date)} · Egreso: {format_date(room.checkout_date)}")
    print(f"  Precio/noche: {currency(room.price)}")
    raw = ask(f"  Noches a facturar [{nights}]: ", str(nights))
    try:
        nights = max(1, int(raw))
    except ValueError:
        pass
    total = nights * room.price
    print(f"  TOTAL A PAGAR: {currency(total)}")
    if ask("Confirmar check-out (s/n): ").lower().startswith("s"):
        mgr.check_out(room, nights, total)
        print(f"✓ Check-out completado · Dpto. {room.number} — Total: {currency(total)}")
    else:
        print("Cancelado.")


def do_edit(mgr):
    num = ask("\nNúmero de departamento a editar: ")
    room = mgr.find_by_number(num)
    if not room:
        print("No existe ese departamento."); return
    if not room.is_occupied:
        print("Solo se pueden editar departamentos ocupados."); return
    guest = ask(f"Nombre del huésped [{room.guest}]: ", room.guest)
    checkin = ask_date("Ingreso", parse_iso(room.checkin_date) or today())
    default_out = parse_iso(room.checkout_date) or (parse_iso(checkin) + timedelta(days=1))
    checkout = ask_date("Egreso", default_out)
    if nights_between(checkin, checkout) < 1:
        print("El egreso debe ser posterior al ingreso. Cambios descartados."); return
    notes = ask(f"Notas internas [{room.notes}]: ", room.notes)
    room.guest = guest
    room.checkin_date = checkin
    room.checkout_date = checkout
    room.nights = nights_between(checkin, checkout)
    room.notes = notes
    mgr._save()
    print("✓ Datos actualizados correctamente.")


def show_occupied(mgr):
    occ = [r for r in mgr.rooms if r.is_occupied]
    print(f"\n=== OCUPADOS ACTUALES ({len(occ)}) ===")
    if not occ:
        print("  No hay departamentos ocupados."); return
    for r in sorted(occ, key=lambda x: int(x.number)):
        badge = ""
        if r.checkout_date:
            rem = (parse_iso(r.checkout_date) - today()).days
            if rem == 0:
                badge = " [CHECK-OUT HOY]"
            elif rem == 1:
                badge = " [CHECK-OUT MAÑANA]"
        print(f"  #{r.number} {TYPE_SHORT[r.type]:<8} {r.guest:<22} "
              f"{format_date(r.checkin_date)} → {format_date(r.checkout_date)} "
              f"· {r.nights}n{badge}")


def show_history(mgr):
    print(f"\n=== HISTORIAL DE FACTURACIÓN · {currency(mgr.total_revenue)} ===")
    if not mgr.history:
        print("  Aún no hay movimientos."); return
    for it in reversed(mgr.history):
        ts = it.get("timestamp", "")[:16].replace("T", " ")
        rng = ""
        if it.get("checkin") and it.get("checkout"):
            rng = f" ({format_date(it['checkin'])} → {format_date(it['checkout'])})"
        print(f"  {ts}  Dpto. {it['room']} · {it['guest']} · {it['nights']}n{rng}"
              f"  →  {currency(it['total'])}")


def show_calendar(mgr):
    cur = today().replace(day=1)
    while True:
        year, month = cur.year, cur.month
        days_in_month = (cur.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        n_days = days_in_month.day
        occ_rooms = [r for r in mgr.rooms if r.is_occupied and r.checkin_date and r.checkout_date]

        occ_days = free_days = arr_days = dep_days = 0
        rows = []
        for d in range(1, n_days + 1):
            day = date(year, month, d)
            arrivals = [r for r in occ_rooms if parse_iso(r.checkin_date) == day]
            departures = [r for r in occ_rooms if parse_iso(r.checkout_date) == day]
            stays = [r for r in occ_rooms
                     if parse_iso(r.checkin_date) <= day < parse_iso(r.checkout_date)]
            if stays:
                occ_days += 1
            else:
                free_days += 1
            if arrivals:
                arr_days += 1
            if departures:
                dep_days += 1
            if stays or arrivals or departures:
                marks = ("▼" if arrivals else " ") + ("▲" if departures else " ")
                rows.append((d, len(stays), marks, day == today()))

        print("\n" + "=" * 56)
        print(f"  CALENDARIO · {MONTHS_FULL[month - 1].capitalize()} {year}")
        print("=" * 56)
        print(f"  Días con ocupación: {occ_days}  ·  libres: {free_days}  ·  "
              f"🛬 llegadas: {arr_days}  ·  🛫 salidas: {dep_days}")
        print("  (▼ llegada  ▲ salida  * hoy)")
        if rows:
            for d, n, marks, is_today in rows:
                print(f"    {'*' if is_today else ' '}{d:>2}  {marks}  ocupados: {n}")
        else:
            print("  Sin actividad este mes.")

        # Timeline (primeros 8)
        if occ_rooms:
            print("\n  Timeline de ocupación:")
            for r in occ_rooms[:8]:
                print(f"    #{r.number} {(r.guest or ''):<20} "
                      f"{format_date(r.checkin_date)} → {format_date(r.checkout_date)}")
            if len(occ_rooms) > 8:
                print(f"    + {len(occ_rooms) - 8} más")

        print("\n  [a]nterior  [s]iguiente  [d]etalle de un día  [q]volver")
        op = input("  > ").strip().lower()
        if op == "q":
            return
        elif op == "a":
            cur = (cur - timedelta(days=1)).replace(day=1)
        elif op == "s":
            cur = (days_in_month + timedelta(days=1))
        elif op == "d":
            show_day_detail(mgr, year, month)


def show_day_detail(mgr, year, month):
    raw = input(f"  Día (1-31) de {MONTHS_FULL[month - 1]}: ").strip()
    try:
        day = date(year, month, int(raw))
    except (ValueError, TypeError):
        print("  Día inválido."); return
    occ_rooms = [r for r in mgr.rooms if r.is_occupied and r.checkin_date and r.checkout_date]
    arrivals = [r for r in occ_rooms if parse_iso(r.checkin_date) == day]
    departures = [r for r in occ_rooms if parse_iso(r.checkout_date) == day]
    stays = [r for r in occ_rooms
             if parse_iso(r.checkin_date) < day < parse_iso(r.checkout_date)]
    print(f"\n  {format_date(iso(day))}:")
    if not (arrivals or departures or stays):
        print("    Sin ocupaciones."); return
    for label, grp in (("📥 Llegadas", arrivals), ("📤 Salidas", departures), ("🏠 Estancias", stays)):
        if grp:
            print(f"    {label}:")
            for r in grp:
                print(f"      #{r.number} · {r.guest}")


def do_export(mgr):
    default = os.path.join(os.path.dirname(__file__),
                           f"backup-aparthotel-{iso(today())}.json")
    path = ask(f"Ruta de exportación [{default}]: ", default)
    try:
        mgr.export_backup(path)
        print(f"✓ Respaldo exportado en: {path}")
    except OSError as e:
        print(f"Error al exportar: {e}")


def do_import(mgr):
    path = ask("Ruta del archivo JSON a importar: ")
    if not path or not os.path.exists(path):
        print("No se encontró el archivo."); return
    try:
        mgr.import_backup(path)
        print("✓ Datos importados correctamente.")
    except (json.JSONDecodeError, ValueError, OSError) as e:
        print(f"Error al importar: {e}")


def do_reset(mgr):
    print("\n⚠️  Se perderán TODOS los datos actuales. Esta acción no se puede deshacer.")
    if ask("Escribe 'REINICIAR' para confirmar: ") == "REINICIAR":
        mgr.reset()
        print("✓ Sistema reiniciado correctamente.")
    else:
        print("Cancelado.")


# ============================================================
#  BÚSQUEDA RÁPIDA
# ============================================================
def do_search(mgr):
    term = normalize_text(input("\nBuscar (huésped o número): "))
    if not term:
        return
    found = [r for r in mgr.rooms
             if term in normalize_text(r.number) or term in normalize_text(r.guest or "")]
    if not found:
        print("  Sin resultados."); return
    print(f"  {len(found)} resultado(s):")
    for r in sorted(found, key=lambda x: int(x.number)):
        estado = "ocupado" if r.is_occupied else "disponible"
        extra = f" · {r.guest}" if r.is_occupied else ""
        print(f"    #{r.number} {TYPE_SHORT[r.type]:<8} [{estado}]{extra}")


# ============================================================
#  MENÚ PRINCIPAL
# ============================================================
MENU = """
--- APARTHOTEL PAROS · SISTEMA DE GESTIÓN ---
1. Panel general (estadísticas)
2. Mapa de departamentos (filtros/orden/búsqueda)
3. Check-in (registrar huésped)
4. Check-out (facturar y liberar)
5. Editar ocupación
6. Ocupados actuales
7. Calendario mensual
8. Historial de facturación
9. Buscar
10. Exportar respaldo JSON
11. Importar respaldo JSON
12. Reiniciar sistema
0. Salir
"""


def main():
    mgr = HotelManager()
    actions = {
        "1": lambda: show_dashboard(mgr),
        "2": lambda: show_map(mgr),
        "3": lambda: do_check_in(mgr),
        "4": lambda: do_check_out(mgr),
        "5": lambda: do_edit(mgr),
        "6": lambda: show_occupied(mgr),
        "7": lambda: show_calendar(mgr),
        "8": lambda: show_history(mgr),
        "9": lambda: do_search(mgr),
        "10": lambda: do_export(mgr),
        "11": lambda: do_import(mgr),
        "12": lambda: do_reset(mgr),
    }
    while True:
        print(MENU)
        op = input("Seleccione: ").strip()
        if op == "0":
            print("¡Hasta luego!")
            break
        action = actions.get(op)
        if action:
            action()
            if op not in ("2", "7"):  # estas vistas son interactivas y ya pausan
                pause()
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    main()
