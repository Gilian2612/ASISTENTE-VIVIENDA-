"""Tests de integración: consultan los servicios REALES de Catastro Bogotá / IDECA.

No corren por defecto (requieren red). Ejecutar con:

    pytest -m integration --no-cov

Verifican que cada fuente responde, trae los campos esperados y un volumen
razonable de datos, y que el pipeline completo produce >= 20 zonas válidas.
"""
import pytest

from ETL import arcgis, fuentes
from ETL.construir_zonas import COLUMNAS, construir

pytestmark = pytest.mark.integration

# Mínimos conservadores (valores observados en nov-2026 entre paréntesis).
MINIMOS = {
    "upz": 100,            # (112)
    "localidades": 20,     # (20)
    "estaciones_tm": 100,  # (140)
    "portales_tm": 5,      # (9)
    "paraderos_sitp": 5000,  # (7496)
    "parques": 3000,       # (5262)
}


@pytest.fixture(scope="module")
def capas():
    return fuentes.descargar_todo()


@pytest.mark.parametrize("nombre", sorted(fuentes.CAPAS))
def test_capa_responde_con_volumen_minimo(nombre):
    assert arcgis.contar(fuentes.CAPAS[nombre]) >= MINIMOS[nombre]


@pytest.mark.parametrize("nombre", sorted(fuentes.CAPAS))
def test_capa_acepta_la_consulta_del_etl(nombre):
    """Misma consulta que hace el ETL (campos, EPSG:9377, GeoJSON), limitada a 1 registro."""
    datos = arcgis.get_json(f"{fuentes.CAPAS[nombre]}/query", {
        "where": "1=1",
        "outFields": ",".join(fuentes.CAMPOS[nombre]),
        "outSR": arcgis.SR_METROS,
        "orderByFields": "OBJECTID",
        "resultOffset": 0,
        "resultRecordCount": 1,
        "f": "geojson",
    })
    (f,) = datos["features"]
    assert f["geometry"]["type"] in {"Point", "Polygon", "MultiPolygon"}
    for campo in fuentes.CAMPOS[nombre]:
        assert campo in f["properties"]


def test_descarga_completa_tiene_volumen_minimo(capas):
    for nombre, features in capas.items():
        assert len(features) >= MINIMOS[nombre], nombre


def test_campos_esperados_presentes(capas):
    for nombre, features in capas.items():
        for campo in fuentes.CAMPOS[nombre]:
            assert campo in features[0]["properties"], f"{nombre}.{campo}"


def test_geometrias_en_bogota_y_en_metros(capas):
    # En EPSG:9377 Bogotá está aprox. en x ≈ 4.85e6–4.92e6, y ≈ 2.03e6–2.12e6.
    x, y = capas["estaciones_tm"][0]["geometry"]["coordinates"][:2]
    assert 4_800_000 < x < 5_000_000
    assert 2_000_000 < y < 2_200_000


def test_pipeline_produce_al_menos_20_zonas_validas(capas):
    filas = construir(capas)
    assert len(filas) >= 20
    for f in filas:
        assert set(f) == set(COLUMNAS)
        assert f["area_km2"] > 0
        assert 0 <= f["transporte"] <= 1
        assert 0 <= f["verdes"] <= 1
    assert all(f["localidad"] for f in filas), "UPZ sin localidad asignada"


def test_upz_conocidas_tienen_sentido(capas):
    """Chequeo de cordura con UPZ conocidas de Bogotá."""
    por_nombre = {f["nombre"].upper(): f for f in construir(capas)}
    chapinero = por_nombre["CHAPINERO"]
    assert chapinero["localidad"] == "CHAPINERO"
    assert chapinero["estaciones_tm"] > 0
    # Las UPZ-parque deben tener mucho más verde que una UPZ densa del centro.
    assert por_nombre["PARQUE SALITRE"]["verdes"] > chapinero["verdes"]


def test_tipos_marcados_sin_excluir(capas):
    """Las UPZ industriales y dotacionales siguen en el dataset, marcadas."""
    por_nombre = {f["nombre"].upper(): f for f in construir(capas)}
    assert por_nombre["ZONA INDUSTRIAL"]["tipo"] == "industrial"
    assert por_nombre["PUENTE ARANDA"]["tipo"] == "industrial"
    assert por_nombre["AEROPUERTO EL DORADO"]["tipo"] == "dotacional"
    assert por_nombre["CHAPINERO"]["tipo"] == "residencial"


def test_parques_que_cruzan_limites_cuentan_en_varias_upz(capas):
    """Hay parques contados en más de una UPZ, sin duplicar el área total."""
    from ETL.construir_zonas import IndiceZonas, repartir_parques
    from ETL.geometria import area

    indice = IndiceZonas(capas["upz"], "CODIGO_UPZ")
    areas, conteo = repartir_parques(indice, capas["parques"])
    assert sum(conteo.values()) > len([p for p in capas["parques"] if p.get("geometry")]) * 0.9
    area_total = sum(area(p["geometry"]) for p in capas["parques"] if p.get("geometry"))
    assert sum(areas.values()) <= area_total * 1.001
