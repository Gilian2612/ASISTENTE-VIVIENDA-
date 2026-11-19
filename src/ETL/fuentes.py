"""Capas oficiales usadas como fuente de verdad (Catastro Bogotá / IDECA).

Todas son públicas y se consultan por ArcGIS REST sin autenticación.
Explorador: https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services
"""
from ETL import arcgis
from ETL.arcgis import BASE

CAPAS = {
    # 112 polígonos UPZ (Secretaría Distrital de Planeación, POT)
    "upz": f"{BASE}/ordenamientoterritorial/unidadplaneamientozonal/MapServer/0",
    # 20 localidades
    "localidades": f"{BASE}/Mapa_Referencia/Mapa_Referencia/MapServer/48",
    # Transporte público (TRANSMILENIO / SITP)
    "estaciones_tm": f"{BASE}/movilidad/transportepublico/MapServer/1",
    "portales_tm": f"{BASE}/movilidad/transportepublico/MapServer/2",
    "paraderos_sitp": f"{BASE}/movilidad/transportepublico/MapServer/5",
    # Sistema Distrital de Parques (IDRD)
    "parques": f"{BASE}/recreaciondeporte/parquesyescenarios/MapServer/1",
}

CAMPOS = {
    "upz": ("CODIGO_UPZ", "NOMBRE"),
    "localidades": ("LOCCODIGO", "LOCNOMBRE"),
    "estaciones_tm": ("ETRNOMBRE",),
    "portales_tm": ("ETRNOMBRE",),
    "paraderos_sitp": ("PSINOMBRE",),
    "parques": ("ID_PARQUE", "NOMBREPAR"),
}


def descargar(nombre, **kwargs):
    """Descarga todas las entidades de la capa `nombre` (GeoJSON, EPSG:9377)."""
    return arcgis.consultar(CAPAS[nombre], CAMPOS[nombre], **kwargs)


def descargar_todo(**kwargs):
    """Descarga todas las capas: {nombre: [features]}."""
    return {nombre: descargar(nombre, **kwargs) for nombre in CAPAS}
