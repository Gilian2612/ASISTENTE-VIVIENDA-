import pytest

from ETL.tipos_upz import DOTACIONAL, INDUSTRIAL, RESIDENCIAL, TIPOS_UPZ, tipo_de


class TestTiposUpz:
    """Tabla hardcodeada de tipos de UPZ (industrial / dotacional / residencial)."""

    @pytest.mark.unit
    def test_industriales_conocidas(self):
        for codigo in ["108", "111", "76", "77", "112"]:
            assert tipo_de(codigo) == INDUSTRIAL

    @pytest.mark.unit
    def test_acepta_codigo_numerico(self):
        assert tipo_de(108) == INDUSTRIAL

    @pytest.mark.unit
    def test_por_defecto_residencial(self):
        assert tipo_de("99") == RESIDENCIAL  # Chapinero
        assert tipo_de("no-existe") == RESIDENCIAL

    @pytest.mark.unit
    def test_tabla_bien_formada(self):
        for codigo, (tipo, verificado, fuente) in TIPOS_UPZ.items():
            assert codigo.isdigit()
            assert tipo in {INDUSTRIAL, DOTACIONAL}
            assert isinstance(verificado, bool)
            assert fuente, codigo

    @pytest.mark.unit
    def test_industriales_tienen_fuente_verificada(self):
        for codigo, (tipo, verificado, _) in TIPOS_UPZ.items():
            if tipo == INDUSTRIAL:
                assert verificado, codigo
