"""Tests de la construcción del dataset con capas sintéticas (sin red).

Escenario: dos UPZ de 1 km x 1 km lado a lado dentro de una localidad.
"""
import csv

import pytest

from ETL.geometria import centroide
from ETL.construir_zonas import (
    COLUMNAS,
    IndiceZonas,
    construir,
    contar_puntos,
    escribir_csv,
    normalizar,
    repartir_area,
    repartir_parques,
    zonas_tocadas,
)

KM = 1000.0


def cuadrado(x0, y0, lado):
    return {"type": "Polygon", "coordinates": [[
        [x0, y0], [x0 + lado, y0], [x0 + lado, y0 + lado], [x0, y0 + lado], [x0, y0]
    ]]}


def poligono(props, geom):
    return {"type": "Feature", "properties": props, "geometry": geom}


def punto(x, y):
    return {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [x, y]}}


UPZ_A = poligono({"CODIGO_UPZ": "2", "NOMBRE": "A"}, cuadrado(0, 0, KM))
UPZ_B = poligono({"CODIGO_UPZ": "10", "NOMBRE": "B"}, cuadrado(KM, 0, KM))
LOCALIDAD = poligono({"LOCNOMBRE": "LOC1"}, cuadrado(-1, -1, 2 * KM + 2))


def incidentes(codigo, por_anio):
    """Feature de la capa 3 (incidentes 123 por UPZ) con `por_anio` hurtos en 2025 y 2026."""
    return {"type": "Feature", "geometry": None,
            "properties": {"CMIUUPLA": codigo, "CMH25CONT": por_anio, "CMH26CONT": por_anio}}


def delitos(localidad, por_anio):
    """Feature de la capa 0 (delitos por localidad) con `por_anio` homicidios en 2025 y 2026."""
    return {"type": "Feature", "geometry": None,
            "properties": {"CMNOMLOCAL": localidad, "CMH25CONT": por_anio, "CMH26CONT": por_anio}}


def capas_base(**cambios):
    capas = {
        "upz": [UPZ_A, UPZ_B],
        "localidades": [LOCALIDAD],
        "estaciones_tm": [punto(100, 100), punto(200, 200)],  # 2 en A
        "portales_tm": [punto(1500, 500)],                    # 1 en B
        "paraderos_sitp": [punto(1100, 100), punto(1200, 100), punto(5000, 5000)],  # 2 en B, 1 fuera
        "parques": [poligono({}, cuadrado(100, 100, 500))],   # 250.000 m² en A
        # SDSCJ: A con 10 incidentes/año, B con 100; LOC1 con 50 delitos/año.
        "incidentes_upz": [incidentes("UPZ2", 10), incidentes("UPZ10", 100), incidentes("UPR1", 999)],
        "delitos_localidad": [delitos("Loc1", 50), delitos("Sin Localización", 9)],
    }
    capas.update(cambios)
    return capas


class TestIndiceZonas:
    @pytest.mark.unit
    def test_buscar(self):
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        assert indice.buscar(10, 10) == "2"
        assert indice.buscar(KM + 10, 10) == "10"
        assert indice.buscar(-50, -50) is None

    @pytest.mark.unit
    def test_buscar_poligono_por_centroide(self):
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        assert indice.buscar_poligono(cuadrado(1100, 100, 50)) == "10"

    @pytest.mark.unit
    def test_buscar_poligono_por_mayoria_de_vertices(self):
        # Una "C" cuyo centroide cae en el hueco (fuera de la zona) pero
        # cuyos vértices están dentro de A.
        c = {"type": "Polygon", "coordinates": [[
            [100, 100], [900, 100], [900, 300], [300, 300], [300, 700],
            [900, 700], [900, 900], [100, 900], [100, 100],
        ]]}
        zona_sin_centro = poligono({"ID": "A"}, {"type": "Polygon", "coordinates": [
            cuadrado(0, 0, KM)["coordinates"][0],
            [[350, 350], [350, 650], [1000, 650], [1000, 350], [350, 350]][::-1],
        ]})
        indice = IndiceZonas([zona_sin_centro], "ID")
        assert centroide(c) == pytest.approx((440, 500))
        assert indice.buscar(440, 500) is None  # el centroide cae en el hueco
        assert indice.buscar_poligono(c) == "A"

    @pytest.mark.unit
    def test_buscar_poligono_fuera_de_todo(self):
        indice = IndiceZonas([UPZ_A], "CODIGO_UPZ")
        assert indice.buscar_poligono(cuadrado(10 * KM, 10 * KM, 10)) is None


