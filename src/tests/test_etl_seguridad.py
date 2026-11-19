import pytest

from ETL import seguridad
from ETL.seguridad import (
    CATEGORIAS_LOCALIDAD,
    CATEGORIAS_UPZ,
    PESO_LOCALIDAD,
    PESO_UPZ,
    campos,
    clave_localidad,
    codigo_upz,
    combinar,
    delitos_por_localidad,
    incidentes_por_upz,
    promedio_anual,
)


def feature(**props):
    return {"type": "Feature", "geometry": None, "properties": props}


class TestCampos:
    @pytest.mark.unit
    def test_nombres_del_servicio(self):
        assert campos({"H": "", "PIA": ""}, ("25", "26")) == [
            "CMH25CONT", "CMH26CONT", "CMPIA25CONT", "CMPIA26CONT"]

    @pytest.mark.unit
    def test_periodo_es_2025_2026(self):
        assert seguridad.ANIOS == ("25", "26")

    @pytest.mark.unit
    def test_pesos_suman_uno(self):
        assert PESO_UPZ == 0.7
        assert PESO_UPZ + PESO_LOCALIDAD == pytest.approx(1)


class TestPromedioAnual:
    @pytest.mark.unit
    def test_suma_categorias_y_promedia_anios(self):
        attrs = {"CMH25CONT": 10, "CMH26CONT": 20, "CMR25CONT": 4, "CMR26CONT": 6}
        assert promedio_anual(attrs, {"H": "", "R": ""}, ("25", "26")) == 20  # (30+10)/2

    @pytest.mark.unit
    def test_nulos_y_faltantes_cuentan_cero(self):
        assert promedio_anual({"CMH25CONT": None}, {"H": ""}, ("25", "26")) == 0


class TestCodigos:
    @pytest.mark.unit
    @pytest.mark.parametrize("entrada,salida", [
        ("UPZ37", "37"), ("UPZ1", "1"), ("upz09", "9"), (" UPZ108 ", "108"),
        ("UPR3", None), ("999", None), ("UPZ", None), ("UPZX1", None),
    ])
    def test_codigo_upz(self, entrada, salida):
        assert codigo_upz(entrada) == salida

    @pytest.mark.unit
    @pytest.mark.parametrize("a,b", [
        ("Usaquén", "USAQUEN"), ("Ciudad Bolívar", "CIUDAD BOLIVAR"),
        ("Antonio Nariño", "ANTONIO NARIÑO"), ("Los Mártires", "LOS MARTIRES"),
        ("Engativá", "ENGATIVA"),
    ])
    def test_clave_localidad_cruza_fuentes(self, a, b):
        assert clave_localidad(a) == clave_localidad(b) == b

    @pytest.mark.unit
    def test_clave_localidad_vacia(self):
        assert clave_localidad(None) == ""


class TestAgregados:
    @pytest.mark.unit
    def test_incidentes_por_upz_ignora_rurales(self):
        fs = [feature(CMIUUPLA="UPZ37", CMH25CONT=100, CMH26CONT=200),
              feature(CMIUUPLA="UPR1", CMH25CONT=5, CMH26CONT=5),
              feature(CMIUUPLA="999", CMH25CONT=5, CMH26CONT=5)]
        assert incidentes_por_upz(fs) == {"37": 150}

    @pytest.mark.unit
    def test_incidentes_usa_las_categorias_definidas(self):
        attrs = {f"CM{c}{a}CONT": 1 for c in CATEGORIAS_UPZ for a in ("25", "26")}
        attrs["CMHC25CONT"] = attrs["CMHC26CONT"] = 1000  # habitantes de calle: no cuenta
        assert incidentes_por_upz([feature(CMIUUPLA="UPZ1", **attrs)]) == {"1": len(CATEGORIAS_UPZ)}

    @pytest.mark.unit
    def test_delitos_por_localidad(self):
        fs = [feature(CMNOMLOCAL="Usaquén", CMHP25CONT=6000, CMHP26CONT=5000),
              feature(CMNOMLOCAL="Sin Localización", CMHP25CONT=9, CMHP26CONT=9),
              feature(CMNOMLOCAL=None, CMHP25CONT=9, CMHP26CONT=9)]
        assert delitos_por_localidad(fs) == {"USAQUEN": 5500}

    @pytest.mark.unit
    def test_delitos_usa_las_categorias_definidas(self):
        assert set(CATEGORIAS_LOCALIDAD) == {"H", "LP", "HP", "HR", "DS"}


class TestCombinar:
    @pytest.mark.unit
    def test_ponderado(self):
        assert combinar(1.0, 0.0) == pytest.approx(0.7)
        assert combinar(0.0, 1.0) == pytest.approx(0.3)

    @pytest.mark.unit
    def test_falta_un_componente(self):
        assert combinar(None, 0.4) == 0.4
        assert combinar(0.6, None) == 0.6

    @pytest.mark.unit
    def test_faltan_ambos(self):
        assert combinar(None, None) == 0.5
