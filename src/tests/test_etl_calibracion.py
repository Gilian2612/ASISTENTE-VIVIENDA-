"""Tests de la calibración del arriendo con anuncios recogidos a mano."""
import csv
from datetime import date

import pytest

from ETL import calibracion as C

ZONAS = [
    {"codigo_upz": "99", "nombre": "CHAPINERO", "arriendo_avaluo": "1000000.0"},
    {"codigo_upz": "85", "nombre": "BOSA CENTRAL", "arriendo_avaluo": "500000.0"},
    {"codigo_upz": "60", "nombre": "PARQUE ENTRENUBES", "arriendo_avaluo": ""},
]


def zonas(n=10):
    """n UPZ con arriendo_avaluo de 1.000.000."""
    return [{"codigo_upz": str(i), "nombre": f"UPZ {i}", "arriendo_avaluo": "1000000"} for i in range(1, n + 1)]


def anuncio(upz="99", canon=1_500_000, area=60, fuente="metrocuadrado"):
    return {"fuente": fuente, "fecha": date(2026, 11, 1), "url": "", "codigo_upz": upz,
            "area_m2": area, "canon_cop": canon}


def fila(**cambios):
    base = {"fuente": "metrocuadrado", "fecha": "2026-11-01", "url": "https://ejemplo",
            "upz": "Chapinero", "area_m2": "60", "canon_cop": "1500000"}
    base.update(cambios)
    return base


def escribir(ruta, filas):
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=C.COLUMNAS_ANUNCIOS)
        w.writeheader()
        w.writerows(filas)


class TestResolverUpz:
    @pytest.mark.unit
    @pytest.mark.parametrize("valor,codigo", [
        ("99", "99"), ("UPZ99", "99"), ("upz 99", "99"), ("099", "99"),
        ("Chapinero", "99"), ("  chapinero ", "99"), ("Bosa Central", "85"),
        ("Bosa-Central", "85"), ("Inexistente", None), ("123", None), ("", None),
    ])
    def test_resolver(self, valor, codigo):
        assert C.resolver_upz(valor, ZONAS) == codigo


class TestNumero:
    @pytest.mark.unit
    @pytest.mark.parametrize("texto,valor", [
        ("2500000", 2_500_000), ("2.500.000", 2_500_000), ("2,500,000", 2_500_000),
        ("$ 1.800.000", 1_800_000), ("62,5", 62.5), ("62.5", 62.5), ("60", 60),
        ("1.200", 1200), ("1,200", 1200),
    ])
    def test_formatos(self, texto, valor):
        assert C._numero(texto) == valor


class TestValidarAnuncio:
    @pytest.mark.unit
    def test_valido(self):
        a = C.validar_anuncio(fila(fuente="Fincaraíz", canon_cop="$ 1.500.000"), ZONAS)
        assert a == {"fuente": "fincaraiz", "fecha": date(2026, 11, 1), "url": "https://ejemplo",
                     "codigo_upz": "99", "area_m2": 60.0, "canon_cop": 1_500_000.0}

    @pytest.mark.unit
    @pytest.mark.parametrize("cambios,mensaje", [
        ({"fuente": "ciencuadras"}, "no es metrocuadrado ni fincaraiz"),
        ({"fecha": "01/11/2026"}, "AAAA-MM-DD"),
        ({"area_m2": "grande"}, "deben ser números"),
        ({"area_m2": "5"}, "area_m2"),
        ({"canon_cop": "50000"}, "canon_cop"),
        ({"upz": "Narnia"}, "no existe"),
    ])
    def test_invalidos(self, cambios, mensaje):
        with pytest.raises(ValueError, match=mensaje):
            C.validar_anuncio(fila(**cambios), ZONAS)


class TestLeerAnuncios:
    @pytest.mark.unit
    def test_sin_archivo(self, tmp_path):
        assert C.leer_anuncios(tmp_path / "no.csv", ZONAS) == ([], [])

    @pytest.mark.unit
    def test_separa_validos_y_errores_e_ignora_filas_vacias(self, tmp_path):
        ruta = tmp_path / "a.csv"
        escribir(ruta, [fila(), {k: "" for k in C.COLUMNAS_ANUNCIOS}, fila(upz="Narnia")])
        validos, errores = C.leer_anuncios(ruta, ZONAS)
        assert len(validos) == 1
        assert errores == [(4, "UPZ 'Narnia' no existe (usa el código o el nombre de la UPZ)")]

    @pytest.mark.unit
    def test_plantilla_del_repo_es_valida(self):
        """data/calibracion_arriendos.csv tiene las columnas esperadas."""
        with C.RUTA_ANUNCIOS.open(encoding="utf-8") as fh:
            assert next(csv.reader(fh)) == C.COLUMNAS_ANUNCIOS


