# scraper.py
import re
import time
import json
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlencode, parse_qs

import requests
from bs4 import BeautifulSoup
import urllib3
import requests_cache

# -------------------------
# Config base
# -------------------------

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Cache de respuestas (reduce MUCHO llamadas repetidas)
# Ajusta expire_after si quieres (en segundos). Ej: 1800 = 30 min, 3600 = 1 hora.
requests_cache.install_cache("job_cache", expire_after=3600)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        # UA fijo (más “limpio” que rotarlo para camuflar). Puedes poner tu contacto real.
        "User-Agent": "JobAggregatorBot/1.0 (contact: tu-email@dominio.com)",
    })
    return s


class PoliteFetcher:
    """
    Rate limit por dominio + backoff ante 429/5xx + jitter.
    Esto NO “burla” nada: baja carga, respeta tiempos y evita reintentos agresivos.
    """

    def __init__(self, min_delay_by_domain=None, default_delay=10.0):
        self.min_delay_by_domain = min_delay_by_domain or {}
        self.default_delay = float(default_delay)
        self.last_request_ts = {}

    def _min_delay(self, domain: str) -> float:
        return float(self.min_delay_by_domain.get(domain, self.default_delay))

    def get(
        self,
        session: requests.Session,
        url: str,
        params=None,
        headers=None,
        timeout=(8, 20),
        max_retries=3,
        allow_redirects=True
    ):
        domain = urlparse(url).netloc.lower()
        headers = headers or {}

        # 1) Delay mínimo por dominio
        now = time.time()
        last = self.last_request_ts.get(domain, 0.0)
        wait = self._min_delay(domain) - (now - last)
        if wait > 0:
            time.sleep(wait + random.uniform(0.3, 1.2))

        # 2) Retries con backoff (y respeto de Retry-After)
        backoff = 4.0
        resp = None

        for _ in range(max_retries):
            resp = session.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                allow_redirects=allow_redirects,
                verify=True,
            )
            self.last_request_ts[domain] = time.time()

            if resp.status_code in (429, 500, 502, 503, 504):
                ra = resp.headers.get("Retry-After")
                sleep_s = int(ra) if (ra and ra.isdigit()) else (backoff + random.uniform(0.5, 2.0))
                time.sleep(sleep_s)
                backoff *= 1.8
                continue

            return resp

        return resp


def is_google_blocked(html: str, final_url: str) -> bool:
    """
    Detecta cuando Google no devolvió SERP real (consent/sorry/captcha),
    aunque venga status 200.
    """
    if not html:
        return True
    u = (final_url or "").lower()
    h = (html[:2500] or "").lower()
    signals = [
        "consent.google.com",
        "/sorry/",
        "unusual traffic",
        "our systems have detected unusual traffic",
        "recaptcha",
        "before you continue to google",
    ]
    return any(s in u for s in signals) or any(s in h for s in signals)


# Sesión + fetcher global (IMPORTANTE: no recrearlos dentro de cada función)
session = build_session()
fetcher = PoliteFetcher(
    min_delay_by_domain={
        "www.google.com": 12,
        "www.laborum.cl": 10,
        "www.chiletrabajos.cl": 10,
        "www.getonbrd.com": 12,
        "cl.indeed.com": 15,
        "www.empleospublicos.cl": 12,
    },
    default_delay=10.0
)

# -------------------------
# Utilidades
# -------------------------

def limpiar_texto(texto: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (texto or "")).strip()


def canonical_url(url: str) -> str:
    """
    Limpia redirecciones típicas de Google (/url?q=...) y trackers comunes para dedupe.
    """
    if not url:
        return url

    if "/url?q=" in url:
        url = url.split("/url?q=")[1].split("&")[0]

    parts = urlparse(url)
    q = parse_qs(parts.query, keep_blank_values=False)

    for k in list(q.keys()):
        if k.lower() in {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "ref", "refsrc"}:
            q.pop(k, None)

    new_query = urlencode({k: v[0] for k, v in q.items()})
    return parts._replace(query=new_query, fragment="").geturl()


def parse_relative_time(text: str) -> Optional[int]:
    """
    Devuelve horas desde publicación si logra interpretarlo.
    Acepta: "hace 2 horas", "hace 3 días", "ayer", "hoy", "just now".
    """
    if not text:
        return None
    t = text.lower()

    if any(x in t for x in ["just now", "ahora", "recién", "recien", "nuevo", "new"]):
        return 0
    if "hoy" in t or "today" in t:
        return 0
    if "ayer" in t or "yesterday" in t:
        return 24

    m = re.search(r"(\d+)\s*(minuto|minutos|min|minute|minutes)", t)
    if m:
        return 0
    m = re.search(r"(\d+)\s*(hora|horas|hour|hours)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(día|días|dia|dias|day|days)", t)
    if m:
        return int(m.group(1)) * 24

    return None


