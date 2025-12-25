from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scraper import obtener_empleos_reales

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "Robot de 9 Categorias Activo"}

@app.get("/jobs")
def get_jobs():
    datos = obtener_empleos_reales()
    return datos