class TestAgregados:
    @pytest.mark.unit
    def test_contar_puntos_ignora_los_de_fuera(self):
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        conteo = contar_puntos(indice, [punto(1, 1), punto(2, 2), punto(KM + 1, 1), punto(-9, -9)])
        assert conteo == {"2": 2, "10": 1}

    @pytest.mark.unit
    def test_zonas_tocadas(self):
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        assert zonas_tocadas(indice, cuadrado(100, 100, 50)) == {"2"}
        assert zonas_tocadas(indice, cuadrado(900, 100, 200)) == {"2", "10"}
        assert zonas_tocadas(indice, cuadrado(9 * KM, 0, 10)) == set()


class TestRepartirParques:
    """Un parque que cruza un límite cuenta en TODAS las UPZ que toca, y su
    área se reparte según la porción que cae en cada una."""

    @pytest.mark.unit
    def test_parque_dentro_de_una_upz_va_completo(self):
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        assert repartir_area(indice, cuadrado(100, 100, 100)) == pytest.approx({"2": 10_000})

    @pytest.mark.unit
    def test_parque_fuera_de_todo_no_suma(self):
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        assert repartir_area(indice, cuadrado(9 * KM, 0, 10)) == {}

    @pytest.mark.unit
    def test_parque_mitad_y_mitad(self):
        # 200x100 centrado en el límite x = 1000: 10.000 m² en cada UPZ.
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        reparto = repartir_area(indice, cuadrado(900, 100, 200))
        assert reparto == pytest.approx({"2": 20_000, "10": 20_000}, rel=0.05)
        assert sum(reparto.values()) == pytest.approx(40_000)

    @pytest.mark.unit
    def test_parque_25_75(self):
        # x de 950 a 1150: 50 m en A y 150 m en B.
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        geom = {"type": "Polygon", "coordinates": [[[950, 0], [1150, 0], [1150, 200], [950, 200], [950, 0]]]}
        reparto = repartir_area(indice, geom)
        assert reparto["2"] == pytest.approx(10_000, rel=0.1)
        assert reparto["10"] == pytest.approx(30_000, rel=0.1)

    @pytest.mark.unit
    def test_parque_triangular_solo_cuenta_puntos_dentro(self):
        # Triángulo con base sobre y=0 de x=800 a x=1200 y vértice en (1000, 400):
        # simétrico respecto al límite x=1000, área total 80.000 m².
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        geom = {"type": "Polygon", "coordinates": [[[800, 0], [1200, 0], [1000, 400], [800, 0]]]}
        reparto = repartir_area(indice, geom)
        assert sum(reparto.values()) == pytest.approx(80_000)
        assert reparto["2"] == pytest.approx(reparto["10"], rel=0.1)

    @pytest.mark.unit
    def test_poligono_largo_y_delgado_termina_rapido(self):
        # 2 km x 1 cm cruzando el límite: el paso se acota por el lado largo.
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        geom = {"type": "Polygon", "coordinates": [[[0, 10], [2000, 10], [2000, 10.01], [0, 10.01], [0, 10]]]}
        reparto = repartir_area(indice, geom)
        assert set(reparto) == {"2", "10"}

    @pytest.mark.unit
    def test_parte_fuera_de_las_upz_se_descarta(self):
        # Parque de 200x100 = 20.000 m²: la mitad con x < 0 queda fuera de toda UPZ.
        upz_c = poligono({"CODIGO_UPZ": "3"}, cuadrado(0, -KM, KM))
        indice = IndiceZonas([UPZ_A, upz_c], "CODIGO_UPZ")
        geom = {"type": "Polygon", "coordinates": [[[-100, -50], [100, -50], [100, 50], [-100, 50], [-100, -50]]]}
        reparto = repartir_area(indice, geom)
        assert sum(reparto.values()) == pytest.approx(10_000, rel=0.05)  # de 20.000

    @pytest.mark.unit
    def test_poligono_muy_delgado_reparte_por_igual(self):
        # Línea degenerada sobre el límite: ningún punto de la grilla cae dentro.
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        geom = {"type": "Polygon", "coordinates": [[[900, 100], [1100, 100], [900, 100]]]}
        reparto = repartir_area(indice, geom)
        assert set(reparto) == {"2", "10"}
        assert reparto["2"] == reparto["10"]

    @pytest.mark.unit
    def test_repartir_parques_cuenta_en_ambas_y_omite_sin_geometria(self):
        indice = IndiceZonas([UPZ_A, UPZ_B], "CODIGO_UPZ")
        parques = [
            poligono({}, cuadrado(100, 100, 100)),   # solo A
            poligono({}, cuadrado(900, 100, 200)),   # A y B
            poligono({}, None),
        ]
        areas, conteo = repartir_parques(indice, parques)
        assert conteo == {"2": 2, "10": 1}
        assert areas["2"] == pytest.approx(30_000, rel=0.05)
        assert areas["10"] == pytest.approx(20_000, rel=0.05)