# -------------------------
# Modelo
# -------------------------

@dataclass
class Job:
    category: str
    role: str
    company: str
    location: str
    source: str
    link: str
    posted_raw: str = ""
    posted_hours_ago: Optional[int] = None
    requirements: Optional[List[str]] = None

    def to_dict(self) -> Dict:
        return {
            "category": self.category,
            "role": self.role,
            "company": self.company,
            "location": self.location,
            "source": self.source,
            "posted_at": self.posted_raw or "",
            "posted_hours_ago": self.posted_hours_ago,
            "link": self.link,
            "requirements": self.requirements or [],
        }


# -------------------------
# Google (fallback)
# -------------------------

def google_search_links(query: str, days: int = 5, num: int = 10) -> List[Dict]:
    """
    Scrape HTML de Google como fallback.
    Nota: Google puede bloquear en cloud; si detectamos bloqueo devolvemos [].
    """
    base = "https://www.google.com/search"
    params = {
        "q": query,
        "num": str(num),
        "hl": "es",
        "gl": "cl",
        "filter": "0",
        "tbs": f"qdr:d{days}",
    }

    r = fetcher.get(
        session=session,
        url=base,
        params=params,
        headers={"User-Agent": random.choice(USER_AGENTS)},
        timeout=(8, 20),
        max_retries=3
    )

    if not r or r.status_code != 200:
        return []

    if is_google_blocked(r.text, r.url):
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # Selector más actual, con fallback al antiguo
    blocks = soup.select("div.tF2Cxc") or soup.select("div.g")

    out = []
    for b in blocks:
        a = b.select_one("a[href]")
        h3 = b.select_one("h3")
        if not a or not h3:
            continue

        link = canonical_url(a.get("href", ""))
        title = limpiar_texto(h3.get_text(" ", strip=True))

        s = b.select_one("div.VwiC3b") or b.select_one("span.aCOpRe") or b.select_one("div.IsZvec")
        snippet = limpiar_texto(s.get_text(" ", strip=True)) if s else ""

        if not link.startswith("http"):
            continue

        out.append({"title": title, "link": link, "snippet": snippet})

    return out


# -------------------------
# Scrapers directos (best-effort, sin JS)
# -------------------------

def scrape_laborum(keyword: str, max_days: int = 5, pages: int = 2) -> List[Job]:
    d = min(max_days, 7)
    url_base = f"https://www.laborum.cl/empleos-publicacion-menor-a-{d}-dias.html"
    jobs: List[Job] = []

    for page in range(1, pages + 1):
        url = url_base if page == 1 else f"{url_base}?page={page}"

        r = fetcher.get(
            session=session,
            url=url,
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=(8, 20),
            max_retries=3
        )
        if not r or r.status_code != 200:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.select('a[href*="/empleos/"]'):
            href = a.get("href", "")
            if not href or "empleos-publicacion" in href:
                continue

            text = limpiar_texto(a.get_text(" ", strip=True))
            if not text or keyword.lower() not in text.lower():
                continue

            link = canonical_url(urljoin("https://www.laborum.cl", href))
            posted_hours = parse_relative_time(text)

            parts = re.split(r"\s{2,}| - ", text)
            role = (parts[0] if parts else text)[:140]
            company = (parts[1] if len(parts) > 1 else "Confidencial")[:120]

            jobs.append(Job(
                category=keyword,
                role=role,
                company=company,
                location="Chile",
                source="LABORUM",
                link=link,
                posted_raw=f"≤ {max_days} días (listado)",
                posted_hours_ago=posted_hours,
                requirements=[]
            ))

    return jobs


def scrape_chiletrabajos(keyword: str, pages: int = 1) -> List[Job]:
    jobs: List[Job] = []
    base = "https://www.chiletrabajos.cl/encuentra-un-empleo"

    for p in range(1, pages + 1):
        url = base if p == 1 else f"{base}?page={p}"

        r = fetcher.get(
            session=session,
            url=url,
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=(8, 20),
            max_retries=3
        )
        if not r or r.status_code != 200:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        for h2 in soup.select("h2"):
            a = h2.find("a", href=True)
            if not a:
                continue

            title = limpiar_texto(a.get_text(" ", strip=True))
            if keyword.lower() not in title.lower():
                continue

            link = canonical_url(urljoin("https://www.chiletrabajos.cl", a["href"]))

            company = "Empresa"
            location = "Chile"
            posted_raw = ""

            node = h2
            h3s = []
            for _ in range(3):
                node = node.find_next_sibling()
                if node and node.name == "h3":
                    h3s.append(node)

            if len(h3s) >= 1:
                company_loc = limpiar_texto(h3s[0].get_text(" ", strip=True))
                if "," in company_loc:
                    company, location = [x.strip() for x in company_loc.split(",", 1)]
                else:
                    company = company_loc

            if len(h3s) >= 2:
                posted_raw = limpiar_texto(h3s[1].get_text(" ", strip=True))

            jobs.append(Job(
                category=keyword,
                role=title[:140],
                company=company[:120] or "Empresa",
                location=location[:80] or "Chile",
                source="CHILETRABAJOS",
                link=link,
                posted_raw=posted_raw,
                posted_hours_ago=parse_relative_time(posted_raw),
                requirements=[]
            ))

    return jobs


