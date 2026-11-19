"""KNN ponderado para recomendar zonas (UPZ) de Bogotá.

Cada zona se describe con 5 variables normalizadas en [0, 1] (1 = mejor):
transporte, seguridad, precio (1 = más barato), universidades, zonas verdes.
El usuario da la importancia (1-5) de cada variable, un presupuesto máximo y,
opcionalmente, si busca o evita zonas industriales; se recomiendan las K
zonas más cercanas a su perfil ideal.

Datos HÍBRIDOS:
- REALES (data/zonas.csv, generado por `ETL.construir_zonas`):
  UPZ, localidad, tipo, transporte, seguridad (SDSCJ) y zonas verdes.
- PROVISIONALES (hardcodeados abajo, por localidad, hasta tener fuente):
  universidades y arriendo promedio (del que sale `precio`).
"""
import csv
import math
from pathlib import Path

VARIABLES = ["transporte", "seguridad", "precio", "universidades", "verdes"]

# Variables que aún usan datos provisionales (ver PROVISIONAL_POR_LOCALIDAD).
VARIABLES_PROVISIONALES = ["precio", "universidades"]

RUTA_ZONAS = Path(__file__).resolve().parents[2] / "data" / "zonas.csv"

# PROVISIONAL — valores de ejemplo por localidad, NO son datos oficiales.
# Reemplazar cuando haya fuente (SNIES, OTC/Catastro).
# localidad: (universidades 0-1, arriendo promedio COP)
PROVISIONAL_POR_LOCALIDAD = {
    "USAQUEN":            (0.45, 2_600_000),
    "CHAPINERO":          (0.95, 2_900_000),
    "SANTA FE":           (0.85, 1_500_000),
    "SAN CRISTOBAL":      (0.10,   900_000),
    "USME":               (0.05,   750_000),
    "TUNJUELITO":         (0.20, 1_000_000),
    "BOSA":               (0.10,   850_000),
    "KENNEDY":            (0.25, 1_100_000),
    "FONTIBON":           (0.30, 1_700_000),
    "ENGATIVA":           (0.35, 1_300_000),
    "SUBA":               (0.40, 1_600_000),
    "BARRIOS UNIDOS":     (0.55, 1_800_000),
    "TEUSAQUILLO":        (0.90, 2_000_000),
    "LOS MARTIRES":       (0.45, 1_200_000),
    "ANTONIO NARIÑO":     (0.40, 1_200_000),
    "PUENTE ARANDA":      (0.30, 1_300_000),
    "CANDELARIA":         (0.90, 1_500_000),
    "RAFAEL URIBE URIBE": (0.15,   950_000),
    "CIUDAD BOLIVAR":     (0.05,   750_000),
    "SUMAPAZ":            (0.00,   600_000),
}


CONECTORES = {"de", "del", "la", "las", "los", "el", "y"}


def formato_nombre(texto):
    """'PASEO DE LOS LIBERTADORES' -> 'Paseo de los Libertadores'."""
    palabras = texto.strip().lower().split()
    return " ".join(
        p if i > 0 and p in CONECTORES else p[:1].upper() + p[1:]
        for i, p in enumerate(palabras)
    )


def cargar_zonas(ruta=RUTA_ZONAS, provisional=None):
    """Lee el CSV del ETL y completa con los datos provisionales (universidades, arriendo).

    Devuelve (zonas, metadatos):
    - zonas: {nombre: ([5 variables normalizadas], arriendo COP)}
    - metadatos: {nombre: {"codigo_upz", "localidad", "tipo"}}

    Las UPZ sin localidad o con localidad sin datos provisionales se omiten.
    `precio` se calcula invirtiendo el arriendo con min-max sobre las zonas
    cargadas (la más barata = 1, la más cara = 0).
    """
    provisional = PROVISIONAL_POR_LOCALIDAD if provisional is None else provisional
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe {ruta}. Genéralo con: cd src && python3 -m ETL.construir_zonas"
        )

    filas = []
    with ruta.open(encoding="utf-8") as fh:
        for fila in csv.DictReader(fh):
            if fila["localidad"] in provisional:
                filas.append(fila)

    arriendos = [provisional[f["localidad"]][1] for f in filas]
    minimo, maximo = (min(arriendos), max(arriendos)) if arriendos else (0, 0)
    rango = (maximo - minimo) or 1

    zonas, metadatos = {}, {}
    for f in filas:
        universidades, arriendo = provisional[f["localidad"]]
        precio = 1 - (arriendo - minimo) / rango
        nombre = formato_nombre(f["nombre"])
        zonas[nombre] = (
            [float(f["transporte"]), float(f["seguridad"]), round(precio, 4),
             universidades, float(f["verdes"])],
            arriendo,
        )
        metadatos[nombre] = {
            "codigo_upz": f["codigo_upz"],
            "localidad": f["localidad"],
            "tipo": f["tipo"],
        }
    return zonas, metadatos


ZONAS, METADATOS = cargar_zonas()


def pesos_desde_importancia(importancias):
    """Convierte importancias 1-5 en pesos que suman 1."""
    total = sum(importancias)
    return [i / total for i in importancias]


def distancia(a, b, pesos):
    """Distancia euclidiana ponderada."""
    return math.sqrt(sum(w * (x - y) ** 2 for x, y, w in zip(a, b, pesos)))


def cumple_preferencia_industrial(nombre, industrial):
    """industrial: True = solo zonas industriales, False = excluirlas, None = sin preferencia."""
    if industrial is None:
        return True
    es_industrial = METADATOS.get(nombre, {}).get("tipo") == "industrial"
    return es_industrial == industrial


def recomendar(importancias, presupuesto, k=3, industrial=None):
    """Devuelve las k zonas más parecidas al perfil: [(zona, similitud %), ...].

    El perfil ideal del usuario es 1.0 en todas las variables; las
    importancias solo ponderan cuánto pesa cada variable en la distancia.
    `industrial` filtra por tipo de zona (ver `cumple_preferencia_industrial`).
    """
    pesos = pesos_desde_importancia(importancias)
    ideal = [1.0] * len(VARIABLES)
    max_dist = math.sqrt(sum(pesos))  # distancia máxima posible (todo en 0)

    candidatas = []
    for nombre, (vector, arriendo) in ZONAS.items():
        if arriendo > presupuesto:  # filtro duro por presupuesto
            continue
        if not cumple_preferencia_industrial(nombre, industrial):
            continue
        d = distancia(vector, ideal, pesos)
        candidatas.append((nombre, round(100 * (1 - d / max_dist), 1)))

    candidatas.sort(key=lambda t: t[1], reverse=True)
    return candidatas[:k]


if __name__ == "__main__":  # pragma: no cover
    # Importancia 1-5 en el orden de VARIABLES
    perfil = [5, 4, 3, 5, 2]  # estudiante: transporte y universidades
    presupuesto = 1_800_000

    print(f"Importancias: {dict(zip(VARIABLES, perfil))}")
    print(f"Presupuesto máximo: ${presupuesto:,} COP")
    print(f"Zonas cargadas: {len(ZONAS)} UPZ\n")
    for etiqueta, industrial in [("sin preferencia", None), ("evitando industriales", False)]:
        print(f"-- {etiqueta}")
        for i, (zona, sim) in enumerate(recomendar(perfil, presupuesto, industrial=industrial), 1):
            m = METADATOS[zona]
            print(f"{i}. {zona} ({m['localidad'].title()}, {m['tipo']}): {sim}% de similitud")
