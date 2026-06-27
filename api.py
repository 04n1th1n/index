import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from supabase import create_client
from main import HotelManager

app = FastAPI()
mgr = HotelManager()

# Configuración de Supabase (usando las variables que pondremos en Render)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Servir archivos estáticos y el index
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