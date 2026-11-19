"""Capas oficiales usadas como fuente de verdad.

Todas son públicas y se consultan por ArcGIS REST sin autenticación:
- Catastro Bogotá / IDECA: https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services
- SDSCJ (Secretaría Distrital de Seguridad, Convivencia y Justicia):
  https://oaiee.scj.gov.co/agc/rest/services/Tematicos_Pub/CifrasSCJ/MapServer
"""
from ETL import arcgis, seguridad
from ETL.arcgis import BASE

BASE_SDSCJ = "https://oaiee.scj.gov.co/agc/rest/services/Tematicos_Pub/CifrasSCJ/MapServer"

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
    # Seguridad (SDSCJ): incidentes línea 123 por UPZ y delitos SIEDCO por localidad
    "incidentes_upz": f"{BASE_SDSCJ}/3",
    "delitos_localidad": f"{BASE_SDSCJ}/0",
}

CAMPOS = {
    "upz": ("CODIGO_UPZ", "NOMBRE"),
    "localidades": ("LOCCODIGO", "LOCNOMBRE"),
    "estaciones_tm": ("ETRNOMBRE",),
    "portales_tm": ("ETRNOMBRE",),
    "paraderos_sitp": ("PSINOMBRE",),
    "parques": ("ID_PARQUE", "NOMBREPAR"),
    "incidentes_upz": ("CMIUUPLA", "CMNOMUPLA", *seguridad.campos(seguridad.CATEGORIAS_UPZ)),
    "delitos_localidad": ("CMIULOCAL", "CMNOMLOCAL", *seguridad.campos(seguridad.CATEGORIAS_LOCALIDAD)),
}

# Capas de las que solo se necesitan atributos (cifras), no geometría.
SIN_GEOMETRIA = {"incidentes_upz", "delitos_localidad"}


def descargar(nombre, **kwargs):
    """Descarga todas las entidades de la capa `nombre` (GeoJSON, EPSG:9377)."""
    return arcgis.consultar(
        CAPAS[nombre], CAMPOS[nombre], geometria=nombre not in SIN_GEOMETRIA, **kwargs
    )


def descargar_todo(**kwargs):
    """Descarga todas las capas: {nombre: [features]}."""
    return {nombre: descargar(nombre, **kwargs) for nombre in CAPAS}
