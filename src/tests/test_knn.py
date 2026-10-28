import math

import pytest

from KNN import knn
from KNN.knn import (
    VARIABLES,
    ZONAS,
    distancia,
    pesos_desde_importancia,
    recomendar,
)

PERFIL_ESTUDIANTE = [5, 4, 3, 5, 2]
PRESUPUESTO_ALTO = 10_000_000


# ---------------------------------------------------------------- datos
class TestDatosZonas:
    """Valida la consistencia de los datos de ejemplo `ZONAS` y `VARIABLES`.

    No prueba lógica, sino que el "dataset" esté bien formado: si alguien lo
    reemplaza por el dataset real de UPZ y rompe el formato, estos tests avisan.
    Se va a testear:
    - que cada zona tenga un valor por variable,
    - que los valores estén normalizados en [0, 1],
    - que los arriendos sean positivos.
    """

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
    """

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
        assert len(recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=100)) == len(ZONAS)

    @pytest.mark.unit
    def test_k_cero_devuelve_vacio(self):
        """Con k = 0 devuelve una lista vacía."""
        assert recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=0) == []

    @pytest.mark.unit
    def test_formato_nombre_y_similitud(self):
        """Cada resultado es (nombre de zona existente, similitud float entre 0 y 100)."""
        for nombre, sim in recomendar(PERFIL_ESTUDIANTE, PRESUPUESTO_ALTO, k=10):
            assert nombre in ZONAS
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
            assert ZONAS[nombre][1] <= presupuesto

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
