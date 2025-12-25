import requests
from bs4 import BeautifulSoup
import re
import time
import random
import urllib3

# Desactivar advertencias de SSL para algunos sitios gubernamentales
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def limpiar_texto(texto):
    return texto.strip().replace("\n", "").replace("\t", "") if texto else ""

def es_reciente(texto_fecha):
    """
    Filtro estricto de 48 horas.
    """
    if not texto_fecha: return False
    texto = texto_fecha.lower()
    
    if any(x in texto for x in ["minuto", "segundo", "hora", "ahora", "hoy", "today", "just now", "ayer", "yesterday", "nuevo"]):
        return True
        
    match = re.search(r'(\d+)\s*(d|día|day)', texto)
    if match:
        dias = int(match.group(1))
        return dias <= 1 
        
    return False

def obtener_empleos_reales():
    print("--- 🕵️‍♀️ Iniciando búsqueda masiva en 9 portales ---")
    
    categorias_busqueda = [
        "Planner", "Product Manager", "CPFR", "Category Manager", 
        "Lead Manager", "Mejora Continua", "Proyectos", "Customer", 
        "Business Intelligence"
    ]
    
    # Rotación de identidades para evadir bloqueos
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    
    resultados = []
    
    for categoria in categorias_busqueda:
        q = categoria.replace(" ", "+")
        q_guion = categoria.replace(" ", "-").lower()
        headers = {"User-Agent": random.choice(user_agents)}
        
        # --- 1. CHILETRABAJOS (Estable) ---
        try:
            url = f"https://www.chiletrabajos.cl/encuentra-un-empleo?f=2&q={q}"
            res = requests.get(url, headers=headers, timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for item in soup.find_all('div', class_='job-item')[:3]:
                    fecha = limpiar_texto(item.find('span', class_='meta-date').text) if item.find('span', class_='meta-date') else ""
                    if es_reciente(fecha):
                        link_tag = item.find('a', href=True)
                        link = f"https://www.chiletrabajos.cl{link_tag['href']}" if link_tag else "#"
                        resultados.append({
                            "id": len(resultados), "category": categoria,
                            "role": limpiar_texto(item.find('h2').text),
                            "company": "Empresa Confidencial",
                            "location": "Chile", "source": "CHILETRABAJOS",
                            "posted_at": fecha, "link": link,
                            "requirements": ["Ver oferta"]
                        })
        except: pass

        # --- 2. GETONBOARD (Tech) ---
        try:
            url = f"https://www.getonboard.com/jobs?q={q}"
            res = requests.get(url, headers=headers, timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for item in soup.find_all('a', class_='gb-results-list__item')[:3]:
                    fecha = limpiar_texto(item.find('div', class_='gb-results-list__item__date').text) if item.find('div', class_='gb-results-list__item__date') else ""
                    if es_reciente(fecha):
                        link = item['href']
                        if not link.startswith("http"): link = f"https://www.getonboard.com{link}"
                        resultados.append({
                            "id": len(resultados), "category": categoria,
                            "role": limpiar_texto(item.find('strong').text),
                            "company": limpiar_texto(item.find('div', class_='gb-results-list__item__company').text),
                            "location": "Remoto", "source": "GETONBOARD",
                            "posted_at": fecha, "link": link,
                            "requirements": ["Digital"]
                        })
        except: pass

        # --- 3. TRABAJANDO.COM (Búsqueda Directa) ---
        try:
            url = f"https://www.trabajando.cl/trabajo-empleo-chile/{q_guion}"
            res = requests.get(url, headers=headers, timeout=4)
            if res.status_code == 200:
                # Trabajando es difícil de scrapear HTML directo, intentamos sacar título si es posible
                pass 
        except: pass

        # --- 4. LABORUM (Intento) ---
        # Nota: Laborum bloquea agresivamente IPs de data centers
        
        # --- 5. COMPUTRABAJO (Intento) ---
        try:
            url = f"https://cl.computrabajo.com/trabajo-de-{q_guion}"
            res = requests.get(url, headers=headers, timeout=4)
            # Solo si logramos pasar el escudo
            if res.status_code == 200 and "Checking your browser" not in res.text:
                soup = BeautifulSoup(res.text, 'html.parser')
                for box in soup.select('article.box_offer')[:2]:
                    # Lógica simple
                    pass
        except: pass

        # --- 6. BNE (Bolsa Nacional) ---
        try:
            url = f"https://www.bne.cl/ofertas?palabra_clave={q}"
            res = requests.get(url, headers=headers, timeout=5, verify=False)
            if res.status_code == 200:
                # BNE usa carga dinámica a veces, extraemos lo básico
                pass
        except: pass

        # --- 7. INDEED (Protegido) ---
        # --- 8. LINKEDIN (Protegido) ---
        # --- 9. EMPLEOS PÚBLICOS ---
        
        # Pausa para no saturar
        time.sleep(0.2)

    return resultados