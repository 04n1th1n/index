import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from supabase import create_client
from main import HotelManager

app = FastAPI()
mgr = HotelManager()

# Leemos las variables directamente de Render
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

print(f"DEBUG: URL cargada: {SUPABASE_URL}") # Esto nos dirá en los logs si está leyendo algo

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def read_root():
    return FileResponse("index.html")

@app.get("/api/rooms")
def get_rooms():
    return [vars(r) for r in mgr.rooms]

if __name__ == "__main__":
    # Render exige que el puerto sea el 10000
    uvicorn.run(app, host="0.0.0.0", port=10000)