class TestNormalizar:
    @pytest.mark.unit
    def test_vacio(self):
        assert normalizar([]) == []

    @pytest.mark.unit
    def test_todo_cero(self):
        assert normalizar([0, 0, 0]) == [0.0, 0.0, 0.0]

    @pytest.mark.unit
    def test_rango_y_maximo(self):
        assert normalizar([0, 5, 10], percentil=1.0) == pytest.approx([0, 0.5, 1])

    @pytest.mark.unit
    def test_atipico_se_recorta_a_uno(self):
        valores = list(range(1, 21)) + [1000]
        r = normalizar(valores)
        assert all(0 <= v <= 1 for v in r)
        assert r[-1] == 1.0
        assert r[0] > 0.04  # el atípico no aplasta al resto

    @pytest.mark.unit
    def test_referencia_define_la_escala(self):
        # El tope sale de la referencia [0, 10]; el 50 (fuera de escala) se recorta.
        assert normalizar([5, 50], percentil=1.0, referencia=[0, 10]) == [0.5, 1.0]

    @pytest.mark.unit
    def test_negativos_quedan_en_cero(self):
        assert normalizar([-5, 10], percentil=1.0) == [0.0, 1.0]


class TestConstruir:
    @pytest.mark.unit
    def test_una_fila_por_upz_con_todas_las_columnas(self):
        filas = construir(capas_base())
        assert len(filas) == 2
        assert all(set(f) == set(COLUMNAS) for f in filas)

    @pytest.mark.unit
    def test_orden_numerico_por_codigo(self):
        assert [f["codigo_upz"] for f in construir(capas_base())] == ["2", "10"]

    @pytest.mark.unit
    def test_valores_calculados(self):
        a, b = construir(capas_base())
        assert a["localidad"] == b["localidad"] == "LOC1"
        assert a["area_km2"] == pytest.approx(1.0)
        assert (a["estaciones_tm"], a["paraderos_sitp"]) == (2, 0)
        assert (b["estaciones_tm"], b["paraderos_sitp"]) == (1, 2)
        assert a["area_parques_m2"] == pytest.approx(250_000)
        assert a["parques"] == 1
        assert a["verde_pct"] == pytest.approx(25.0)
        assert b["verde_pct"] == 0.0

    @pytest.mark.unit
    def test_scores_en_rango_0_1(self):
        for f in construir(capas_base()):
            assert 0 <= f["transporte"] <= 1
            assert 0 <= f["verdes"] <= 1

    @pytest.mark.unit
    def test_mas_parque_mas_verdes(self):
        a, b = construir(capas_base())
        assert a["verdes"] > b["verdes"]

    @pytest.mark.unit
    def test_tipo_y_parques(self):
        a, b = construir(capas_base())
        assert a["tipo"] == b["tipo"] == "residencial"
        assert (a["parques"], b["parques"]) == (1, 0)

    @pytest.mark.unit
    def test_upz_industrial_marcada_no_excluida(self):
        industrial = poligono({"CODIGO_UPZ": "108", "NOMBRE": "ZONA INDUSTRIAL"}, cuadrado(5 * KM, 0, KM))
        filas = construir(capas_base(upz=[UPZ_A, UPZ_B, industrial]))
        assert [f["tipo"] for f in filas] == ["residencial", "residencial", "industrial"]

    @pytest.mark.unit
    def test_escala_se_calibra_con_residenciales(self):
        # Una UPZ dotacional 100 % parque no debe bajar el puntaje de A.
        parque = poligono({"CODIGO_UPZ": "103", "NOMBRE": "PARQUE"}, cuadrado(5 * KM, 0, KM))
        sin = construir(capas_base())
        con = construir(capas_base(
            upz=[UPZ_A, UPZ_B, parque],
            parques=capas_base()["parques"] + [poligono({}, cuadrado(5 * KM, 0, KM))],
        ))
        assert con[0]["verdes"] == sin[0]["verdes"]
        assert con[-1]["tipo"] == "dotacional" and con[-1]["verdes"] == 1.0

    @pytest.mark.unit
    def test_ignora_upz_sin_geometria_y_localidad_vacia_si_no_cae(self):
        sin_geom = poligono({"CODIGO_UPZ": "99", "NOMBRE": "X"}, None)
        filas = construir(capas_base(upz=[UPZ_A, sin_geom], localidades=[]))
        assert [f["codigo_upz"] for f in filas] == ["2"]
        assert filas[0]["localidad"] == ""

    @pytest.mark.unit
    def test_codigo_no_numerico_va_al_final(self):
        upz_x = poligono({"CODIGO_UPZ": "UPR1", "NOMBRE": "R"}, cuadrado(5 * KM, 0, KM))
        filas = construir(capas_base(upz=[upz_x, UPZ_B, UPZ_A]))
        assert [f["codigo_upz"] for f in filas] == ["2", "10", "UPR1"]

    @pytest.mark.unit
    def test_parque_mas_grande_que_la_upz_tope_100(self):
        filas = construir(capas_base(parques=[poligono({}, cuadrado(-KM, -KM, 3 * KM))]))
        assert max(f["verde_pct"] for f in filas) <= 100


