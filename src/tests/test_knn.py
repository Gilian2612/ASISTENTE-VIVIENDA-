import csv
import math

import pytest

from KNN import knn
from KNN.knn import (
    METADATOS,
    PROVISIONAL_POR_LOCALIDAD,
    VARIABLES,
    ZONAS,
    cargar_zonas,
    cumple_preferencia_industrial,
    distancia,
    pesos_desde_importancia,
    recomendar,
)

PERFIL_ESTUDIANTE = [5, 4, 3, 5, 2]
PRESUPUESTO_ALTO = 10_000_000

# Datos fijos de ejemplo para probar el ALGORITMO sin depender del dataset
# real (que cambia cada vez que se regenera con el ETL).
ZONAS_EJEMPLO = {
    "Chapinero":      ([0.90, 0.60, 0.25, 0.95, 0.60], 2_200_000),
    "Teusaquillo":    ([0.85, 0.70, 0.45, 0.90, 0.75], 1_800_000),
    "Usaquén":        ([0.70, 0.80, 0.30, 0.40, 0.85], 2_400_000),
    "Suba":           ([0.60, 0.55, 0.60, 0.35, 0.70], 1_400_000),
    "Kennedy":        ([0.75, 0.40, 0.80, 0.30, 0.45], 1_000_000),
    "Fontibón":       ([0.80, 0.60, 0.65, 0.40, 0.50], 1_300_000),
    "Engativá":       ([0.70, 0.50, 0.70, 0.45, 0.55], 1_200_000),
    "Bosa":           ([0.50, 0.30, 0.90, 0.15, 0.35], 800_000),
    "Barrios Unidos": ([0.80, 0.65, 0.55, 0.60, 0.60], 1_500_000),
    "Santa Fe":       ([0.85, 0.35, 0.60, 0.85, 0.55], 1_300_000),
}


# ---------------------------------------------------------------- datos
class TestDatosZonas:
    """Valida el dataset REAL cargado (`data/zonas.csv` + datos provisionales).

    No prueba lógica, sino que el dataset esté bien formado: si alguien
    regenera el CSV o cambia los datos provisionales y rompe el formato, estos
    tests avisan. Se va a testear:
    - que haya al menos 20 zonas (objetivo del proyecto),
    - que cada zona tenga un valor por variable,
    - que los valores estén normalizados en [0, 1],
    - que los arriendos sean positivos,
    - que cada zona tenga metadatos (localidad y tipo).
    """

    @pytest.mark.unit
    def test_al_menos_20_zonas(self):
        """El objetivo cuantitativo del proyecto: >= 20 zonas."""
        assert len(ZONAS) >= 20

    @pytest.mark.unit
    def test_cada_zona_tiene_metadatos(self):
        """Toda zona tiene código UPZ, localidad y un tipo válido."""
        assert set(METADATOS) == set(ZONAS)
        for nombre, m in METADATOS.items():
            assert m["codigo_upz"] and m["localidad"], nombre
            assert m["tipo"] in {"residencial", "industrial", "dotacional"}, nombre

    @pytest.mark.unit
    def test_hay_zonas_industriales_marcadas(self):
        """Las UPZ industriales no se excluyen del dataset: se marcan."""
        assert any(m["tipo"] == "industrial" for m in METADATOS.values())

    @pytest.mark.unit
    def test_provisional_cubre_todas_las_localidades_del_csv(self):
        """Ninguna UPZ se pierde por falta de datos provisionales de su localidad."""
        with knn.RUTA_ZONAS.open(encoding="utf-8") as fh:
            localidades = {f["localidad"] for f in csv.DictReader(fh)}
        assert localidades <= set(PROVISIONAL_POR_LOCALIDAD)

    @pytest.mark.unit
    def test_cada_zona_tiene_un_valor_por_variable(self):
        """El vector de cada zona tiene tantos valores como `VARIABLES` (5)."""
        for nombre, (vector, _) in ZONAS.items():
            assert len(vector) == len(VARIABLES), nombre

    @pytest.mark.unit
    def test_variables_normalizadas_entre_0_y_1(self):
        """Todos los valores de todas las zonas están entre 0.0 y 1.0."""
        for nombre, (vector, _) in ZONAS.items():
            assert all(0.0 <= x <= 1.0 for x in vector), nombre

    @pytest.mark.unit
    def test_arriendos_positivos(self):
        """El arriendo promedio (COP) de cada zona es mayor que cero."""
        assert all(arriendo > 0 for _, arriendo in ZONAS.values())


