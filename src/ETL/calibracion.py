"""Calibración del arriendo estimado con anuncios reales (Metrocuadrado / Fincaraíz).

El arriendo que sale del avalúo catastral (`arriendo_avaluo`, ver
`ETL.precio`) puede estar desplazado frente al mercado. Esta etapa lo corrige
con una MUESTRA DE ANUNCIOS RECOGIDA A MANO en Metrocuadrado y Fincaraíz,
guardada en `data/calibracion_arriendos.csv` (no se hace scraping: los portales
tienen protección anti-bots y no se confirmó que sus términos lo permitan).

Método:
1. Cada anuncio se lleva a un apartamento de `AREA_TIPICA_M2` (60 m²):
   canon_60 = canon / área × 60.
2. Razón del anuncio = canon_60 / arriendo_avaluo de su UPZ.
3. Factor = MEDIANA de las razones (robusta a anuncios atípicos).
4. arriendo_estimado = arriendo_avaluo × factor, redondeado a miles.

El factor es único para toda la ciudad, así que NO cambia el orden entre UPZ
(la variable `precio`); solo corrige el valor en pesos del filtro de
presupuesto. Si la muestra es muy pequeña (< MIN_ANUNCIOS anuncios o
< MIN_UPZ UPZ distintas) no se aplica y se informa el motivo.

Uso (recalibra data/zonas.csv sin volver a descargar las fuentes):
    cd src && python3 -m ETL.calibracion
"""
import csv
import statistics
import sys
import unicodedata
from datetime import date
from pathlib import Path

from ETL.precio import AREA_TIPICA_M2

RAIZ = Path(__file__).resolve().parents[2]
RUTA_ANUNCIOS = RAIZ / "data" / "calibracion_arriendos.csv"
RUTA_ZONAS = RAIZ / "data" / "zonas.csv"

COLUMNAS_ANUNCIOS = ["fuente", "fecha", "url", "upz", "area_m2", "canon_cop"]
FUENTES_VALIDAS = {"metrocuadrado", "fincaraiz"}
MIN_ANUNCIOS = 20
MIN_UPZ = 5
AREA_RANGO = (15, 400)              # m²
CANON_RANGO = (200_000, 40_000_000)  # COP / mes


def _normalizar(texto):
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                         if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.upper().replace("-", " ").split())


def resolver_upz(valor, filas):
    """Código de UPZ a partir de un código ('99', 'UPZ99') o un nombre ('Chapinero')."""
    texto = _normalizar(valor)
    codigo = texto.replace("UPZ", "").strip()
    codigos = {str(r["codigo_upz"]) for r in filas}
    if codigo.isdigit() and codigo.lstrip("0") in codigos:
        return codigo.lstrip("0")
    for r in filas:
        if _normalizar(r["nombre"]) == texto:
            return str(r["codigo_upz"])
    return None


def _numero(valor):
    """'2.500.000' / '2,500,000' / '$ 2500000' / '62,5' -> float."""
    texto = str(valor).replace("$", "").replace(" ", "").strip()
    if texto.count(".") > 1 or (texto.count(".") == 1 and len(texto.split(".")[1]) == 3):
        texto = texto.replace(".", "")
    if texto.count(",") > 1 or (texto.count(",") == 1 and len(texto.split(",")[1]) == 3):
        texto = texto.replace(",", "")
    return float(texto.replace(",", "."))


def validar_anuncio(fila, filas_zonas):
    """Devuelve el anuncio limpio o lanza ValueError con el motivo."""
    fuente = _normalizar(fila.get("fuente")).lower().replace(" ", "")
    if fuente not in FUENTES_VALIDAS:
        raise ValueError(f"fuente '{fila.get('fuente')}' no es metrocuadrado ni fincaraiz")
    try:
        fecha = date.fromisoformat(str(fila.get("fecha", "")).strip())
    except ValueError:
        raise ValueError(f"fecha '{fila.get('fecha')}' no tiene formato AAAA-MM-DD") from None
    try:
        area, canon = _numero(fila.get("area_m2")), _numero(fila.get("canon_cop"))
    except (TypeError, ValueError):
        raise ValueError("area_m2 y canon_cop deben ser números") from None
    if not AREA_RANGO[0] <= area <= AREA_RANGO[1]:
        raise ValueError(f"area_m2 {area:g} fuera de rango {AREA_RANGO}")
    if not CANON_RANGO[0] <= canon <= CANON_RANGO[1]:
        raise ValueError(f"canon_cop {canon:,.0f} fuera de rango {CANON_RANGO}")
    codigo = resolver_upz(fila.get("upz"), filas_zonas)
    if codigo is None:
        raise ValueError(f"UPZ '{fila.get('upz')}' no existe (usa el código o el nombre de la UPZ)")
    return {"fuente": fuente, "fecha": fecha, "url": (fila.get("url") or "").strip(),
            "codigo_upz": codigo, "area_m2": area, "canon_cop": canon}


