"""Genera los iconos PNG de la PWA sin dependencias externas.

Pillow no esta instalado y no merece la pena anadirlo a requirements.txt solo
para dos imagenes, asi que estos PNG se escriben a mano: cabecera, un IDAT
comprimido con zlib y el IEND. Formato RGB de 8 bits, sin canal alfa.

El dibujo es un edificio dorado sobre el fondo oscuro del tema, con una
cuadricula de 10x10 ventanas — los 100 apartamentos del Aparthotel.

Uso:
    python make_icons.py

Reescribe icons/icon-192.png e icons/icon-512.png. Son un marcador de posicion
decente: si tienes un logo real, sustituye los archivos y no vuelvas a ejecutar
este script.
"""
import struct
import zlib
from pathlib import Path

ICONS_DIR = Path(__file__).resolve().parent / "icons"

# Colores tomados de :root en index.html
BG = (0x06, 0x0A, 0x14)        # --bg-primary
GOLD = (0xD4, 0xA8, 0x53)      # --gold
GOLD_LIGHT = (0xE8, 0xC9, 0x7A)  # --gold-light
WINDOW = (0x0A, 0x0E, 0x1A)    # --text-on-gold

SIZES = (192, 512)


def write_png(path: Path, width: int, height: int, rows: list) -> None:
    """Escribe un PNG RGB de 8 bits. `rows` son listas de tuplas (r, g, b)."""
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filtro 0 (None) en cada scanline
        for r, g, b in row:
            raw += bytes((r, g, b))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    # IHDR: ancho, alto, 8 bits, color 2 (RGB), sin entrelazado
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def draw_icon(size: int) -> list:
    """Edificio dorado centrado sobre fondo oscuro.

    El dibujo se mantiene dentro del 60% central para que el icono funcione
    tambien como `maskable`: Android recorta hasta un circulo inscrito y todo
    lo que quede fuera de esa zona segura se pierde.
    """
    rows = [[BG for _ in range(size)] for _ in range(size)]

    # Cuerpo del edificio
    b_w = int(size * 0.52)
    b_h = int(size * 0.60)
    x0 = (size - b_w) // 2
    y0 = int(size * 0.30)

    for y in range(y0, y0 + b_h):
        for x in range(x0, x0 + b_w):
            rows[y][x] = GOLD

    # Tejado: triangulo que sobresale un poco por los lados
    roof_h = int(size * 0.13)
    roof_w = int(b_w * 1.18)
    rx0 = (size - roof_w) // 2
    for i in range(roof_h):
        y = y0 - roof_h + i
        if y < 0:
            continue
        # El triangulo se ensancha conforme baja
        ancho = int(roof_w * (i + 1) / roof_h)
        inicio = (size - ancho) // 2
        for x in range(max(0, inicio), min(size, inicio + ancho)):
            rows[y][x] = GOLD_LIGHT

    # Ventanas: cuadricula 10x10 = los 100 apartamentos
    cols = filas = 10
    margen = max(1, int(b_w * 0.09))
    hueco_x = (b_w - 2 * margen) / cols
    hueco_y = (b_h - 2 * margen) / filas
    v_w = max(1, int(hueco_x * 0.55))
    v_h = max(1, int(hueco_y * 0.55))

    for f in range(filas):
        for c in range(cols):
            vx = int(x0 + margen + c * hueco_x + (hueco_x - v_w) / 2)
            vy = int(y0 + margen + f * hueco_y + (hueco_y - v_h) / 2)
            for y in range(vy, min(vy + v_h, size)):
                for x in range(vx, min(vx + v_w, size)):
                    rows[y][x] = WINDOW
    return rows


def main() -> None:
    ICONS_DIR.mkdir(exist_ok=True)
    for size in SIZES:
        destino = ICONS_DIR / f"icon-{size}.png"
        write_png(destino, size, size, draw_icon(size))
        print(f"  {destino.relative_to(ICONS_DIR.parent)}  ({destino.stat().st_size} bytes)")
    print("Iconos generados.")


if __name__ == "__main__":
    main()