# ------------------------------------------------ pesos_desde_importancia
class TestPesos:
    """Prueba `pesos_desde_importancia`, que convierte importancias 1-5 en pesos.

    Se va a testear que los pesos resultantes sumen 1, que sean proporcionales
    a la importancia dada, que importancias iguales den pesos iguales y que el
    caso degenerado (todo en 0) falle de forma explícita.
    """

    @pytest.mark.unit
    def test_suman_uno(self):
        """Los pesos de un perfil real suman 1 (normalización correcta)."""
        assert sum(pesos_desde_importancia(PERFIL_ESTUDIANTE)) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_son_proporcionales_a_la_importancia(self):
        """Importancias [1, 3] dan pesos [0.25, 0.75]: 3 pesa el triple que 1."""
        pesos = pesos_desde_importancia([1, 3])
        assert pesos == pytest.approx([0.25, 0.75])

    @pytest.mark.unit
    def test_importancias_iguales_dan_pesos_iguales(self):
        """Cinco importancias iguales reparten el peso por igual (0.2 cada una)."""
        assert pesos_desde_importancia([3, 3, 3, 3, 3]) == pytest.approx([0.2] * 5)

    @pytest.mark.unit
    def test_todas_cero_lanza_division_por_cero(self):
        """Si todas las importancias son 0, la suma es 0 y lanza ZeroDivisionError."""
        with pytest.raises(ZeroDivisionError):
            pesos_desde_importancia([0, 0, 0])


# ------------------------------------------------------------- distancia
class TestDistancia:
    """Prueba `distancia`, la distancia euclidiana ponderada entre dos vectores.

    Se va a testear las propiedades matemáticas de una distancia (cero con
    vectores iguales, simetría), un valor calculado a mano, el efecto de los
    pesos (un peso 0 ignora la variable; un peso mayor aumenta la distancia) y
    el valor máximo posible.
    """

    @pytest.mark.unit
    def test_vectores_iguales_distancia_cero(self):
        """La distancia de un vector consigo mismo es exactamente 0."""
        assert distancia([0.5, 0.2], [0.5, 0.2], [0.5, 0.5]) == 0.0

    @pytest.mark.unit
    def test_es_simetrica(self):
        """distancia(a, b) es igual a distancia(b, a)."""
        a, b, w = [0.1, 0.9], [0.7, 0.3], [0.4, 0.6]
        assert distancia(a, b, w) == pytest.approx(distancia(b, a, w))

    @pytest.mark.unit
    def test_valor_conocido(self):
        """Caso calculado a mano: sqrt(0.5*1² + 0.5*1²) = 1."""
        # sqrt(0.5*1^2 + 0.5*1^2) = 1
        assert distancia([0, 0], [1, 1], [0.5, 0.5]) == pytest.approx(1.0)

    @pytest.mark.unit
    def test_peso_cero_ignora_la_variable(self):
        """Una variable con peso 0 no aporta aunque sus valores sean distintos."""
        assert distancia([0, 0], [1, 0], [0.0, 1.0]) == 0.0

    @pytest.mark.unit
    def test_pesos_mayores_aumentan_la_distancia(self):
        """Con la misma diferencia, un peso de 0.9 da más distancia que uno de 0.1."""
        a, b = [0.0], [1.0]
        assert distancia(a, b, [0.9]) > distancia(a, b, [0.1])

    @pytest.mark.unit
    def test_maxima_distancia_es_raiz_de_suma_de_pesos(self):
        """Entre todo-0 y todo-1 la distancia es sqrt(Σ pesos); `recomendar` la usa para normalizar."""
        pesos = pesos_desde_importancia(PERFIL_ESTUDIANTE)
        assert distancia([0] * 5, [1] * 5, pesos) == pytest.approx(math.sqrt(sum(pesos)))


