import pytest

from ETL.geometria import (
    area,
    area_con_signo,
    caja,
    centroide,
    en_caja,
    poligonos,
    punto_en_anillo,
    punto_en_poligono,
)


def anillo_cuadrado(x0, y0, lado, antihorario=True):
    pts = [[x0, y0], [x0 + lado, y0], [x0 + lado, y0 + lado], [x0, y0 + lado], [x0, y0]]
    return pts if antihorario else pts[::-1]


def cuadrado(x0, y0, lado):
    return {"type": "Polygon", "coordinates": [anillo_cuadrado(x0, y0, lado)]}


# Cuadrado 10x10 con un hueco 2x2 en el centro (área 96)
CON_HUECO = {
    "type": "Polygon",
    "coordinates": [anillo_cuadrado(0, 0, 10), anillo_cuadrado(4, 4, 2, antihorario=False)],
}

MULTI = {
    "type": "MultiPolygon",
    "coordinates": [[anillo_cuadrado(0, 0, 2)], [anillo_cuadrado(10, 10, 2)]],
}


class TestPoligonos:
    """`poligonos` normaliza Polygon y MultiPolygon a una lista de polígonos."""

    @pytest.mark.unit
    def test_polygon_da_uno(self):
        assert len(poligonos(cuadrado(0, 0, 1))) == 1

    @pytest.mark.unit
    def test_multipolygon_da_varios(self):
        assert len(poligonos(MULTI)) == 2

    @pytest.mark.unit
    def test_tipo_no_soportado_falla(self):
        with pytest.raises(ValueError):
            poligonos({"type": "Point", "coordinates": [0, 0]})


class TestArea:
    """Área por la fórmula del zapato, con signo según orientación y huecos restados."""

    @pytest.mark.unit
    def test_signo_segun_orientacion(self):
        assert area_con_signo(anillo_cuadrado(0, 0, 2)) == pytest.approx(4)
        assert area_con_signo(anillo_cuadrado(0, 0, 2, antihorario=False)) == pytest.approx(-4)

    @pytest.mark.unit
    def test_cuadrado(self):
        assert area(cuadrado(5, 5, 3)) == pytest.approx(9)

    @pytest.mark.unit
    def test_resta_huecos(self):
        assert area(CON_HUECO) == pytest.approx(96)

    @pytest.mark.unit
    def test_multipolygon_suma(self):
        assert area(MULTI) == pytest.approx(8)


class TestCentroide:
    """Centroide ponderado por área."""

    @pytest.mark.unit
    def test_cuadrado(self):
        assert centroide(cuadrado(0, 0, 2)) == pytest.approx((1, 1))

    @pytest.mark.unit
    def test_hueco_simetrico_no_lo_mueve(self):
        assert centroide(CON_HUECO) == pytest.approx((5, 5))

    @pytest.mark.unit
    def test_multipolygon_iguales_queda_en_medio(self):
        assert centroide(MULTI) == pytest.approx((6, 6))

    @pytest.mark.unit
    def test_poligono_degenerado_usa_promedio_de_vertices(self):
        linea = {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [4, 0], [0, 0]]]}
        x, y = centroide(linea)
        assert y == 0 and 0 <= x <= 4


class TestCaja:
    @pytest.mark.unit
    def test_caja_multipolygon(self):
        assert caja(MULTI) == (0, 0, 12, 12)

    @pytest.mark.unit
    def test_en_caja_incluye_bordes(self):
        c = (0, 0, 1, 1)
        assert en_caja(0, 0, c) and en_caja(1, 1, c) and not en_caja(1.1, 0.5, c)


class TestPuntoEnPoligono:
    """Ray casting, respetando huecos y MultiPolygon."""

    @pytest.mark.unit
    def test_dentro_y_fuera_de_anillo(self):
        anillo = anillo_cuadrado(0, 0, 10)
        assert punto_en_anillo(5, 5, anillo)
        assert not punto_en_anillo(15, 5, anillo)

    @pytest.mark.unit
    def test_punto_en_hueco_esta_fuera(self):
        assert not punto_en_poligono(5, 5, CON_HUECO)
        assert punto_en_poligono(1, 1, CON_HUECO)

    @pytest.mark.unit
    def test_multipolygon_cualquier_parte(self):
        assert punto_en_poligono(11, 11, MULTI)
        assert not punto_en_poligono(5, 5, MULTI)

    @pytest.mark.unit
    def test_poligono_concavo(self):
        # Forma de "U": el punto en la abertura está fuera.
        u = {"type": "Polygon", "coordinates": [[
            [0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3], [0, 0]
        ]]}
        assert not punto_en_poligono(1.5, 2, u)
        assert punto_en_poligono(0.5, 2, u)
