import requests
from bs4 import BeautifulSoup
import re
import time
import random
import urllib3

# Desactivar advertencias de SSL para evitar logs sucios en la consola
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def limpiar_texto(texto):
    """Limpia espacios y saltos de línea innecesarios."""
    return texto.strip().replace("\n", "").replace("\t", "") if texto else ""

def es_reciente(texto_fecha):
    """
    Filtro estricto: Acepta ofertas de hasta 120 horas (5 días).
    """
    if not texto_fecha: return False
    texto = texto_fecha.lower()
    
    # 1. Conceptos de inmediatez (siempre aceptados)
    # Incluye términos como "nuevo", "hoy", "ayer"
    if any(x in texto for x in ["minuto", "segundo", "hora", "ahora", "hoy", "today", "just now", "ayer", "yesterday", "nuevo", "new"]):
        return True
        
    # 2. Análisis numérico de días (ej: "Hace 2 días")
    match = re.search(r'(\d+)\s*(d|día|day|dia)', texto)
    if match:
        dias = int(match.group(1))
        return dias <= 5  # Ventana de 5 días
        
    return False

def obtener_empleos_reales():
    print("--- 🕵️‍♀️ Iniciando Búsqueda Google Dorking (Estrategia Maestra) ---")
    
    categorias = [
        "Planner", "Product Manager", "CPFR", "Category Manager", 
        "Lead Manager", "Mejora Continua", "Proyectos", "Customer", 
        "Business Intelligence"
    ]
    
    # Rotación de identidades para parecer un humano ante Google
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    
    resultados = []
    
    for categoria in categorias:
        # ESTRATEGIA MAESTRA:
        # Usamos Google para buscar DENTRO de los 9 portales a la vez.
        # "site:..." limita la búsqueda a esos dominios.
        sitios = "(site:linkedin.com/jobs OR site:laborum.cl OR site:chiletrabajos.cl OR site:getonboard.com OR site:computrabajo.cl OR site:trabajando.cl OR site:bne.cl OR site:empleospublicos.cl OR site:cl.indeed.com)"
        
        # Consulta de búsqueda
        query = f'"{categoria}" empleo chile {sitios}'
        query_url = query.replace(" ", "+").replace('"', '%22').replace(":", "%3A").replace("/", "%2F").replace("(", "%28").replace(")", "%29")
        
        # URL de Google con filtro de tiempo (tbs=qdr:d5 = últimos 5 días)
        url = f"https://www.google.com/search?q={query_url}&tbs=qdr:d5&gl=cl&hl=es"
        
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        try:
            # Pausa humana aleatoria para evitar bloqueo 429
            time.sleep(random.uniform(2.0, 5.0))
            
            res = requests.get(url, headers=headers, timeout=10)
            
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Buscamos los bloques de resultados de Google (clase 'g')
                bloques = soup.find_all('div', class_='g')
                
                # Procesamos los primeros 3 resultados por categoría
                for bloque in bloques[:3]:
                    link_tag = bloque.find('a', href=True)
                    titulo_tag = bloque.find('h3')
                    
                    if link_tag and titulo_tag:
                        link = link_tag['href']
                        titulo_completo = titulo_tag.text
                        
                        # Limpiar redirecciones de Google
                        if "/url?q=" in link:
                            link = link.split("/url?q=")[1].split("&")[0]
                            
                        # Identificar la fuente según el dominio
                        fuente = "OTRO"
                        if "linkedin" in link: fuente = "LINKEDIN"
                        elif "laborum" in link: fuente = "LABORUM"
                        elif "computrabajo" in link: fuente = "COMPUTRABAJO"
                        elif "trabajando" in link: fuente = "TRABAJANDO"
                        elif "chiletrabajos" in link: fuente = "CHILETRABAJOS"
                        elif "getonboard" in link: fuente = "GETONBOARD"
                        elif "bne.cl" in link: fuente = "BNE"
                        
                        # Intentar limpiar el título (Formato usual: Cargo - Empresa - Sitio)
                        partes = titulo_completo.split(" - ")
                        cargo = partes[0]
                        empresa = partes[1] if len(partes) > 1 else "Empresa Confidencial"
                        
                        # Extraer snippet de fecha si existe
                        snippet_div = bloque.find('div', style='-webkit-line-clamp:2')
                        snippet = snippet_div.text if snippet_div else "Ver detalles..."

                        resultados.append({
                            "id": len(resultados) + 1,
                            "category": categoria,
                            "role": cargo,
                            "company": empresa,
                            "location": "Chile",
                            "source": fuente,
                            "posted_at": "Hace < 5 días",
                            "link": link,
                            "requirements": [snippet[:100] + "..."]
                        })
            
            elif res.status_code == 429:
                print(f"⚠️ Google detectó tráfico inusual (Error 429). Saltando categoría {categoria}...")
                time.sleep(10) # Castigo por detección

        except Exception as e:
            print(f"Error buscando {categoria}: {e}")

    return resultados