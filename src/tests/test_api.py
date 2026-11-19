"""Tests de la API: lógica de rutas (sin red) y servidor HTTP en localhost.

El servidor se levanta en 127.0.0.1 con un puerto libre; no se contacta a
ningún servicio externo, así que corre en CI.
"""
import json
import threading
import urllib.error
import urllib.request

import pytest

from API import rutas, servidor
from API.rutas import ErrorParametros
from KNN import knn

PERFIL = {
    "transporte": "5", "seguridad": "4", "precio": "3",
    "universidades": "5", "verdes": "2", "presupuesto": "1800000",
}


def perfil(**cambios):
    return {**PERFIL, **cambios}


# ------------------------------------------------------------ leer_perfil
class TestLeerPerfil:
    """Validación de parámetros de /api/recomendar."""

    @pytest.mark.unit
    def test_perfil_valido(self):
        assert rutas.leer_perfil(perfil()) == ([5, 4, 3, 5, 2], 1_800_000, 3, None)

    @pytest.mark.unit
    @pytest.mark.parametrize("valor,esperado", [("si", True), ("no", False), ("", None), (" SI ", True)])
    def test_industrial(self, valor, esperado):
        assert rutas.leer_perfil(perfil(industrial=valor))[3] is esperado

    @pytest.mark.unit
    def test_k_personalizado(self):
        assert rutas.leer_perfil(perfil(k="5"))[2] == 5

    @pytest.mark.unit
    @pytest.mark.parametrize("cambios,mensaje", [
        ({"transporte": ""}, "Falta el parámetro 'transporte'"),
        ({"verdes": "0"}, "entre 1 y 5"),
        ({"precio": "6"}, "entre 1 y 5"),
        ({"seguridad": "alto"}, "número entero"),
        ({"presupuesto": "-1"}, "'presupuesto' debe estar entre"),
        ({"presupuesto": "2.5e6"}, "número entero"),
        ({"k": "0"}, "'k' debe estar entre"),
        ({"industrial": "quizas"}, "'industrial'"),
    ])
    def test_parametros_invalidos(self, cambios, mensaje):
        with pytest.raises(ErrorParametros, match=mensaje):
            rutas.leer_perfil(perfil(**cambios))

    @pytest.mark.unit
    def test_falta_presupuesto(self):
        params = perfil()
        del params["presupuesto"]
        with pytest.raises(ErrorParametros, match="presupuesto"):
            rutas.leer_perfil(params)

    @pytest.mark.unit
    def test_k_no_supera_el_numero_de_zonas(self):
        with pytest.raises(ErrorParametros):
            rutas.leer_perfil(perfil(k=str(len(knn.ZONAS) + 1)))


# ------------------------------------------------------------------ zonas
class TestZonas:
    @pytest.mark.unit
    def test_todas_las_zonas_con_sus_campos(self):
        datos = rutas.zonas()
        assert datos["variables"] == knn.VARIABLES
        assert datos["provisionales"] == knn.VARIABLES_PROVISIONALES
        assert len(datos["zonas"]) == len(knn.ZONAS)
        for z in datos["zonas"]:
            assert set(z) == {"nombre", "codigo_upz", "localidad", "tipo", "arriendo", "norm"}
            assert set(z["norm"]) == set(knn.VARIABLES)

    @pytest.mark.unit
    def test_valores_coinciden_con_el_knn(self):
        z = next(z for z in rutas.zonas()["zonas"] if z["nombre"] == "Chapinero")
        vector, arriendo = knn.ZONAS["Chapinero"]
        assert z["arriendo"] == arriendo
        assert [z["norm"][v] for v in knn.VARIABLES] == vector
        assert z["localidad"] == "Chapinero"  # en formato título

    @pytest.mark.unit
    def test_zona_sin_metadatos_usa_valores_por_defecto(self, monkeypatch):
        monkeypatch.setattr(knn, "ZONAS", {"X": ([0.5] * 5, 1)})
        monkeypatch.setattr(knn, "METADATOS", {})
        (z,) = rutas.zonas()["zonas"]
        assert (z["codigo_upz"], z["localidad"], z["tipo"]) == ("", "", "residencial")


# ------------------------------------------------------------- recomendar
class TestRecomendar:
    @pytest.mark.unit
    def test_mismo_resultado_que_el_knn(self):
        esperado = knn.recomendar([5, 4, 3, 5, 2], 1_800_000, k=3)
        obtenido = rutas.recomendar(perfil())["resultados"]
        assert [(r["nombre"], r["similitud"]) for r in obtenido] == esperado
        for r in obtenido:
            assert r["codigo_upz"] == knn.METADATOS[r["nombre"]]["codigo_upz"]

    @pytest.mark.unit
    def test_filtro_industrial(self):
        n = str(len(knn.ZONAS))
        solo = rutas.recomendar(perfil(industrial="si", k=n, presupuesto="10000000000"))["resultados"]
        sin = rutas.recomendar(perfil(industrial="no", k=n, presupuesto="10000000000"))["resultados"]
        assert solo and all(knn.METADATOS[r["nombre"]]["tipo"] == "industrial" for r in solo)
        assert all(knn.METADATOS[r["nombre"]]["tipo"] != "industrial" for r in sin)

    @pytest.mark.unit
    def test_presupuesto_insuficiente_lista_vacia(self):
        assert rutas.recomendar(perfil(presupuesto="0")) == {"resultados": []}


# --------------------------------------------------------------- servidor
@pytest.fixture(scope="module")
def url_base():
    servidor.Manejador.silencioso = True
    srv = servidor.crear_servidor(puerto=0)  # puerto libre
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


class TestServidor:
    @pytest.mark.unit
    def test_sirve_el_front(self, url_base):
        estado, _, cuerpo = get(url_base + "/")
        assert estado == 200
        assert b"/api/zonas" in cuerpo  # el front consume la API

    @pytest.mark.unit
    def test_api_zonas(self, url_base):
        estado, cabeceras, cuerpo = get(url_base + "/api/zonas")
        assert estado == 200
        assert cabeceras["Content-Type"].startswith("application/json")
        assert len(json.loads(cuerpo)["zonas"]) == len(knn.ZONAS)

    @pytest.mark.unit
    def test_api_recomendar(self, url_base):
        query = urllib.parse.urlencode(perfil(industrial="no"))
        estado, _, cuerpo = get(f"{url_base}/api/recomendar?{query}")
        assert estado == 200
        assert len(json.loads(cuerpo)["resultados"]) == 3

    @pytest.mark.unit
    def test_api_parametros_invalidos_400(self, url_base):
        estado, _, cuerpo = get(url_base + "/api/recomendar?transporte=9")
        assert estado == 400
        assert "error" in json.loads(cuerpo)

    @pytest.mark.unit
    def test_api_ruta_desconocida_404(self, url_base):
        estado, _, cuerpo = get(url_base + "/api/no-existe")
        assert estado == 404
        assert "no-existe" in json.loads(cuerpo)["error"]

    @pytest.mark.unit
    def test_no_sirve_archivos_fuera_del_front(self, url_base):
        estado, _, cuerpo = get(url_base + "/../KNN/knn.py")
        assert b"PROVISIONAL_POR_LOCALIDAD" not in cuerpo
