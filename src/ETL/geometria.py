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


def ctm12_a_wgs84(x, y):
    """(x, y) en metros EPSG:9377 -> (longitud, latitud) en grados.

    Inversa de la Transversa de Mercator (Snyder, 1987); error < 1e-8 grados.
    """
    e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
    m = _arco_meridiano(_LAT0) + (y - _FN) / _K0
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2 ** 2 / 64 - 5 * _E2 ** 3 / 256))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    sen, cos, tan = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    c1 = _EP2 * cos ** 2
    t1 = tan ** 2
    n1 = _A / math.sqrt(1 - _E2 * sen ** 2)
    r1 = _A * (1 - _E2) / (1 - _E2 * sen ** 2) ** 1.5
    d = (x - _FE) / (n1 * _K0)
    phi = phi1 - (n1 * tan / r1) * (
        d ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * _EP2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * _EP2 - 3 * c1 ** 2) * d ** 6 / 720
    )
    lam = _LON0 + (
        d - (1 + 2 * t1 + c1) * d ** 3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * _EP2 + 24 * t1 ** 2) * d ** 5 / 120
    ) / cos
    return math.degrees(lam), math.degrees(phi)


def a_wgs84(geom, decimales=6):
    """Copia de una geometría GeoJSON (Point/Polygon/MultiPolygon) en EPSG:9377
    convertida a longitud/latitud, redondeada (6 decimales ≈ 10 cm)."""
    def punto(p):
        lon, lat = ctm12_a_wgs84(p[0], p[1])
        return [round(lon, decimales), round(lat, decimales)]

    tipo, coords = geom["type"], geom["coordinates"]
    if tipo == "Point":
        nuevas = punto(coords)
    elif tipo == "Polygon":
        nuevas = [[punto(p) for p in anillo] for anillo in coords]
    elif tipo == "MultiPolygon":
        nuevas = [[[punto(p) for p in anillo] for anillo in pol] for pol in coords]
    else:
        raise ValueError(f"Geometría no soportada: {tipo}")
    return {"type": tipo, "coordinates": nuevas}


def _dist_a_segmento(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def simplificar_linea(puntos, tolerancia):
    """Douglas-Peucker: quita vértices a menos de `tolerancia` de la línea simplificada."""
    if len(puntos) < 3:
        return list(puntos)
    conservar = [False] * len(puntos)
    conservar[0] = conservar[-1] = True
    pila = [(0, len(puntos) - 1)]
    while pila:
        i, j = pila.pop()
        mayor, indice = -1.0, None
        for k in range(i + 1, j):
            d = _dist_a_segmento(puntos[k], puntos[i], puntos[j])
            if d > mayor:
                mayor, indice = d, k
        if indice is not None and mayor > tolerancia:
            conservar[indice] = True
            pila.extend([(i, indice), (indice, j)])
    return [p for p, c in zip(puntos, conservar) if c]


def simplificar(geom, tolerancia):
    """Simplifica Polygon/MultiPolygon (en metros). Cada anillo conserva al menos
    4 puntos (triángulo cerrado); si quedaría con menos, se deja como estaba."""
    def anillo(a):
        s = simplificar_linea(a, tolerancia)
        return s if len(s) >= 4 else list(a)

    tipo = geom["type"]
    if tipo == "Polygon":
        return {"type": tipo, "coordinates": [anillo(a) for a in geom["coordinates"]]}
    if tipo == "MultiPolygon":
        return {"type": tipo, "coordinates": [[anillo(a) for a in pol] for pol in geom["coordinates"]]}
    raise ValueError(f"Geometría no soportada: {tipo}")


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
