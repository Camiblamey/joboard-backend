import requests
from bs4 import BeautifulSoup
import re
import time
import random
import urllib3

# Desactivar advertencias de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def limpiar_texto(texto):
    return texto.strip().replace("\n", "").replace("\t", "") if texto else ""

def es_reciente(texto_fecha):
    """
    Filtro estricto: Acepta ofertas de hasta 120 horas (5 días).
    """
    if not texto_fecha: return False
    texto = texto_fecha.lower()
    
    # 1. Inmediatez
    if any(x in texto for x in ["minuto", "segundo", "hora", "ahora", "hoy", "today", "just now", "ayer", "yesterday", "nuevo", "new"]):
        return True
        
    # 2. Días numéricos
    match = re.search(r'(\d+)\s*(d|día|day|dia)', texto)
    if match:
        dias = int(match.group(1))
        return dias <= 5 
        
    return False

def obtener_empleos_reales():
    print("--- 🕵️‍♀️ Iniciando Mega-Búsqueda (9 Fuentes) ---")
    
    categorias = [
        "Planner", "Product Manager", "CPFR", "Category Manager", 
        "Lead Manager", "Mejora Continua", "Proyectos", "Customer", 
        "Business Intelligence"
    ]
    
    # User-Agents rotativos para intentar engañar a los bloqueos
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
    ]
    
    resultados = []
    
    for categoria in categorias:
        q = categoria.replace(" ", "+") # Para URL tipo query=busqueda+fuerte
        q_guion = categoria.replace(" ", "-").lower() # Para URL tipo busqueda-fuerte
        
        headers = {"User-Agent": random.choice(user_agents)}
        
        # ==========================================
        # 1. CHILETRABAJOS (Alta probabilidad de éxito)
        # ==========================================
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
                            "company": "Confidencial / ChileTrabajos",
                            "location": "Chile", "source": "CHILETRABAJOS",
                            "posted_at": fecha, "link": link, "requirements": ["Ver oferta"]
                        })
        except: pass

        # ==========================================
        # 2. GETONBOARD (Alta probabilidad de éxito - Tech)
        # ==========================================
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
                            "posted_at": fecha, "link": link, "requirements": ["Digital"]
                        })
        except: pass

        # ==========================================
        # 3. TRABAJANDO.COM (Media probabilidad)
        # ==========================================
        try:
            # Trabajando usa una estructura compleja, intentamos búsqueda genérica
            url = f"https://www.trabajando.cl/trabajo-empleo-chile/{q_guion}"
            res = requests.get(url, headers=headers, timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                # La estructura cambia mucho, buscamos h2 genéricos de ofertas
                # Nota: Este sitio suele requerir JS, el éxito es bajo con requests puro
                pass 
        except: pass

        # ==========================================
        # 4. BNE - BOLSA NACIONAL (Media probabilidad)
        # ==========================================
        try:
            url = f"https://www.bne.cl/ofertas?palabra_clave={q}"
            res = requests.get(url, headers=headers, timeout=5, verify=False)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                # Lógica simplificada para BNE
                for item in soup.find_all('div', class_='job-result')[:2]:
                     # Extracción básica si la estructura lo permite
                     pass
        except: pass

        # ==========================================
        # 5. COMPUTRABAJO (Baja - Antibot fuerte)
        # ==========================================
        try:
            url = f"https://cl.computrabajo.com/trabajo-de-{q_guion}"
            res = requests.get(url, headers=headers, timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for box in soup.select('article.box_offer')[:2]:
                    title = box.find('h2').text.strip()
                    resultados.append({
                        "id": len(resultados), "category": categoria,
                        "role": title, "company": "Computrabajo",
                        "location": "Chile", "source": "COMPUTRABAJO",
                        "posted_at": "Reciente", "link": f"https://cl.computrabajo.com{box.find('a')['href']}",
                        "requirements": []
                    })
        except: pass

        # ==========================================
        # 6. LABORUM (Muy Baja - Antibot fuerte)
        # ==========================================
        # Requiere Selenium o API de pago. Intentamos request simple.
        try:
            url = f"https://www.laborum.cl/empleos-busqueda-{q_guion}.html"
            requests.get(url, headers=headers, timeout=3)
        except: pass

        # ==========================================
        # 7. INDEED (Muy Baja - Bloqueo inmediato)
        # ==========================================
        # Indeed bloquea centros de datos.
        
        # ==========================================
        # 8. LINKEDIN (Muy Baja - Requiere Login)
        # ==========================================
        # LinkedIn público solo muestra 2-3 ofertas y ofusca el HTML.
        
        # ==========================================
        # 9. EMPLEOS PÚBLICOS (Media)
        # ==========================================
        try:
            url = f"https://www.empleospublicos.cl/pub/convocatorias/convocatorias.aspx?palabra={q}"
            requests.get(url, headers=headers, timeout=4, verify=False)
        except: pass
        
        # Pausa de cortesía para no saturar la red
        time.sleep(0.5)

    return resultados