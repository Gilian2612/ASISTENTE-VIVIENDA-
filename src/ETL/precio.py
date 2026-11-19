"""Variable `precio` y arriendo estimado a partir del avalúo catastral.

Fuente: Catastro Bogotá (UAECD), servicio `catastro/medavalcatphmz` capa 1:
mediana del avalúo catastral por m² de predios en propiedad horizontal
RESIDENCIAL (apartamentos), por manzana, vigencia 2026.

Para cada UPZ se toma la mediana de sus manzanas (asignadas por centroide).
El arriendo mensual se estima como:

    arriendo ≈ (avalúo/m² ÷ RELACION_AVALUO_COMERCIAL) × AREA_TIPICA_M2
               × TASA_RENTA_ANUAL ÷ 12

- TASA_RENTA_ANUAL: ~6,2 % anual (canon / valor comercial), Observatorio
  Técnico Catastral (OTC, UAECD), estudio de rentabilidad de la vivienda.
- RELACION_AVALUO_COMERCIAL: en Bogotá el avalúo catastral está entre el
  70 % y el 100 % del valor comercial; se usa el punto medio, 85 %.
- AREA_TIPICA_M2: supuesto del proyecto (apartamento de 60 m²).

Ver DOCS/PRECIO.md para la explicación completa.
"""
import statistics

VIGENCIA = 2026
TASA_RENTA_ANUAL = 0.062
RELACION_AVALUO_COMERCIAL = 0.85
AREA_TIPICA_M2 = 60
# Una UPZ con menos manzanas que esto usa la mediana de su localidad.
MIN_MANZANAS = 3

CAMPO_AVALUO = "AV_CAT_PH_RESIDENCIAL"
WHERE = (f"VIGENCIA >= DATE '{VIGENCIA}-01-01' AND VIGENCIA < DATE '{VIGENCIA + 1}-01-01'"
         f" AND {CAMPO_AVALUO} > 0")


def arriendo_estimado(avaluo_m2, relacion=RELACION_AVALUO_COMERCIAL,
                      area_m2=AREA_TIPICA_M2, tasa_anual=TASA_RENTA_ANUAL):
    """Arriendo mensual estimado (COP) de un apartamento típico."""
    valor_comercial_m2 = avaluo_m2 / relacion
    return valor_comercial_m2 * area_m2 * tasa_anual / 12


def mediana(valores):
    return statistics.median(valores) if valores else None


def avaluos_por_zona(manzanas, ubicar):
    """{zona: [avalúos/m² de sus manzanas]}.

    `ubicar(geometria)` devuelve la zona de la manzana (p. ej. la UPZ donde
    cae su centroide) o None si cae fuera.
    """
    resultado = {}
    for f in manzanas:
        valor = (f.get("properties") or {}).get(CAMPO_AVALUO)
        if not f.get("geometry") or not valor or valor <= 0:
            continue
        zona = ubicar(f["geometry"])
        if zona is not None:
            resultado.setdefault(zona, []).append(valor)
    return resultado


def avaluo_por_upz(avaluos_upz, localidad_de_upz, minimo=MIN_MANZANAS):
    """{codigo_upz: (mediana avalúo/m², n.º manzanas, fuente)}.

    fuente = "upz" si la UPZ tiene al menos `minimo` manzanas; si no,
    "localidad" (mediana de todas las manzanas de su localidad) y, si
    tampoco hay, "ciudad" (mediana de toda la ciudad).
    """
    por_localidad = {}
    for codigo, valores in avaluos_upz.items():
        por_localidad.setdefault(localidad_de_upz.get(codigo), []).extend(valores)
    todos = [v for valores in avaluos_upz.values() for v in valores]

    resultado = {}
    for codigo, localidad in localidad_de_upz.items():
        propios = avaluos_upz.get(codigo, [])
        if len(propios) >= minimo:
            resultado[codigo] = (mediana(propios), len(propios), "upz")
        elif por_localidad.get(localidad):
            resultado[codigo] = (mediana(por_localidad[localidad]), len(propios), "localidad")
        else:
            resultado[codigo] = (mediana(todos), len(propios), "ciudad")
    return resultado