# ------------------------------------------------------------- recomendar
class TestRecomendar:
    """Prueba `recomendar`, la función principal que devuelve las k mejores zonas.

    Es la clase más grande porque `recomendar` combina varias reglas. Se va a
    testear, en grupos:
    - tamaño del resultado (k por defecto, k grande, k = 0),
    - formato y orden de lo devuelto (nombre, similitud 0-100, descendente, sin repetidos),
    - el filtro duro por presupuesto (incluye bordes: igual, insuficiente, 0 o negativo),
    - el efecto de las importancias (perfil estudiante, subir precio o universidades,
      escalar importancias no cambia nada),
    - los extremos de similitud (100 % y 0 %) usando datos falsos con `monkeypatch`,
    - errores y determinismo.

    Usa `ZONAS_EJEMPLO` (fixture autouse) para que los resultados esperados
    no cambien al regenerar el dataset real.
    """

    @pytest.fixture(autouse=True)
    def datos_de_ejemplo(self, monkeypatch):
        monkeypatch.setattr(knn, "ZONAS", ZONAS_EJEMPLO)
        monkeypatch.setattr(knn, "METADATOS", {})

    @pytest.mark.unit
    def test_devuelve_k_resultados_por_defecto_3(self):
        """Sin pasar `k`, devuelve 3 zonas."""
        assert len(recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO)) == 3

    @pytest.mark.unit
    @pytest.mark.parametrize("k", [1, 2, 5, 10])
    def test_respeta_k(self, k):
        """Con k = 1, 2, 5 y 10 devuelve exactamente esa cantidad (4 casos)."""
        assert len(recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=k)) == k

    @pytest.mark.unit
    def test_k_mayor_que_zonas_devuelve_todas(self):
        """Con k = 100 y solo 10 zonas, devuelve las 10 sin error."""
        assert len(recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=100)) == len(ZONAS_EJEMPLO)

    @pytest.mark.unit
    def test_k_cero_devuelve_vacio(self):
        """Con k = 0 devuelve una lista vacía."""
        assert recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=0) == []

    @pytest.mark.unit
    def test_formato_nombre_y_similitud(self):
        """Cada resultado es (nombre de zona existente, similitud float entre 0 y 100)."""
        for nombre, sim in recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=10):
            assert nombre in ZONAS_EJEMPLO
            assert isinstance(sim, float)
            assert 0.0 <= sim <= 100.0

    @pytest.mark.unit
    def test_ordenado_por_similitud_descendente(self):
        """La primera zona es la más parecida: las similitudes bajan de mayor a menor."""
        sims = [s for _, s in recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=10)]
        assert sims == sorted(sims, reverse=True)

    @pytest.mark.unit
    def test_no_repite_zonas(self):
        """Ninguna zona aparece dos veces en el resultado."""
        nombres = [n for n, _ in recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=10)]
        assert len(nombres) == len(set(nombres))

    @pytest.mark.unit
    @pytest.mark.parametrize("presupuesto", [900_000, 1_300_000, 1_800_000, 2_400_000])
    def test_filtro_de_presupuesto(self, presupuesto):
        """Con 4 presupuestos distintos, ninguna zona recomendada cuesta más que el presupuesto."""
        for nombre, _ in recomendar(PERFIL_ESTUDIANTE, presupuesto, k=10):
            assert ZONAS_EJEMPLO[nombre][1] <= presupuesto

    @pytest.mark.unit
    def test_presupuesto_igual_al_arriendo_incluye_la_zona(self):
        """Borde: con presupuesto = 800.000 (arriendo de Bosa) solo queda Bosa; el límite es inclusivo."""
        nombres = [n for n, _ in recomendar(PERFIL_ESTUDIANTE, 800_000, k=10)]
        assert nombres == ["Bosa"]

    @pytest.mark.unit
    def test_presupuesto_insuficiente_devuelve_vacio(self):
        """Con 100.000 COP no alcanza ninguna zona: lista vacía."""
        assert recomendar(PERFIL_ESTUDIANTE, 100_000) == []

    @pytest.mark.unit
    def test_presupuesto_cero_o_negativo_devuelve_vacio(self):
        """Presupuesto 0 o -1 no lanza error: devuelve lista vacía."""
        assert recomendar(PERFIL_ESTUDIANTE, 0) == []
        assert recomendar(PERFIL_ESTUDIANTE, -1) == []

    @pytest.mark.unit
    def test_perfil_estudiante_sin_restriccion_recomienda_zonas_universitarias(self):
        """Un perfil que prioriza transporte y universidades pone primero a Chapinero o Teusaquillo."""
        top = [n for n, _ in recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=3)]
        assert top[0] in {"Chapinero", "Teusaquillo"}

    @staticmethod
    def _sim(zona, importancias):
        """Ayudante (no es un test): similitud de una zona concreta para unas importancias."""
        return dict(recomendar(importancias, PRESUPUESTO_ALTO, k=10))[zona]

    @pytest.mark.unit
    def test_subir_importancia_de_precio_acerca_la_zona_barata_a_la_cara(self):
        """Al subir la importancia del precio de 1 a 5, Bosa (barata) mejora frente a Chapinero (cara)."""
        # Bosa es la más barata (precio=0.90); Chapinero de las más caras (0.25)
        brecha_baja = self._sim("Bosa", [3, 3, 1, 3, 3]) - self._sim("Chapinero", [3, 3, 1, 3, 3])
        brecha_alta = self._sim("Bosa", [3, 3, 5, 3, 3]) - self._sim("Chapinero", [3, 3, 5, 3, 3])
        assert brecha_alta > brecha_baja

    @pytest.mark.unit
    def test_subir_importancia_de_universidades_favorece_a_chapinero_sobre_bosa(self):
        """Al subir la importancia de universidades de 1 a 5, Chapinero gana ventaja sobre Bosa."""
        brecha_baja = self._sim("Chapinero", [3, 3, 3, 1, 3]) - self._sim("Bosa", [3, 3, 3, 1, 3])
        brecha_alta = self._sim("Chapinero", [3, 3, 3, 5, 3]) - self._sim("Bosa", [3, 3, 3, 5, 3])
        assert brecha_alta > brecha_baja

    @pytest.mark.unit
    def test_escalar_importancias_no_cambia_el_resultado(self):
        """[1,2,3,4,5] y [2,4,6,8,10] son el mismo perfil (solo importa la proporción): mismo resultado."""
        base = recomendar([1, 2, 3, 4, 5], PRESUPUESTO_ALTO, k=10)
        escalado = recomendar([2, 4, 6, 8, 10], PRESUPUESTO_ALTO, k=10)
        assert base == escalado

    @pytest.mark.unit
    def test_zona_perfecta_tendria_100_por_ciento(self, monkeypatch):
        """Con una zona falsa de todo 1.0 (el perfil ideal), la similitud es exactamente 100.0."""
        monkeypatch.setattr(knn, "ZONAS", {"Ideal": ([1.0] * 5, 1)})
        assert recomendar(PERFIL_ESTUDIANTE, 10, k=1) == [("Ideal", 100.0)]

    @pytest.mark.unit
    def test_zona_peor_posible_tendria_0_por_ciento(self, monkeypatch):
        """Con una zona falsa de todo 0.0 (lo más lejos del ideal), la similitud es exactamente 0.0."""
        monkeypatch.setattr(knn, "ZONAS", {"Peor": ([0.0] * 5, 1)})
        assert recomendar(PERFIL_ESTUDIANTE, 10, k=1) == [("Peor", 0.0)]

    @pytest.mark.unit
    def test_importancias_todas_cero_lanza_error(self):
        """Con importancias [0,0,0,0,0] el error de `pesos_desde_importancia` se propaga hasta `recomendar`."""
        with pytest.raises(ZeroDivisionError):
            recomendar([0, 0, 0, 0, 0], PRESUPUESTO_ALTO)

    @pytest.mark.unit
    def test_resultado_determinista(self):
        """Llamar dos veces con la misma entrada da exactamente el mismo resultado."""
        a = recomendar(PERFIL_ESTUDIANTE, 1_800_000)
        b = recomendar(PERFIL_ESTUDIANTE, 1_800_000)
        assert a == b


