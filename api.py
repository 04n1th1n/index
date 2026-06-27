import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from supabase import create_client

app = FastAPI()

# Conexión a Supabase usando las variables secretas de Render
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Servir archivos estáticos y el index
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def read_root():
    return FileResponse("index.html")

# RUTA PARA GUARDAR DATOS (Cuando el usuario hace Check-in/out en la web)
@app.post("/api/update")
async def update_data(request: Request):
    data = await request.json()
    # Guardamos en la tabla 'hotel_data' de Supabase
    # El id: 1 es para que siempre sobrescriba el mismo registro principal
    supabase.table("hotel_data").upsert({"id": 1, "data": data}).execute()
    return {"status": "success"}

# RUTA PARA LEER DATOS (Cuando el usuario abre la página)
@app.get("/api/rooms")
def get_rooms():
    # Buscamos el registro con id 1
    response = supabase.table("hotel_data").select("data").eq("id", 1).execute()
    if response.data:
        return response.data[0]['data']['rooms']
    return [] # Si no hay nada, devuelve lista vacía