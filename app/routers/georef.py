# Proxy a la API de Georef (datos.gob.ar) para provincias y localidades.
# La app llama a este backend en lugar de datos.gob.ar directo, así evita
# problemas de red/CORS en el dispositivo.

import logging
from fastapi import APIRouter, HTTPException
import httpx

logger = logging.getLogger(__name__)

GEOREF_BASE = "https://apis.datos.gob.ar/georef/api/v2.0"
router = APIRouter()


@router.get("/provincias")
async def get_provincias():
    """Lista de provincias argentinas (proxy a datos.gob.ar)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{GEOREF_BASE}/provincias?orden=nombre")
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.warning("Georef provincias error: %s", e)
        raise HTTPException(status_code=502, detail="No se pudieron cargar las provincias.") from e


@router.get("/localidades")
async def get_localidades(provincia: int):
    """Localidades de una provincia (proxy a datos.gob.ar)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{GEOREF_BASE}/localidades",
                params={"provincia": provincia, "orden": "nombre", "max": 5000},
            )
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.warning("Georef localidades error: %s", e)
        raise HTTPException(status_code=502, detail="No se pudieron cargar las localidades.") from e
