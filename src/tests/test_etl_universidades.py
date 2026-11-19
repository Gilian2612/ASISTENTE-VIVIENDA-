import pytest

from ETL import universidades as U
from ETL.geometria import punto_en_poligono, wgs84_a_ctm12


def cuadrado(x0, y0, lado):
    return {"type": "Polygon", "coordinates": [[
        [x0, y0], [x0 + lado, y0], [x0 + lado, y0 + lado], [x0, y0 + lado], [x0, y0]]]}


def campus(nombre, geom):
    return {"type": "Feature", "properties": {"NOMBRE": nombre}, "geometry": geom}


def ies(nombre, x, y, estado="01"):
    return {"type": "Feature", "properties": {"NOMBRE": nombre, "ESTADO": estado},
            "geometry": {"type": "Point", "coordinates": [x, y]}}


class TestProyeccion:
    """WGS84 -> EPSG:9377, comparado con puntos proyectados por el servidor de Catastro."""

    @pytest.mark.unit
    @pytest.mark.parametrize("lon,lat,x,y", [
        (-74.08981575, 4.63942077, 4879166.618034107, 2070743.9172044687),   # U. Nacional
        (-74.05812355, 4.65850505, 4882684.053018095, 2072847.6271308465),   # U. Pedagógica
        (-74.06886266, 4.61495298, 4881485.99381799, 2068036.3889202254),    # U. Colegio Mayor
        (-74.03287714099997, 4.7034075170000165, 4885490.770863603, 2077805.6965954362),
    ])
    def test_coincide_con_el_servidor(self, lon, lat, x, y):
        px, py = wgs84_a_ctm12(lon, lat)
        assert px == pytest.approx(x, abs=0.01)
        assert py == pytest.approx(y, abs=0.01)

    @pytest.mark.unit
    def test_origen(self):
        assert wgs84_a_ctm12(-73.0, 4.0) == pytest.approx((5_000_000, 2_000_000), abs=1e-6)


class TestSedesSnies:
    @pytest.mark.unit
    def test_excluye_inactivas_y_sin_coordenadas(self):
        fs = [ies("A", 1, 2), ies("B", 3, 4, estado="00"),
              {"type": "Feature", "properties": {"NOMBRE": "C", "ESTADO": "01"},
               "geometry": {"type": "Point", "coordinates": []}},
              {"type": "Feature", "properties": {"NOMBRE": "D", "ESTADO": "01"}, "geometry": None}]
        assert U.sedes_snies(fs) == [{"nombre": "A", "x": 1, "y": 2, "fuente": "SNIES"}]


class TestSedesManuales:
    @pytest.mark.unit
    def test_convierte_a_metros(self):
        (s,) = U.sedes_manuales([("X", "dir", 4.0, -73.0, "nota")])
        assert (s["x"], s["y"]) == pytest.approx((5_000_000, 2_000_000))
        assert s["fuente"] == "manual"

    @pytest.mark.unit
    def test_tabla_bien_formada_y_en_bogota(self):
        assert len(U.SEDES_MANUALES) == 8
        for nombre, direccion, lat, lon, nota in U.SEDES_MANUALES:
            assert nombre and direccion and "aproximada" in nota
            assert 4.45 < lat < 4.85 and -74.25 < lon < -73.95, nombre


class TestCampusPot:
    @pytest.mark.unit
    def test_agrupa_predios_con_mismo_nombre_cercanos(self):
        fs = [campus("Universidad X", cuadrado(0, 0, 100)),
              campus("UNIVERSIDAD  X", cuadrado(200, 0, 100)),   # mismo nombre, a 200 m
              campus("Universidad X", cuadrado(5000, 0, 100)),   # mismo nombre, lejos: otra sede
              campus("Universidad Y", cuadrado(0, 0, 100)),      # otro nombre
              campus("Sin geometría", None)]
        sedes = U.campus_pot(fs)
        assert len(sedes) == 3
        x1 = next(s for s in sedes if s["nombre"] == "UNIVERSIDAD X" and s["x"] < 1000)
        assert x1["x"] == pytest.approx(150)  # centroide ponderado de los dos predios
        assert len(x1["geometrias"]) == 2
        assert all(s["fuente"] == "POT" for s in sedes)

    @pytest.mark.unit
    def test_predios_de_area_cero(self):
        degenerado = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]}
        sedes = U.campus_pot([campus("Z", degenerado), campus("Z", degenerado)])
        assert len(sedes) == 1

    @pytest.mark.unit
    def test_normalizar_nombre(self):
        assert U.normalizar_nombre("  Católica   de Colombia ") == "CATOLICA DE COLOMBIA"
        assert U.normalizar_nombre(None) == ""


class TestUnificar:
    @pytest.mark.unit
    def test_punto_dentro_de_campus_no_se_cuenta_dos_veces(self):
        c = U.campus_pot([campus("U", cuadrado(0, 0, 100))])
        snies = [{"nombre": "U", "x": 50, "y": 50, "fuente": "SNIES"},
                 {"nombre": "V", "x": 500, "y": 500, "fuente": "SNIES"}]
        manual = [{"nombre": "W", "x": 10, "y": 10, "fuente": "manual"}]
        sedes = U.unificar(snies, c, manual)
        assert sorted(s["nombre"] for s in sedes) == ["U", "V"]
        assert all(set(s) == {"nombre", "x", "y", "fuente"} for s in sedes)

    @pytest.mark.unit
    def test_construir_sedes_combina_las_tres_fuentes(self):
        sedes = U.construir_sedes([ies("A", 0, 0)], [campus("B", cuadrado(1000, 1000, 10))],
                                  [("C", "dir", 4.0, -73.0, "aproximada")])
        assert sorted(s["fuente"] for s in sedes) == ["POT", "SNIES", "manual"]


class TestCercania:
    @pytest.mark.unit
    def test_cuenta_y_distancia_minima(self):
        sedes = [{"x": 0, "y": 0}, {"x": 1500, "y": 0}, {"x": 0, "y": 2500}]
        assert U.cercania((0, 0), sedes) == (2, 0)
        assert U.cercania((0, 0), sedes, radio=100) == (1, 0)

    @pytest.mark.unit
    def test_radio_inclusivo(self):
        assert U.cercania((0, 0), [{"x": 2000, "y": 0}]) == (1, 2000)

    @pytest.mark.unit
    def test_sin_sedes(self):
        assert U.cercania((0, 0), []) == (0, None)

    @pytest.mark.unit
    def test_parametros(self):
        assert U.RADIO_M == 2000
        assert punto_en_poligono(5, 5, cuadrado(0, 0, 10))