def scrape_getonbrd(keyword: str, pages: int = 1) -> List[Job]:
    jobs: List[Job] = []
    base = "https://www.getonbrd.com/jobs"

    for p in range(1, pages + 1):
        url = base if p == 1 else f"{base}?page={p}"

        r = fetcher.get(
            session=session,
            url=url,
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=(8, 20),
            max_retries=3
        )
        if not r or r.status_code != 200:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.select('a[href^="/jobs/"]'):
            href = a.get("href", "")
            txt = limpiar_texto(a.get_text(" ", strip=True))
            if not txt or keyword.lower() not in txt.lower():
                continue

            link = canonical_url(urljoin("https://www.getonbrd.com", href))
            role = txt.split("  ")[0][:140]

            jobs.append(Job(
                category=keyword,
                role=role,
                company="(ver en link)",
                location="Chile/Remoto",
                source="GETONBRD",
                link=link,
                posted_raw="",
                posted_hours_ago=None,
                requirements=[]
            ))

    return jobs


def scrape_indeed(keyword: str, max_days: int = 5, pages: int = 1) -> List[Job]:
    jobs: List[Job] = []
    base = "https://cl.indeed.com/jobs"

    for i in range(pages):
        params = {"q": keyword, "l": "Chile", "fromage": str(max_days), "start": str(i * 10)}

        r = fetcher.get(
            session=session,
            url=base,
            params=params,
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=(8, 20),
            max_retries=3
        )
        if not r or r.status_code != 200:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        found_any = False

        # JSON-LD (cuando existe)
        for s in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(s.get_text())
            except Exception:
                continue

            posts = []
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                posts = [data]
            elif isinstance(data, list):
                posts = [x for x in data if isinstance(x, dict) and x.get("@type") == "JobPosting"]

            for post in posts:
                title = limpiar_texto(post.get("title") or "")
                if not title or keyword.lower() not in title.lower():
                    continue

                org = post.get("hiringOrganization", {}) or {}
                company = limpiar_texto(org.get("name") or "Empresa")

                loc = "Chile"
                if isinstance(post.get("jobLocation"), list) and post["jobLocation"]:
                    addr = post["jobLocation"][0].get("address", {}) or {}
                    loc = limpiar_texto(addr.get("addressLocality") or addr.get("addressRegion") or "Chile")

                link = canonical_url(post.get("url") or "")
                if not link:
                    continue

                jobs.append(Job(
                    category=keyword,
                    role=title[:140],
                    company=company[:120],
                    location=loc[:80],
                    source="INDEED",
                    link=link,
                    posted_raw=limpiar_texto(post.get("datePosted") or ""),
                    posted_hours_ago=parse_relative_time(limpiar_texto(post.get("datePosted") or "")),
                    requirements=[]
                ))
                found_any = True

        # fallback básico si no hubo JSON-LD parseable
        if not found_any:
            for a in soup.select('a[href*="/viewjob?"]'):
                title = limpiar_texto(a.get_text(" ", strip=True))
                if not title or keyword.lower() not in title.lower():
                    continue

                link = canonical_url(urljoin("https://cl.indeed.com", a.get("href", "")))
                jobs.append(Job(
                    category=keyword,
                    role=title[:140],
                    company="(ver en link)",
                    location="Chile",
                    source="INDEED",
                    link=link,
                    posted_raw=f"≤ {max_days} días (Indeed filter)",
                    posted_hours_ago=None,
                    requirements=[]
                ))

    return jobs


def scrape_empleos_publicos(keyword: str, max_items: int = 25) -> List[Job]:
    url = "https://www.empleospublicos.cl/pub/convocatorias/convocatorias.aspx"

    r = fetcher.get(
        session=session,
        url=url,
        headers={"User-Agent": random.choice(USER_AGENTS)},
        timeout=(8, 20),
        max_retries=3
    )
    if not r or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    jobs: List[Job] = []

    for a in soup.select('a[href*="convocatoria"]'):
        title = limpiar_texto(a.get_text(" ", strip=True))
        if not title or len(title) < 4:
            continue
        if keyword.lower() not in title.lower():
            continue

        link = canonical_url(urljoin(url, a.get("href", "")))

        jobs.append(Job(
            category=keyword,
            role=title[:160],
            company="Servicio Civil / Institución",
            location="Chile",
            source="EMPLEOSPÚBLICOS",
            link=link,
            posted_raw="(ver plazos en link)",
            posted_hours_ago=None,
            requirements=[]
        ))

        if len(jobs) >= max_items:
            break

    return jobs


