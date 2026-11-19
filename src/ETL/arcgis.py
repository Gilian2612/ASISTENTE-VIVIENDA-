"""Cliente mínimo para servicios ArcGIS REST (solo librería estándar).

Se usa contra el servidor público de Catastro Bogotá / IDECA:
https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services
No requiere clave ni autenticación.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services"

# MAGNA-SIRGAS / Origen-Nacional (CTM12), en metros: permite calcular áreas
# y distancias directamente sobre las coordenadas.
SR_METROS = 9377

USER_AGENT = "asistente-vivienda-etl/0.1"


class ErrorArcGIS(Exception):
    """El servicio respondió con error o no se pudo contactar."""


def get_json(url, params, timeout=60, reintentos=3, espera=2.0):
    """GET `url?params` y devuelve el JSON. Reintenta ante fallos de red.

    Un error devuelto por el propio servicio (`{"error": ...}`) no se
    reintenta: se lanza `ErrorArcGIS` de inmediato.
    """
    url_completa = f"{url}?{urllib.parse.urlencode(params)}"
    peticion = urllib.request.Request(url_completa, headers={"User-Agent": USER_AGENT})
    ultimo_error = None
    for intento in range(reintentos):
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
                datos = json.load(respuesta)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            ultimo_error = e
            if intento < reintentos - 1:
                time.sleep(espera * (intento + 1))
            continue
        if isinstance(datos, dict) and "error" in datos:
            raise ErrorArcGIS(f"{url}: {datos['error']}")
        return datos
    raise ErrorArcGIS(f"{url}: sin respuesta tras {reintentos} intentos ({ultimo_error})")


def contar(url_capa, where="1=1", **kwargs):
    """Número de registros de la capa que cumplen `where`."""
    datos = get_json(
        f"{url_capa}/query",
        {"where": where, "returnCountOnly": "true", "f": "json"},
        **kwargs,
    )
    return datos["count"]


def consultar(url_capa, campos=("*",), where="1=1", out_sr=SR_METROS,
              tam_pagina=1000, geometria=True, **kwargs):
    """Descarga todas las entidades de una capa como lista de features GeoJSON.

    Pagina con `resultOffset` porque el servidor limita cada respuesta
    (maxRecordCount = 2000). Las geometrías vienen en `out_sr`; con
    `geometria=False` solo se descargan los atributos.
    """
    features = []
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": ",".join(campos),
            "outSR": out_sr,
            "returnGeometry": "true" if geometria else "false",
            "orderByFields": "OBJECTID",
            "resultOffset": offset,
            "resultRecordCount": tam_pagina,
            "f": "geojson",
        }
        datos = get_json(f"{url_capa}/query", params, **kwargs)
        lote = datos.get("features", [])
        features.extend(lote)
        excedido = datos.get("exceededTransferLimit") or (
            datos.get("properties") or {}
        ).get("exceededTransferLimit")
        if not lote or (len(lote) < tam_pagina and not excedido):
            return features
        offset += len(lote)
