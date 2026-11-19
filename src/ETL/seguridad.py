"""Variable `seguridad` a partir de las cifras de la SDSCJ.

Fuente: Secretaría Distrital de Seguridad, Convivencia y Justicia, Oficina de
Análisis de la Información y Estudios Estratégicos. Servicio ArcGIS REST
público `Tematicos_Pub/CifrasSCJ` (licencia CC BY-SA 4.0), listado en Datos
Abiertos Bogotá como "Delito de Alto Impacto. Bogotá D.C.".

Construcción (decisión del proyecto):
- 70 %: incidentes reportados a la línea 123 (NUSE) **por UPZ**.
- 30 %: delitos de alto impacto (SIEDCO, Policía) **por localidad**: el
  servicio no publica delitos por UPZ.
- Periodo: promedio de enero a septiembre de 2025 y 2026.
- Cada conteo se divide por el área (km²) de la UPZ o de la localidad,
  se normaliza a riesgo [0, 1] y seguridad = 1 - riesgo.
"""
import unicodedata

# Incidentes 123 por UPZ (capa 3) que reflejan inseguridad en el entorno.
CATEGORIAS_UPZ = {
    "H": "hurto",
    "R": "riñas",
    "D": "disparos",
    "PIA": "porte ilegal de armas",
    "N": "narcóticos",
}

# Delitos de alto impacto por localidad (capa 0) que afectan a residentes.
CATEGORIAS_LOCALIDAD = {
    "H": "homicidios",
    "LP": "lesiones personales",
    "HP": "hurto a personas",
    "HR": "hurto a residencias",
    "DS": "delitos sexuales",
}

ANIOS = ("25", "26")   # 2025 y 2026 (enero a septiembre)
PESO_UPZ = 0.7
PESO_LOCALIDAD = 1 - PESO_UPZ


def campos(categorias, anios=ANIOS):
    """Nombres de los campos del servicio, p. ej. 'CMH25CONT'."""
    return [f"CM{c}{a}CONT" for c in categorias for a in anios]


def promedio_anual(atributos, categorias, anios=ANIOS):
    """Suma de las categorías, promediada entre los años. Nulos cuentan como 0."""
    total = sum(atributos.get(f"CM{c}{a}CONT") or 0 for c in categorias for a in anios)
    return total / len(anios)


def codigo_upz(codigo_scj):
    """'UPZ37' -> '37'; 'UPZ1' -> '1'. Zonas rurales (UPR) o '999' -> None."""
    codigo = str(codigo_scj).strip().upper()
    if not codigo.startswith("UPZ"):
        return None
    numero = codigo[3:].lstrip("0")
    return numero if numero.isdigit() else None


def clave_localidad(nombre):
    """Normaliza nombres para cruzar fuentes: 'Usaquén' == 'USAQUEN'."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", nombre or "")
        if unicodedata.category(c) != "Mn" or c == "̃"  # conserva la ñ
    )
    return unicodedata.normalize("NFC", sin_tildes).strip().upper()


def incidentes_por_upz(features):
    """{codigo_upz: incidentes 123 promedio por año}."""
    resultado = {}
    for f in features:
        props = f["properties"]
        codigo = codigo_upz(props.get("CMIUUPLA"))
        if codigo is not None:
            resultado[codigo] = promedio_anual(props, CATEGORIAS_UPZ)
    return resultado


def delitos_por_localidad(features):
    """{CLAVE_LOCALIDAD: delitos de alto impacto promedio por año}."""
    resultado = {}
    for f in features:
        props = f["properties"]
        clave = clave_localidad(props.get("CMNOMLOCAL"))
        if clave and clave != "SIN LOCALIZACION":
            resultado[clave] = promedio_anual(props, CATEGORIAS_LOCALIDAD)
    return resultado


def combinar(seguridad_upz, seguridad_localidad):
    """Promedio ponderado; si falta un componente se usa el otro; si faltan ambos, 0.5."""
    if seguridad_upz is None and seguridad_localidad is None:
        return 0.5
    if seguridad_upz is None:
        return seguridad_localidad
    if seguridad_localidad is None:
        return seguridad_upz
    return PESO_UPZ * seguridad_upz + PESO_LOCALIDAD * seguridad_localidad