# ------------------------------------------------------------ cargar_zonas
def escribir_csv_zonas(ruta, filas):
    columnas = ["codigo_upz", "nombre", "localidad", "tipo", "transporte", "verdes"]
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)


def fila(codigo, nombre, localidad, tipo="residencial", transporte=0.5, verdes=0.5):
    return {"codigo_upz": codigo, "nombre": nombre, "localidad": localidad,
            "tipo": tipo, "transporte": transporte, "verdes": verdes}


PROVISIONAL_PRUEBA = {
    "CARA":   (0.8, 0.9, 3_000_000),
    "BARATA": (0.2, 0.1, 1_000_000),
}


class TestCargarZonas:
    """Prueba `cargar_zonas`: combina el CSV real con los datos provisionales."""

    @pytest.mark.unit
    def test_combina_csv_y_provisional(self, tmp_path):
        """transporte/verdes vienen del CSV; seguridad/universidades/arriendo, del provisional."""
        ruta = tmp_path / "zonas.csv"
        escribir_csv_zonas(ruta, [fila("1", "ZONA UNO", "CARA", transporte=0.7, verdes=0.3)])
        zonas, meta = cargar_zonas(ruta, PROVISIONAL_PRUEBA)
        vector, arriendo = zonas["Zona Uno"]
        assert vector[0] == 0.7 and vector[4] == 0.3
        assert vector[1] == 0.8 and vector[3] == 0.9
        assert arriendo == 3_000_000
        assert meta["Zona Uno"] == {"codigo_upz": "1", "localidad": "CARA", "tipo": "residencial"}

    @pytest.mark.unit
    def test_precio_invierte_el_arriendo(self, tmp_path):
        """La zona más barata tiene precio 1 y la más cara precio 0."""
        ruta = tmp_path / "zonas.csv"
        escribir_csv_zonas(ruta, [fila("1", "A", "CARA"), fila("2", "B", "BARATA")])
        zonas, _ = cargar_zonas(ruta, PROVISIONAL_PRUEBA)
        assert zonas["A"][0][2] == 0.0
        assert zonas["B"][0][2] == 1.0

    @pytest.mark.unit
    def test_un_solo_arriendo_no_divide_por_cero(self, tmp_path):
        """Si todas las zonas tienen el mismo arriendo, precio = 1 para todas."""
        ruta = tmp_path / "zonas.csv"
        escribir_csv_zonas(ruta, [fila("1", "A", "CARA"), fila("2", "B", "CARA")])
        zonas, _ = cargar_zonas(ruta, PROVISIONAL_PRUEBA)
        assert {v[0][2] for v in zonas.values()} == {1.0}

    @pytest.mark.unit
    def test_omite_localidad_sin_datos_provisionales(self, tmp_path):
        """Una UPZ sin localidad o con localidad desconocida no se carga."""
        ruta = tmp_path / "zonas.csv"
        escribir_csv_zonas(ruta, [fila("1", "A", "CARA"), fila("2", "B", ""), fila("3", "C", "OTRA")])
        zonas, _ = cargar_zonas(ruta, PROVISIONAL_PRUEBA)
        assert list(zonas) == ["A"]

    @pytest.mark.unit
    def test_csv_vacio_da_dataset_vacio(self, tmp_path):
        ruta = tmp_path / "zonas.csv"
        escribir_csv_zonas(ruta, [])
        assert cargar_zonas(ruta, PROVISIONAL_PRUEBA) == ({}, {})

    @pytest.mark.unit
    def test_sin_csv_explica_como_generarlo(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="ETL.construir_zonas"):
            cargar_zonas(tmp_path / "no_existe.csv")

    @pytest.mark.unit
    def test_usa_datos_provisionales_por_defecto(self, tmp_path):
        ruta = tmp_path / "zonas.csv"
        escribir_csv_zonas(ruta, [fila("99", "CHAPINERO", "CHAPINERO")])
        zonas, _ = cargar_zonas(ruta)
        assert zonas["Chapinero"][1] == PROVISIONAL_POR_LOCALIDAD["CHAPINERO"][2]


