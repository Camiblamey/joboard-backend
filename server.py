from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scraper import obtener_empleos_reales

app = FastAPI()

# Configuración de seguridad para permitir que tu web en Render hable con este servidor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "Google Hunter API Activa"}

@app.get("/jobs")
def get_jobs():
    # Llama al robot en tiempo real.
    # Si el robot devuelve una lista vacía (porque no encontró nada o Google bloqueó),
    # el frontend mostrará "Sin resultados reales".
    try:
        return obtener_empleos_reales()
    except Exception as e:
        print(f"Error crítico en el servidor: {e}")
        return []