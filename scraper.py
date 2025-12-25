import requests
from bs4 import BeautifulSoup
import time
import random

# Headers para parecer un humano y no un robot (Anti-bloqueo básico)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9',
}

def scrape_generic_site(url, site_name):
    """
    Ejemplo genérico de cómo extraer datos.
    IMPORTANTE: Cada sitio tiene una estructura HTML diferente.
    Tienes que inspeccionar (F12) cada web para saber qué clases buscar.
    """
    print(f"--- Iniciando búsqueda en {site_name} ---")
    
    try:
        # 1. Descargar el HTML
        response = requests.get(url, headers=HEADERS)
        
        if response.status_code != 200:
            print(f"Error {response.status_code} al conectar con {url}")
            return []

        # 2. Analizar el HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        jobs_found = []

        # EJEMPLO: Buscamos elementos que parezcan tarjetas de trabajo
        # Nota: Estas clases (div.job-card) son inventadas. 
        # Tienes que ver el código real de Laborum/Computrabajo.
        cards = soup.find_all('div', class_='job-card') 
        
        for card in cards[:5]: # Limitamos a 5 para probar
            title = card.find('h2').text.strip() if card.find('h2') else "Sin título"
            company = card.find('span', class_='company').text.strip() if card.find('span', class_='company') else "Confidencial"
            
            job = {
                "role": title,
                "company": company,
                "source": site_name.upper(),
                "daysAgo": 0, # Asumimos hoy
                "hot": False
            }
            jobs_found.append(job)
            
        print(f"Encontradas {len(jobs_found)} ofertas en {site_name}")
        return jobs_found

    except Exception as e:
        print(f"Error grave en scraper: {e}")
        return []

# Ejemplo de uso
if __name__ == "__main__":
    # URLs de ejemplo (Probablemente necesites actualizarlas)
    urls = [
        ("https://www.ejemplo-empleos.cl/busqueda/planning", "CHILETRABAJOS"),
        # ("https://cl.linkedin.com/jobs/planning-jobs", "LINKEDIN"), # LinkedIn requiere login
    ]

    all_jobs = []
    for url, name in urls:
        jobs = scrape_generic_site(url, name)
        all_jobs.extend(jobs)
        # Esperar un poco entre peticiones para no ser bloqueado
        time.sleep(random.uniform(2, 5)) 

    print("Total ofertas extraídas:", len(all_jobs))
    # Aquí guardarías 'all_jobs' en un archivo JSON o Base de Datos