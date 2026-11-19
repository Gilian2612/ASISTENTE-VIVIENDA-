"""KNN ponderado para recomendar zonas (UPZ) de Bogotá.

Cada zona se describe con 5 variables normalizadas en [0, 1] (1 = mejor):
transporte, seguridad, precio (1 = más barato), universidades, zonas verdes.
El usuario da la importancia (1-5) de cada variable, un presupuesto máximo y,
opcionalmente, si busca o evita zonas industriales; se recomiendan las K
zonas más cercanas a su perfil ideal.

Datos: data/zonas.csv, generado por `ETL.construir_zonas` a partir de
fuentes oficiales (Catastro/IDECA, SDSCJ, SNIES, SDP). Las 5 variables
vienen ya normalizadas; `arriendo_estimado` (COP) sale del avalúo catastral
y se usa para el filtro de presupuesto (ver DOCS/PRECIO.md).
"""
import csv
import math
from pathlib import Path

VARIABLES = ["transporte", "seguridad", "precio", "universidades", "verdes"]

# Variables que aún usan datos provisionales (ninguna desde que hay fuente de precio).
VARIABLES_PROVISIONALES = []

RUTA_ZONAS = Path(__file__).resolve().parents[2] / "data" / "zonas.csv"


CONECTORES = {"de", "del", "la", "las", "los", "el", "y"}


def formato_nombre(texto):
    """'PASEO DE LOS LIBERTADORES' -> 'Paseo de los Libertadores'."""
    palabras = texto.strip().lower().split()
    return " ".join(
        p if i > 0 and p in CONECTORES else p[:1].upper() + p[1:]
        for i, p in enumerate(palabras)
    )


def cargar_zonas(ruta=RUTA_ZONAS):
    """Lee el CSV del ETL.

    Devuelve (zonas, metadatos):
    - zonas: {nombre: ([5 variables normalizadas], arriendo estimado COP)}
    - metadatos: {nombre: {"codigo_upz", "localidad", "tipo"}}

    Las UPZ sin arriendo estimado se omiten (no se pueden filtrar por presupuesto).
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe {ruta}. Genéralo con: cd src && python3 -m ETL.construir_zonas"
        )

    zonas, metadatos = {}, {}
    with ruta.open(encoding="utf-8") as fh:
        for f in csv.DictReader(fh):
            if not f.get("arriendo_estimado"):
                continue
            nombre = formato_nombre(f["nombre"])
            zonas[nombre] = (
                [float(f[v]) for v in VARIABLES],
                round(float(f["arriendo_estimado"])),
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
