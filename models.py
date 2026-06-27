"""Modelo de datos y configuración del Aparthotel Paros.

Refleja el mismo modelo del panel web (index.html) para que los respaldos JSON
sean intercambiables entre ambas aplicaciones.
"""
from dataclasses import dataclass, field
from typing import Optional
import unicodedata

# ============================================================
#  CONFIGURACIÓN POR TIPO DE DEPARTAMENTO
# ============================================================
BEDROOMS_BY_TYPE = {"standard": 2, "suite": 3, "vip": 4}
TYPE_SHORT = {"standard": "Estándar", "suite": "Suite", "vip": "VIP"}
TYPE_LABEL = {"standard": "2 Dormitorios", "suite": "3 Dormitorios", "vip": "4 Dormitorios"}
AREA_BY_TYPE = {"standard": 76.62, "suite": 100.48, "vip": 115.24}
PRICE_BY_TYPE = {"standard": 120000, "suite": 200000, "vip": 350000}

TYPES = ["standard", "suite", "vip"]

MONTHS_FULL = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
MONTHS_ABBR = [
    "ene.", "feb.", "mar.", "abr.", "may.", "jun.",
    "jul.", "ago.", "sep.", "oct.", "nov.", "dic.",
]


def bedrooms(room_type: str) -> int:
    return BEDROOMS_BY_TYPE.get(room_type, 0)


def area_of(room_type: str) -> float:
    return AREA_BY_TYPE.get(room_type, 0.0)


# ============================================================
#  HELPERS DE FORMATO (equivalentes a los del index.html)
# ============================================================
def currency(value) -> str:
    """Formato CLP: $120.000 (punto como separador de miles, sin decimales)."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        n = 0
    return "$" + f"{n:,}".replace(",", ".")


def format_date(iso: Optional[str]) -> str:
    """'2026-06-25' -> '25 jun. 2026'. Cadena vacía si no hay fecha."""
    if not iso:
        return ""
    try:
        y, m, d = (int(x) for x in iso[:10].split("-"))
        return f"{d:02d} {MONTHS_ABBR[m - 1]} {y}"
    except (ValueError, IndexError):
        return iso


def normalize_text(s: Optional[str]) -> str:
    """Minúsculas sin acentos, para búsquedas tolerantes (como normalizeText en JS)."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn").lower().strip()


# ============================================================
#  DEPARTAMENTO
# ============================================================
@dataclass
class Room:
    id: int
    number: str
    type: str
    price: int
    status: str = "available"           # 'available' | 'occupied'
    guest: Optional[str] = None
    nights: int = 1
    checkin_date: Optional[str] = None  # ISO 'YYYY-MM-DD'
    checkout_date: Optional[str] = None
    terrace: bool = True
    notes: str = ""

    # --- propiedades derivadas ---
    @property
    def bedrooms(self) -> int:
        return bedrooms(self.type)

    @property
    def area(self) -> float:
        return area_of(self.type)

    @property
    def floor(self) -> int:
        return int(self.number) // 100

    @property
    def is_occupied(self) -> bool:
        return self.status == "occupied"

    # --- serialización compatible con el backup del index.html (camelCase) ---
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "number": self.number,
            "type": self.type,
            "price": self.price,
            "status": self.status,
            "guest": self.guest,
            "nights": self.nights,
            "checkinDate": self.checkin_date,
            "checkoutDate": self.checkout_date,
            "terrace": self.terrace,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Room":
        return cls(
            id=int(d["id"]),
            number=str(d["number"]),
            type=d.get("type", "standard"),
            price=int(d.get("price", PRICE_BY_TYPE.get(d.get("type", "standard"), 0))),
            status=d.get("status", "available"),
            guest=d.get("guest"),
            nights=int(d.get("nights", 1) or 1),
            checkin_date=d.get("checkinDate") or d.get("checkin_date"),
            checkout_date=d.get("checkoutDate") or d.get("checkout_date"),
            terrace=d.get("terrace", True),
            notes=d.get("notes", "") or "",
        )