# -------------------------
# Google -> Visitar portal (mejorar data)
# -------------------------

def infer_source_from_url(url: str) -> str:
    u = (url or "").lower()
    if "linkedin.com" in u: return "LINKEDIN"
    if "laborum.cl" in u: return "LABORUM"
    if "chiletrabajos.cl" in u: return "CHILETRABAJOS"
    if "getonbrd.com" in u: return "GETONBRD"
    if "computrabajo" in u: return "COMPUTRABAJO"
    if "trabajando.cl" in u: return "TRABAJANDO"
    if "bne.cl" in u: return "BNE"
    if "empleospublicos.cl" in u: return "EMPLEOSPÚBLICOS"
    if "indeed." in u: return "INDEED"
    return "OTRO"


def fetch_title_company_generic(url: str) -> Tuple[str, str, str]:
    """
    Extractor genérico (best-effort) desde la página del aviso.
    """
    r = fetcher.get(
        session=session,
        url=url,
        headers={"User-Agent": random.choice(USER_AGENTS)},
        timeout=(8, 20),
        max_retries=2
    )
    if not r or r.status_code != 200:
        return ("", "", "")

    soup = BeautifulSoup(r.text, "html.parser")

    h1 = soup.find(["h1", "h2"])
    title = limpiar_texto(h1.get_text(" ", strip=True)) if h1 else ""

    company = ""
    og = soup.find("meta", attrs={"property": "og:site_name"})
    if og and og.get("content"):
        company = limpiar_texto(og["content"])

    posted_raw = ""
    text = soup.get_text(" ", strip=True).lower()
    m = re.search(r"(publicado|actualizado)\s+hace\s+\d+\s+(minutos|minuto|horas|hora|días|día|dias|dia)", text)
    if m:
        posted_raw = m.group(0)

    return (title, company, posted_raw)


# -------------------------
# Dedupe + Orquestador
# -------------------------

def dedupe_jobs(jobs: List[Job]) -> List[Job]:
    seen = set()
    out = []
    for j in jobs:
        key = canonical_url(j.link) or (j.source + "|" + j.role + "|" + j.company)
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


def obtener_empleos(max_days: int = 5, google_per_category: int = 8) -> List[Dict]:
    categorias = [
        "Planner", "Product Manager", "CPFR", "Category Manager",
        "Lead Manager", "Mejora Continua", "Proyectos", "Customer",
        "Business Intelligence"
    ]

    all_jobs: List[Job] = []

    for cat in categorias:
        # 1) Portales directos
        all_jobs += scrape_laborum(cat, max_days=max_days, pages=2)
        all_jobs += scrape_chiletrabajos(cat, pages=1)
        all_jobs += scrape_getonbrd(cat, pages=1)
        all_jobs += scrape_indeed(cat, max_days=max_days, pages=1)
        all_jobs += scrape_empleos_publicos(cat, max_items=10)

        # 2) Google fallback
        sitios = (
            "(site:linkedin.com/jobs OR site:laborum.cl OR site:chiletrabajos.cl OR site:getonbrd.com OR "
            "site:computrabajo.cl OR site:trabajando.cl OR site:bne.cl OR site:empleospublicos.cl OR site:cl.indeed.com)"
        )
        query = f"{cat} empleo Chile {sitios}"

        serp = google_search_links(query=query, days=max_days, num=google_per_category)

        for item in serp:
            link = canonical_url(item.get("link", ""))
            if not link:
                continue

            src = infer_source_from_url(link)

            role = item.get("title", "") or cat
            company = "Empresa"
            posted_raw = ""

            # Enriquecer visitando aviso (evitar LinkedIn)
            if src != "LINKEDIN":
                t, c, p = fetch_title_company_generic(link)
                if t:
                    role = t
                if c and c.lower() != "google":
                    company = c
                if p:
                    posted_raw = p

            snippet = item.get("snippet", "") or ""

            all_jobs.append(Job(
                category=cat,
                role=role[:160],
                company=company[:120],
                location="Chile",
                source=src,
                link=link,
                posted_raw=posted_raw or snippet[:90],
                posted_hours_ago=parse_relative_time(posted_raw) if posted_raw else None,
                requirements=[snippet[:160] + "..."] if snippet else []
            ))

    deduped = dedupe_jobs(all_jobs)
    out = []
    for i, j in enumerate(deduped, 1):
        d = j.to_dict()
        d["id"] = i
        out.append(d)

    return out


# Alias por compatibilidad si tu server llamaba esto antes
def obtener_empleos_reales():
    return obtener_empleos(max_days=5, google_per_category=8)
