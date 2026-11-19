"""Tests del cliente ArcGIS con HTTP simulado (sin red)."""
import io
import json
import urllib.error
import urllib.parse

import pytest

from ETL import arcgis, fuentes
from ETL.arcgis import ErrorArcGIS

URL_CAPA = "https://ejemplo.test/arcgis/rest/services/x/MapServer/0"


class ServidorFalso:
    """Reemplaza `urlopen`: devuelve respuestas en orden y registra las peticiones."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.peticiones = []

    def __call__(self, peticion, timeout=None):
        self.peticiones.append(peticion)
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        if isinstance(r, bytes):
            return io.BytesIO(r)
        return io.BytesIO(json.dumps(r).encode())

    def params(self, i):
        query = urllib.parse.urlparse(self.peticiones[i].full_url).query
        return dict(urllib.parse.parse_qsl(query))


@pytest.fixture
def servidor(monkeypatch):
    def instalar(*respuestas):
        s = ServidorFalso(respuestas)
        monkeypatch.setattr(arcgis.urllib.request, "urlopen", s)
        return s
    monkeypatch.setattr(arcgis.time, "sleep", lambda _s: None)
    return instalar


def features(n):
    return [{"type": "Feature", "properties": {"id": i}, "geometry": None} for i in range(n)]


class TestGetJson:
    @pytest.mark.unit
    def test_devuelve_json_y_envia_user_agent(self, servidor):
        s = servidor({"ok": 1})
        assert arcgis.get_json(URL_CAPA, {"f": "json"}) == {"ok": 1}
        assert s.peticiones[0].get_header("User-agent") == arcgis.USER_AGENT
        assert s.params(0) == {"f": "json"}

    @pytest.mark.unit
    def test_reintenta_fallos_de_red(self, servidor):
        s = servidor(urllib.error.URLError("caido"), TimeoutError(), {"ok": 1})
        assert arcgis.get_json(URL_CAPA, {}) == {"ok": 1}
        assert len(s.peticiones) == 3

    @pytest.mark.unit
    def test_reintenta_json_invalido(self, servidor):
        servidor(b"<html>error</html>", {"ok": 1})
        assert arcgis.get_json(URL_CAPA, {}) == {"ok": 1}

    @pytest.mark.unit
    def test_falla_tras_agotar_reintentos(self, servidor):
        servidor(*[urllib.error.URLError("caido")] * 3)
        with pytest.raises(ErrorArcGIS, match="3 intentos"):
            arcgis.get_json(URL_CAPA, {})

    @pytest.mark.unit
    def test_error_del_servicio_no_se_reintenta(self, servidor):
        s = servidor({"error": {"code": 400, "message": "Invalid query"}}, {"ok": 1})
        with pytest.raises(ErrorArcGIS, match="Invalid query"):
            arcgis.get_json(URL_CAPA, {})
        assert len(s.peticiones) == 1


class TestContar:
    @pytest.mark.unit
    def test_contar(self, servidor):
        s = servidor({"count": 112})
        assert arcgis.contar(URL_CAPA) == 112
        assert s.params(0)["returnCountOnly"] == "true"
        assert s.peticiones[0].full_url.startswith(f"{URL_CAPA}/query?")


class TestConsultar:
    @pytest.mark.unit
    def test_una_pagina(self, servidor):
        s = servidor({"features": features(3)})
        assert len(arcgis.consultar(URL_CAPA, ("A", "B"), tam_pagina=10)) == 3
        p = s.params(0)
        assert p["outFields"] == "A,B"
        assert p["outSR"] == str(arcgis.SR_METROS)
        assert p["f"] == "geojson"
        assert p["resultOffset"] == "0"

    @pytest.mark.unit
    def test_pagina_hasta_agotar(self, servidor):
        s = servidor({"features": features(2)}, {"features": features(2)}, {"features": features(1)})
        assert len(arcgis.consultar(URL_CAPA, tam_pagina=2)) == 5
        assert [s.params(i)["resultOffset"] for i in range(3)] == ["0", "2", "4"]

    @pytest.mark.unit
    def test_pagina_completa_seguida_de_vacia(self, servidor):
        s = servidor({"features": features(2)}, {"features": []})
        assert len(arcgis.consultar(URL_CAPA, tam_pagina=2)) == 2
        assert len(s.peticiones) == 2

    @pytest.mark.unit
    def test_sigue_si_el_servidor_corta_antes_de_tam_pagina(self, servidor):
        # Si el servidor devuelve menos que lo pedido pero avisa que hay más
        # (exceededTransferLimit), se debe seguir paginando.
        servidor(
            {"features": features(2), "properties": {"exceededTransferLimit": True}},
            {"features": features(2), "exceededTransferLimit": True},
            {"features": features(1)},
        )
        assert len(arcgis.consultar(URL_CAPA, tam_pagina=10)) == 5


class TestFuentes:
    """Las capas configuradas apuntan al servidor oficial y tienen campos definidos."""

    @pytest.mark.unit
    def test_capas_en_servidor_oficial(self):
        for nombre, url in fuentes.CAPAS.items():
            assert url.startswith(arcgis.BASE), nombre
            assert set(fuentes.CAMPOS[nombre]), nombre

    @pytest.mark.unit
    def test_descargar_todo_usa_cada_capa(self, monkeypatch):
        llamadas = []
        monkeypatch.setattr(
            arcgis, "consultar", lambda url, campos, **kw: llamadas.append(url) or [url]
        )
        capas = fuentes.descargar_todo()
        assert set(capas) == set(fuentes.CAPAS)
        assert sorted(llamadas) == sorted(fuentes.CAPAS.values())
