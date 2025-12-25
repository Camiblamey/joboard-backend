from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime

# Iniciamos la aplicación
app = FastAPI()

# Configuración de CORS (Importante para que React pueda hablar con Python)
# Esto permite que tu página web (localhost:3000 o tu dominio) pida datos aquí.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción, cambia "*" por tu dominio real
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- BASE DE DATOS SIMULADA ---
# En un sistema real, aquí te conectarías a PostgreSQL o MongoDB.
# Por ahora, usaremos una lista en memoria que se llena al arrancar.
fake_db = []

def generate_mock_data():
    """
    Genera datos si el scraper falla, para que la API siempre responda algo.
    """
    sources = ['LINKEDIN', 'LABORUM', 'COMPUTRABAJO']
    roles = ['Planner Junior', 'Supply Chain Manager', 'Analista de Demanda']
    
    data = []
    for i in range(5):
        data.append({
            "id": i + 100,
            "category": "Planner",
            "role": random.choice(roles),
            "company": f"Empresa Real {i}",
            "location": "Santiago, Chile",
            "daysAgo": 0,
            "source": random.choice(sources),
            "requirements": ["Python", "API", "React"],
            "salary": "Competitivo",
            "link": "#",
            "hot": True
        })
    return data

@app.get("/")
def read_root():
    return {"status": "Online", "message": "El cerebro de Joboard está funcionando"}

@app.get("/jobs")
def get_jobs():
    """
    Este es el endpoint que tu React va a llamar.
    Devuelve la lista de trabajos encontrados.
    """
    # 1. Aquí podrías llamar a tu función de scraping en tiempo real
    # o leer de tu base de datos.
    
    # Simulemos que leemos de la base de datos
    results = fake_db if fake_db else generate_mock_data()
    
    return results

@app.post("/trigger-scrape")
def trigger_scrape():
    """
    Un botón en tu admin panel podría llamar a esto para forzar
    una búsqueda de nuevas ofertas.
    """
    # Aquí importarías y ejecutarías tu lógica de scraper.py
    # from scraper import correr_scrapers
    # nuevos_datos = correr_scrapers()
    # fake_db.extend(nuevos_datos)
    return {"message": "Scraping iniciado (simulado)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)