class TestEscribirCsv:
    @pytest.mark.unit
    def test_crea_carpeta_y_escribe(self, tmp_path):
        ruta = tmp_path / "sub" / "zonas.csv"
        filas = construir(capas_base())
        escribir_csv(filas, ruta)
        with ruta.open(encoding="utf-8") as fh:
            leidas = list(csv.DictReader(fh))
        assert list(leidas[0]) == COLUMNAS
        assert [r["codigo_upz"] for r in leidas] == ["2", "10"]


class TestSeguridadEnConstruir:
    """La variable `seguridad` combina incidentes por UPZ (70 %) y delitos por localidad (30 %)."""

    @pytest.mark.unit
    def test_columnas_de_seguridad(self):
        a, b = construir(capas_base())
        assert (a["incidentes_123"], b["incidentes_123"]) == (10, 100)
        assert a["incidentes_123_km2"] == pytest.approx(10)
        assert a["delitos_localidad"] == b["delitos_localidad"] == 50

    @pytest.mark.unit
    def test_mas_incidentes_menos_seguridad(self):
        a, b = construir(capas_base())
        assert a["seguridad"] > b["seguridad"]
        assert all(0 <= f["seguridad"] <= 1 for f in (a, b))

    @pytest.mark.unit
    def test_valor_combinado(self):
        # Riesgo UPZ normalizado: A = 0.1, B = 1 → seguridad 0.9 y 0; misma
        # localidad → riesgo 1 → seguridad 0.  A = 0.7*0.9 + 0.3*0 = 0.63.
        a, b = construir(capas_base())
        assert a["seguridad"] == pytest.approx(0.63)
        assert b["seguridad"] == pytest.approx(0.0)

    @pytest.mark.unit
    def test_upz_sin_dato_usa_solo_la_localidad(self):
        a, b = construir(capas_base(incidentes_upz=[incidentes("UPZ2", 10)]))
        assert b["incidentes_123"] == "" and b["incidentes_123_km2"] == ""
        assert b["seguridad"] == pytest.approx(0.0)  # solo localidad (riesgo 1)

    @pytest.mark.unit
    def test_sin_ningun_dato_queda_neutral(self):
        filas = construir(capas_base(incidentes_upz=[], delitos_localidad=[]))
        assert all(f["seguridad"] == 0.5 for f in filas)
        assert all(f["delitos_localidad"] == "" for f in filas)

    @pytest.mark.unit
    def test_localidad_sin_geometria_se_ignora(self):
        sin_geom = poligono({"LOCNOMBRE": "OTRA"}, None)
        a, _ = construir(capas_base(localidades=[LOCALIDAD, sin_geom]))
        assert a["localidad"] == "LOC1"
        assert a["delitos_localidad_km2"] != ""