# ------------------------------------------------- preferencia industrial
class TestPreferenciaIndustrial:
    """La persona responde: ¿buscas zona industrial? sí (True) / no (False) / sin preferencia (None)."""

    ZONAS_TIPOS = {
        "Fabrica": ([0.9] * 5, 1_000_000),
        "Barrio": ([0.5] * 5, 1_000_000),
        "Parque": ([0.4] * 5, 1_000_000),
    }
    META_TIPOS = {
        "Fabrica": {"tipo": "industrial"},
        "Barrio": {"tipo": "residencial"},
        "Parque": {"tipo": "dotacional"},
    }

    @pytest.fixture(autouse=True)
    def datos(self, monkeypatch):
        monkeypatch.setattr(knn, "ZONAS", self.ZONAS_TIPOS)
        monkeypatch.setattr(knn, "METADATOS", self.META_TIPOS)

    def _nombres(self, industrial):
        return [n for n, _ in recomendar([3] * 5, PRESUPUESTO_ALTO, k=10, industrial=industrial)]

    @pytest.mark.unit
    def test_sin_preferencia_incluye_todas(self):
        assert self._nombres(None) == ["Fabrica", "Barrio", "Parque"]

    @pytest.mark.unit
    def test_si_solo_industriales(self):
        assert self._nombres(True) == ["Fabrica"]

    @pytest.mark.unit
    def test_no_excluye_industriales_pero_no_dotacionales(self):
        assert self._nombres(False) == ["Barrio", "Parque"]

    @pytest.mark.unit
    def test_por_defecto_es_sin_preferencia(self):
        assert [n for n, _ in recomendar([3] * 5, PRESUPUESTO_ALTO, k=10)] == self._nombres(None)

    @pytest.mark.unit
    def test_zona_sin_metadatos_cuenta_como_no_industrial(self):
        assert cumple_preferencia_industrial("Desconocida", False)
        assert not cumple_preferencia_industrial("Desconocida", True)


