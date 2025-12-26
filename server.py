from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from scraper import obtener_empleos_reales

import time
import threading

app = FastAPI()

# CORS (idealmente restringe a tu dominio de Render después)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Cache en memoria (TTL)
# =========================

CACHE_TTL_SECONDS = 30 * 60  # 30 min (ajusta: 20-60 min recomendado)
_cache = {
    "data": [],
    "ts": 0.0,         # timestamp de última actualización
    "last_error": None # último error, si hubo
}
_lock = threading.Lock()

def _is_cache_valid() -> bool:
    return _cache["data"] and (time.time() - _cache["ts"] < CACHE_TTL_SECONDS)

def _refresh_cache(force: bool = False):
    """
    Refresca el cache si expiró o si force=True.
    Protegido por lock para evitar scrapes simultáneos.
    """
    with _lock:
        if not force and _is_cache_valid():
            return

        try:
            data = obtener_empleos_reales()
            # aunque venga vacío, lo guardamos: así no martillas si Google bloqueó hoy
            _cache["data"] = data if isinstance(data, list) else []
            _cache["ts"] = time.time()
            _cache["last_error"] = None
        except Exception as e:
            _cache["last_error"] = str(e)
            # NO borramos datos anteriores; servimos lo último bueno
            if not _cache["data"]:
                _cache["data"] = []
            _cache["ts"] = time.time()


@app.get("/")
def home():
    return {"status": "Job Hunter API Activa", "cache_ttl_seconds": CACHE_TTL_SECONDS}


@app.get("/jobs")
def get_jobs(response: Response, refresh: int = 0):
    """
    refresh=1 fuerza actualización (útil para ti, no para el frontend).
    Por defecto sirve cache (evita bloqueos y acelera la web).
    """
    force = bool(refresh)

    # Si cache válido y no forzado => no scrapea
    if not force and _is_cache_valid():
        response.headers["X-Cache"] = "HIT"
        response.headers["Cache-Control"] = f"public, max-age={CACHE_TTL_SECONDS}"
        return _cache["data"]

    # Si no hay cache válido => refresca (una sola vez por lock)
    _refresh_cache(force=force)

    response.headers["X-Cache"] = "MISS" if force else ("REFRESHED" if _cache["data"] else "EMPTY")
    response.headers["Cache-Control"] = f"public, max-age={CACHE_TTL_SECONDS}"
    if _cache["last_error"]:
        response.headers["X-Last-Error"] = _cache["last_error"][:200]

    return _cache["data"]


@app.get("/health")
def health():
    """
    Útil para monitoreo.
    """
    age = time.time() - _cache["ts"] if _cache["ts"] else None
    return {
        "ok": True,
        "cache_items": len(_cache["data"]) if _cache["data"] else 0,
        "cache_age_seconds": age,
        "last_error": _cache["last_error"],
    }
