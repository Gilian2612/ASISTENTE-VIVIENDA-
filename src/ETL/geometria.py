"""Geometría plana mínima sobre GeoJSON en coordenadas métricas.

Solo se necesita: área, centroide, caja envolvente, punto-en-polígono y
distancia, para Polygon y MultiPolygon. Las coordenadas deben estar en metros
(p. ej. EPSG:9377) para que las áreas salgan en m². `wgs84_a_ctm12` convierte
latitud/longitud a EPSG:9377 para datos escritos a mano.
"""
import math

# EPSG:9377 — MAGNA-SIRGAS 2018 / Origen-Nacional (CTM12): Transversa de
# Mercator sobre el elipsoide GRS80.
_A = 6378137.0
_F = 1 / 298.257222101
_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)
_K0 = 0.9992
_LAT0, _LON0 = math.radians(4.0), math.radians(-73.0)
_FE, _FN = 5_000_000.0, 2_000_000.0


def _arco_meridiano(phi):
    e2, e4, e6 = _E2, _E2 ** 2, _E2 ** 3
    return _A * (
        (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
        - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
        + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi)
        - (35 * e6 / 3072) * math.sin(6 * phi)
    )


def wgs84_a_ctm12(lon, lat):
    """(longitud, latitud) en grados -> (x, y) en metros EPSG:9377.

    Transversa de Mercator (Snyder, 1987): error < 1 cm en Colombia.
    """
    phi, lam = math.radians(lat), math.radians(lon)
    sen, cos, tan = math.sin(phi), math.cos(phi), math.tan(phi)
    n = _A / math.sqrt(1 - _E2 * sen ** 2)
    t = tan ** 2
    c = _EP2 * cos ** 2
    a = (lam - _LON0) * cos
    x = _FE + _K0 * n * (
        a + (1 - t + c) * a ** 3 / 6
        + (5 - 18 * t + t ** 2 + 72 * c - 58 * _EP2) * a ** 5 / 120
    )
    y = _FN + _K0 * (
        _arco_meridiano(phi) - _arco_meridiano(_LAT0)
        + n * tan * (
            a ** 2 / 2 + (5 - t + 9 * c + 4 * c ** 2) * a ** 4 / 24
            + (61 - 58 * t + t ** 2 + 600 * c - 330 * _EP2) * a ** 6 / 720
        )
    )
    return x, y


def distancia(p, q):
    """Distancia euclidiana entre dos puntos (x, y)."""
    return math.hypot(p[0] - q[0], p[1] - q[1])


def poligonos(geom):
    """Lista de polígonos (cada uno: [anillo_exterior, *huecos]) de una geometría."""
    tipo = geom["type"]
    if tipo == "Polygon":
        return [geom["coordinates"]]
    if tipo == "MultiPolygon":
        return list(geom["coordinates"])
    raise ValueError(f"Geometría no soportada: {tipo}")


def area_con_signo(anillo):
    """Fórmula del zapato (shoelace). Positiva si el anillo va antihorario."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(anillo, anillo[1:] + anillo[:1]):
        s += x1 * y2 - x2 * y1
    return s / 2.0


def area(geom):
    """Área en unidades² (m² si la geometría está en metros), descontando huecos."""
    total = 0.0
    for exterior, *huecos in poligonos(geom):
        total += abs(area_con_signo(exterior)) - sum(abs(area_con_signo(h)) for h in huecos)
    return total


def _centroide_anillo(anillo):
    a = area_con_signo(anillo)
    if a == 0:
        n = len(anillo)
        return 0.0, sum(p[0] for p in anillo) / n, sum(p[1] for p in anillo) / n
    cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(anillo, anillo[1:] + anillo[:1]):
        f = x1 * y2 - x2 * y1
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    return abs(a), cx / (6 * a), cy / (6 * a)


def centroide(geom):
    """Centroide ponderado por área (los huecos restan)."""
    suma_a = suma_x = suma_y = 0.0
    for exterior, *huecos in poligonos(geom):
        for anillo, signo in [(exterior, 1)] + [(h, -1) for h in huecos]:
            a, x, y = _centroide_anillo(anillo)
            suma_a += signo * a
            suma_x += signo * a * x
            suma_y += signo * a * y
    if suma_a == 0:
        _, x, y = _centroide_anillo(poligonos(geom)[0][0])
        return x, y
    return suma_x / suma_a, suma_y / suma_a


def caja(geom):
    """Caja envolvente (xmin, ymin, xmax, ymax)."""
    xs, ys = [], []
    for poligono in poligonos(geom):
        for x, y in poligono[0]:
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def en_caja(x, y, c):
    return c[0] <= x <= c[2] and c[1] <= y <= c[3]


def punto_en_anillo(x, y, anillo):
    """Ray casting: True si (x, y) está dentro del anillo."""
    dentro = False
    for (x1, y1), (x2, y2) in zip(anillo, anillo[1:] + anillo[:1]):
        if (y1 > y) != (y2 > y):
            x_corte = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_corte:
                dentro = not dentro
    return dentro


def punto_en_poligono(x, y, geom):
    """True si (x, y) está dentro de algún polígono y fuera de sus huecos."""
    for exterior, *huecos in poligonos(geom):
        if punto_en_anillo(x, y, exterior) and not any(
            punto_en_anillo(x, y, h) for h in huecos
        ):
            return True
    return False