# ------------------------------------------------- dataset real (híbrido)
class TestRecomendarConDatosReales:
    """Pruebas de cordura de `recomendar` sobre el dataset real cargado."""

    @pytest.mark.unit
    def test_devuelve_upz_reales(self):
        for nombre, sim in recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=5):
            assert nombre in ZONAS and 0 <= sim <= 100

    @pytest.mark.unit
    def test_evitar_industriales_no_devuelve_ninguna(self):
        for nombre, _ in recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=len(ZONAS), industrial=False):
            assert METADATOS[nombre]["tipo"] != "industrial"

    @pytest.mark.unit
    def test_solo_industriales_devuelve_solo_industriales(self):
        resultado = recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=len(ZONAS), industrial=True)
        assert resultado
        assert all(METADATOS[n]["tipo"] == "industrial" for n, _ in resultado)


class TestFormatoNombre:
    @pytest.mark.unit
    @pytest.mark.parametrize("entrada,salida", [
        ("PASEO DE LOS LIBERTADORES", "Paseo de los Libertadores"),
        ("LA CANDELARIA", "La Candelaria"),          # conector al inicio se capitaliza
        ("SAN ISIDRO - PATIOS", "San Isidro - Patios"),
        ("20 DE JULIO", "20 de Julio"),
        ("ANTONIO NARIÑO", "Antonio Nariño"),
        ("", ""),
    ])
    def test_formato(self, entrada, salida):
        from KNN.knn import formato_nombre
        assert formato_nombre(entrada) == salida
