import pytest

from ETL import precio
from ETL.precio import arriendo_estimado, avaluo_por_upz, avaluos_por_zona, mediana


def manzana(valor, geometria=True):
    return {"type": "Feature", "properties": {precio.CAMPO_AVALUO: valor},
            "geometry": {"type": "Point", "coordinates": [0, 0]} if geometria else None}


class TestParametros:
    """Los parámetros documentados en DOCS/PRECIO.md."""

    @pytest.mark.unit
    def test_valores(self):
        assert precio.TASA_RENTA_ANUAL == 0.062        # OTC / UAECD
        assert precio.RELACION_AVALUO_COMERCIAL == 0.85  # punto medio 70 %-100 %
        assert precio.AREA_TIPICA_M2 == 60
        assert precio.VIGENCIA == 2026

    @pytest.mark.unit
    def test_where_filtra_vigencia_y_valores_positivos(self):
        assert "DATE '2026-01-01'" in precio.WHERE and "DATE '2027-01-01'" in precio.WHERE
        assert f"{precio.CAMPO_AVALUO} > 0" in precio.WHERE


class TestArriendoEstimado:
    @pytest.mark.unit
    def test_formula(self):
        # 2.550.000 / 0,85 = 3.000.000 COP/m² comercial; × 60 m² = 180 M; × 6,2 % / 12 = 930.000
        assert arriendo_estimado(2_550_000) == pytest.approx(930_000)

    @pytest.mark.unit
    def test_parametros_ajustables(self):
        assert arriendo_estimado(1_000_000, relacion=1, area_m2=12, tasa_anual=0.12) == pytest.approx(120_000)

    @pytest.mark.unit
    def test_es_proporcional_al_avaluo(self):
        assert arriendo_estimado(4e6) == pytest.approx(2 * arriendo_estimado(2e6))


class TestMediana:
    @pytest.mark.unit
    def test_mediana(self):
        assert mediana([3, 1, 2]) == 2
        assert mediana([1, 2, 3, 4]) == 2.5
        assert mediana([]) is None


class TestAvaluosPorZona:
    @pytest.mark.unit
    def test_agrupa_y_descarta_invalidos(self):
        zonas = iter(["A", "A", "B", None])
        fs = [manzana(1), manzana(2), manzana(3), manzana(4),    # la 4.ª cae fuera
              manzana(5, geometria=False), manzana(0), manzana(None),
              {"type": "Feature", "properties": None, "geometry": {"type": "Point"}}]
        assert avaluos_por_zona(fs, lambda g: next(zonas)) == {"A": [1, 2], "B": [3]}


class TestAvaluoPorUpz:
    @pytest.mark.unit
    def test_upz_con_suficientes_manzanas(self):
        r = avaluo_por_upz({"1": [1, 2, 3]}, {"1": "L"})
        assert r == {"1": (2, 3, "upz")}

    @pytest.mark.unit
    def test_pocas_manzanas_usa_la_localidad(self):
        r = avaluo_por_upz({"1": [10, 20, 30], "2": [100]}, {"1": "L", "2": "L"})
        assert r["2"] == (25, 1, "localidad")  # mediana de [10, 20, 30, 100]

    @pytest.mark.unit
    def test_sin_datos_en_la_localidad_usa_la_ciudad(self):
        r = avaluo_por_upz({"1": [1, 2, 3]}, {"1": "L", "2": "OTRA"})
        assert r["2"] == (2, 0, "ciudad")

    @pytest.mark.unit
    def test_sin_ningun_dato(self):
        assert avaluo_por_upz({}, {"1": "L"}) == {"1": (None, 0, "ciudad")}

    @pytest.mark.unit
    def test_minimo_configurable(self):
        assert avaluo_por_upz({"1": [5]}, {"1": "L"}, minimo=1) == {"1": (5, 1, "upz")}