class TestCalcularFactor:
    @pytest.mark.unit
    def test_lleva_a_60m2_y_usa_la_mediana(self):
        # 3 anuncios en Chapinero (base 1 M): 1,5 M en 60 m²; 3 M en 120 m² (= 1,5 M en 60); 9 M atípico.
        anuncios = [anuncio(), anuncio(canon=3_000_000, area=120), anuncio(canon=9_000_000)]
        r = C.calcular_factor(anuncios, ZONAS, min_anuncios=1, min_upz=1)
        assert r["factor"] == 1.5  # la mediana ignora el atípico
        assert r["anuncios"] == 3 and r["upz"] == 1 and r["aplicado"]

    @pytest.mark.unit
    def test_por_fuente_y_cuartiles(self):
        anuncios = ([anuncio(upz=str(i), canon=1_200_000) for i in range(1, 6)] +
                    [anuncio(upz=str(i), canon=1_800_000, fuente="fincaraiz") for i in range(1, 6)])
        r = C.calcular_factor(anuncios, zonas(), min_anuncios=10, min_upz=5)
        assert r["por_fuente"] == {"fincaraiz": {"anuncios": 5, "factor": 1.8},
                                   "metrocuadrado": {"anuncios": 5, "factor": 1.2}}
        assert r["factor"] == 1.5 and r["aplicado"]
        assert r["p25"] <= r["factor"] <= r["p75"]

    @pytest.mark.unit
    def test_ignora_upz_sin_arriendo_base(self):
        r = C.calcular_factor([anuncio(upz="60")], ZONAS, min_anuncios=1, min_upz=1)
        assert r["anuncios"] == 0 and not r["aplicado"]

    @pytest.mark.unit
    def test_pocos_anuncios_no_aplica(self):
        r = C.calcular_factor([anuncio()] * 5, ZONAS)
        assert not r["aplicado"]
        assert "5 anuncios (mínimo 20)" in r["motivo"]
        assert r["factor"] == 1.5  # se informa aunque no se aplique

    @pytest.mark.unit
    def test_pocas_upz_no_aplica(self):
        r = C.calcular_factor([anuncio()] * 25, ZONAS)
        assert not r["aplicado"] and "1 UPZ (mínimo 5)" in r["motivo"]

    @pytest.mark.unit
    def test_sin_anuncios(self):
        r = C.calcular_factor([], ZONAS)
        assert (r["factor"], r["aplicado"], r["anuncios"]) == (1.0, False, 0)
        assert "p25" not in r


class TestAplicarYCalibrar:
    @pytest.mark.unit
    def test_aplica_el_factor_y_redondea(self):
        filas = [dict(z) for z in ZONAS]
        C.aplicar(filas, {"aplicado": True, "factor": 1.5})
        assert [f["arriendo_estimado"] for f in filas] == [1_500_000, 750_000, ""]

    @pytest.mark.unit
    def test_no_aplicado_deja_el_valor_base(self):
        filas = [dict(z) for z in ZONAS]
        C.aplicar(filas, {"aplicado": False, "factor": 1.5})
        assert filas[0]["arriendo_estimado"] == 1_000_000

    @pytest.mark.unit
    def test_calibrar_de_punta_a_punta(self, tmp_path):
        ruta = tmp_path / "a.csv"
        filas = zonas()
        escribir(ruta, [fila(upz=str(i % 10 + 1), canon_cop="1600000") for i in range(20)] + [fila(upz="Narnia")])
        resultado, errores = C.calibrar(filas, ruta)
        assert resultado["aplicado"] and resultado["factor"] == 1.6
        assert filas[0]["arriendo_estimado"] == 1_600_000
        assert len(errores) == 1

    @pytest.mark.unit
    def test_reporte(self, tmp_path):
        ruta = tmp_path / "a.csv"
        escribir(ruta, [fila(upz=str(i % 10 + 1)) for i in range(20)] + [fila(fuente="otra")])
        texto = C.reporte(*C.calibrar(zonas(), ruta))
        assert "Anuncios usados: 20 en 10 UPZ" in texto
        assert "metrocuadrado: 20 anuncios, factor 1.5" in texto
        assert "✓ Calibración aplicada" in texto and "descartado (línea 22)" in texto

    @pytest.mark.unit
    def test_reporte_no_aplicado(self):
        texto = C.reporte(C.calcular_factor([], ZONAS), [])
        assert "✗ Calibración NO aplicada" in texto
