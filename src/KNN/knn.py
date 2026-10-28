"""KNN sencillo para recomendar zonas de Bogotá.

Cada zona se describe con 5 variables normalizadas en [0, 1]:
transporte, seguridad, precio (1 = más barato), universidades, zonas verdes.
El usuario da la importancia (1-5) de cada variable y un presupuesto máximo;
se recomiendan las K zonas más cercanas a su perfil ideal.

Los datos de ZONAS son de EJEMPLO: reemplazar por el dataset real de UPZ.
"""
import math

VARIABLES = ["transporte", "seguridad", "precio", "universidades", "verdes"]

# nombre: (variables normalizadas 0-1, arriendo promedio en COP)
ZONAS = {
    "Chapinero":     ([0.90, 0.60, 0.25, 0.95, 0.60], 2_200_000),
    "Teusaquillo":   ([0.85, 0.70, 0.45, 0.90, 0.75], 1_800_000),
    "Usaquén":       ([0.70, 0.80, 0.30, 0.40, 0.85], 2_400_000),
    "Suba":          ([0.60, 0.55, 0.60, 0.35, 0.70], 1_400_000),
    "Kennedy":       ([0.75, 0.40, 0.80, 0.30, 0.45], 1_000_000),
    "Fontibón":      ([0.80, 0.60, 0.65, 0.40, 0.50], 1_300_000),
    "Engativá":      ([0.70, 0.50, 0.70, 0.45, 0.55], 1_200_000),
    "Bosa":          ([0.50, 0.30, 0.90, 0.15, 0.35], 800_000),
    "Barrios Unidos": ([0.80, 0.65, 0.55, 0.60, 0.60], 1_500_000),
    "Santa Fe":      ([0.85, 0.35, 0.60, 0.85, 0.55], 1_300_000),
}


def pesos_desde_importancia(importancias):
    """Convierte importancias 1-5 en pesos que suman 1."""
    total = sum(importancias)
    return [i / total for i in importancias]


def distancia(a, b, pesos):
    """Distancia euclidiana ponderada."""
    return math.sqrt(sum(w * (x - y) ** 2 for x, y, w in zip(a, b, pesos)))


def recomendar(importancias, presupuesto, k=3):
    """Devuelve las k zonas más parecidas al perfil: [(zona, similitud %), ...].

    El perfil ideal del usuario es 1.0 en todas las variables; las
    importancias solo ponderan cuánto pesa cada variable en la distancia.
    """
    pesos = pesos_desde_importancia(importancias)
    ideal = [1.0] * len(VARIABLES)
    max_dist = math.sqrt(sum(pesos))  # distancia máxima posible (todo en 0)

    candidatas = []
    for nombre, (vector, arriendo) in ZONAS.items():
        if arriendo > presupuesto:  # filtro duro por presupuesto
            continue
        d = distancia(vector, ideal, pesos)
        candidatas.append((nombre, round(100 * (1 - d / max_dist), 1)))

    candidatas.sort(key=lambda t: t[1], reverse=True)
    return candidatas[:k]


if __name__ == "__main__":
    # Importancia 1-5 en el orden de VARIABLES
    perfil = [5, 4, 3, 5, 2]  # estudiante: transporte y universidades
    presupuesto = 1_800_000

    print(f"Importancias: {dict(zip(VARIABLES, perfil))}")
    print(f"Presupuesto máximo: ${presupuesto:,} COP\n")
    for i, (zona, sim) in enumerate(recomendar(perfil, presupuesto), 1):
        print(f"{i}. {zona}: {sim}% de similitud")
