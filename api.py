from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from main import HotelManager

app = FastAPI()
mgr = HotelManager()

# ESTA LÍNEA ES LA QUE FALTA EN TU ARCHIVO
# Permite que la web encuentre los archivos (css, js, etc.)
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def read_root():
    return FileResponse("index.html")

@app.get("/api/rooms")
def get_rooms():
    return [vars(r) for r in mgr.rooms]

@app.get("/api/stats")
def get_stats():
    total, available, occupied, rate = mgr.stats()
    return {
        "total": total,
        "available": available,
        "occupied": occupied,
        "rate": rate,
        "revenue": mgr.total_revenue
    }