def leer_anuncios(ruta, filas_zonas):
    """(anuncios válidos, [(línea, motivo)] de los descartados). Sin archivo: ([], [])."""
    ruta = Path(ruta)
    if not ruta.exists():
        return [], []
    validos, errores = [], []
    with ruta.open(encoding="utf-8") as fh:
        for linea, fila in enumerate(csv.DictReader(fh), start=2):
            if not any((v or "").strip() for v in fila.values()):
                continue
            try:
                validos.append(validar_anuncio(fila, filas_zonas))
            except ValueError as e:
                errores.append((linea, str(e)))
    return validos, errores


def calcular_factor(anuncios, filas_zonas, min_anuncios=MIN_ANUNCIOS, min_upz=MIN_UPZ):
    """Resumen de la calibración (dict). `aplicado` indica si la muestra alcanza."""
    base = {str(r["codigo_upz"]): float(r["arriendo_avaluo"])
            for r in filas_zonas if str(r.get("arriendo_avaluo", "")) not in ("", "None")}
    razones, por_fuente = [], {}
    for a in anuncios:
        if a["codigo_upz"] not in base or base[a["codigo_upz"]] <= 0:
            continue
        razon = (a["canon_cop"] / a["area_m2"] * AREA_TIPICA_M2) / base[a["codigo_upz"]]
        razones.append(razon)
        por_fuente.setdefault(a["fuente"], []).append(razon)

    n_upz = len({a["codigo_upz"] for a in anuncios if a["codigo_upz"] in base})
    resultado = {
        "anuncios": len(razones),
        "upz": n_upz,
        "factor": round(statistics.median(razones), 4) if razones else 1.0,
        "por_fuente": {f: {"anuncios": len(r), "factor": round(statistics.median(r), 4)}
                       for f, r in sorted(por_fuente.items())},
        "aplicado": False,
        "motivo": "",
    }
    if len(razones) >= 4:
        q = statistics.quantiles(razones, n=4)
        resultado["p25"], resultado["p75"] = round(q[0], 4), round(q[2], 4)
    if len(razones) < min_anuncios:
        resultado["motivo"] = f"muestra insuficiente: {len(razones)} anuncios (mínimo {min_anuncios})"
    elif n_upz < min_upz:
        resultado["motivo"] = f"muestra insuficiente: {n_upz} UPZ (mínimo {min_upz})"
    else:
        resultado["aplicado"] = True
    return resultado


def aplicar(filas_zonas, resultado):
    """Escribe `arriendo_estimado` = arriendo_avaluo × factor (si la calibración aplica)."""
    factor = resultado["factor"] if resultado["aplicado"] else 1.0
    for r in filas_zonas:
        base = r.get("arriendo_avaluo", "")
        r["arriendo_estimado"] = "" if base in ("", None) else round(float(base) * factor, -3)
    return filas_zonas


def calibrar(filas_zonas, ruta_anuncios=RUTA_ANUNCIOS):
    """Lee los anuncios, calcula el factor y lo aplica. Devuelve (resultado, errores)."""
    anuncios, errores = leer_anuncios(ruta_anuncios, filas_zonas)
    resultado = calcular_factor(anuncios, filas_zonas)
    aplicar(filas_zonas, resultado)
    return resultado, errores


def reporte(resultado, errores):
    """Texto legible con el resumen de la calibración."""
    lineas = [f"Anuncios usados: {resultado['anuncios']} en {resultado['upz']} UPZ"]
    for fuente, d in resultado["por_fuente"].items():
        lineas.append(f"  {fuente}: {d['anuncios']} anuncios, factor {d['factor']}")
    if "p25" in resultado:
        lineas.append(f"Factor (mediana): {resultado['factor']}  [p25 {resultado['p25']} - p75 {resultado['p75']}]")
    if resultado["aplicado"]:
        lineas.append(f"✓ Calibración aplicada: arriendo_estimado = arriendo_avaluo × {resultado['factor']}")
    else:
        lineas.append(f"✗ Calibración NO aplicada ({resultado['motivo']}); arriendo_estimado = arriendo_avaluo")
    for linea, motivo in errores:
        lineas.append(f"  descartado (línea {linea}): {motivo}")
    return "\n".join(lineas)


def main(argv=None):  # pragma: no cover - E/S de consola; la lógica está probada arriba
    from ETL.construir_zonas import COLUMNAS, escribir_csv
    argv = sys.argv[1:] if argv is None else argv
    ruta_zonas = Path(argv[0]) if argv else RUTA_ZONAS
    with ruta_zonas.open(encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))
    resultado, errores = calibrar(filas)
    escribir_csv(filas, ruta_zonas, columnas=COLUMNAS)
    print(reporte(resultado, errores))
    print(f"{ruta_zonas} actualizado.")


if __name__ == "__main__":  # pragma: no cover
    main()
