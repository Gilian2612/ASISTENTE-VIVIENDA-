"""Construye `data/zonas.csv`: una fila por UPZ con las variables verificadas.

Variables disponibles hoy (fuentes oficiales, ver `ETL.fuentes`):
- transporte: densidad de estaciones/portales TM y de paraderos SITP por km².
- verdes: % del área de la UPZ ocupada por parques del sistema distrital.
- localidad: localidad donde cae el centroide de la UPZ.
- tipo: industrial / dotacional / residencial (tabla hardcodeada, `ETL.tipos_upz`).
- seguridad: 70 % incidentes 123 por UPZ + 30 % delitos de alto impacto por
  localidad, por km², promedio 2025-2026 (SDSCJ, ver `ETL.seguridad`).

- universidades: sedes de educación superior a <= 2 km del centroide de la UPZ
  (SNIES + campus del POT + sedes ubicadas a mano, ver `ETL.universidades`).

Pendiente (sin fuente abierta verificada): precio / arriendo.

Normalización: cada indicador se divide por su percentil 95 (calculado solo
sobre las UPZ residenciales) y se recorta a [0, 1], así los valores extremos
(p. ej. UPZ-parque) no aplastan al resto.

Parques que cruzan límites: el parque cuenta en TODAS las UPZ que toca
(columna `parques`), y su área se reparte según la porción que cae en cada
una (estimada por muestreo en grilla), para no contar dos veces los m².

Uso:  cd src && python3 -m ETL.construir_zonas [ruta_salida.csv]
"""
import csv
import math
import sys
from pathlib import Path

from ETL import fuentes, seguridad, universidades
from ETL.geometria import area, caja, centroide, en_caja, poligonos, punto_en_poligono
from ETL.tipos_upz import RESIDENCIAL, tipo_de

RUTA_SALIDA = Path(__file__).resolve().parents[2] / "data" / "zonas.csv"

COLUMNAS = [
    "codigo_upz", "nombre", "localidad", "tipo", "area_km2",
    "estaciones_tm", "paraderos_sitp", "estaciones_tm_km2", "paraderos_sitp_km2",
    "parques", "area_parques_m2", "verde_pct",
    "incidentes_123", "incidentes_123_km2", "delitos_localidad", "delitos_localidad_km2",
    "universidades_2km", "universidad_cercana_m",
    "transporte", "seguridad", "universidades", "verdes",
]

# Puntos de muestreo (aprox.) por parque para repartir su área entre UPZ.
MUESTRAS_POR_PARQUE = 400


class IndiceZonas:
    """Busca en qué polígono cae un punto, con prefiltro por caja envolvente."""

    def __init__(self, features, campo_id):
        self._zonas = [
            (f["properties"][campo_id], f["geometry"], caja(f["geometry"]))
            for f in features
        ]

    def buscar(self, x, y):
        for zona_id, geom, c in self._zonas:
            if en_caja(x, y, c) and punto_en_poligono(x, y, geom):
                return zona_id
        return None

    def buscar_poligono(self, geom):
        """Zona que contiene al polígono: por su centroide o, si este cae fuera
        de todas las zonas, por mayoría de los vértices del anillo exterior."""
        zona = self.buscar(*centroide(geom))
        if zona is not None:
            return zona
        votos = {}
        for poligono in poligonos(geom):
            for x, y in poligono[0]:
                z = self.buscar(x, y)
                if z is not None:
                    votos[z] = votos.get(z, 0) + 1
        return max(votos, key=votos.get) if votos else None


def contar_puntos(indice, puntos):
    """{zona_id: cantidad de puntos} (los puntos fuera de toda zona se ignoran)."""
    conteo = {}
    for f in puntos:
        x, y = f["geometry"]["coordinates"][:2]
        zona = indice.buscar(x, y)
        if zona is not None:
            conteo[zona] = conteo.get(zona, 0) + 1
    return conteo


def zonas_tocadas(indice, geom):
    """Zonas donde cae el centroide o algún vértice del polígono."""
    zonas = {indice.buscar(*centroide(geom))}
    for poligono in poligonos(geom):
        for x, y in poligono[0]:
            zonas.add(indice.buscar(x, y))
    zonas.discard(None)
    return zonas


def repartir_area(indice, geom, muestras=MUESTRAS_POR_PARQUE):
    """{zona_id: m² del polígono dentro de la zona}.

    Si el polígono toca una sola zona, toda su área va a esa zona. Si toca
    varias, se reparte según la fracción de puntos de una grilla regular
    (dentro del polígono) que cae en cada zona. La parte que cae fuera de
    todas las zonas se descarta.
    """
    zonas = zonas_tocadas(indice, geom)
    a = area(geom)
    if len(zonas) <= 1:
        return {z: a for z in zonas}

    xmin, ymin, xmax, ymax = caja(geom)
    ancho, alto = xmax - xmin, ymax - ymin
    # El segundo término acota las iteraciones en polígonos largos y delgados.
    paso = max(math.sqrt(ancho * alto / muestras), max(ancho, alto) / muestras, 1e-9)
    conteo, dentro = {}, 0
    y = ymin + paso / 2
    while y < ymax:
        x = xmin + paso / 2
        while x < xmax:
            if punto_en_poligono(x, y, geom):
                dentro += 1
                z = indice.buscar(x, y)
                if z is not None:
                    conteo[z] = conteo.get(z, 0) + 1
            x += paso
        y += paso
    if dentro == 0:  # polígono muy delgado: ningún punto de la grilla cayó dentro
        return {z: a / len(zonas) for z in zonas}
    return {z: a * n / dentro for z, n in conteo.items()}


def repartir_parques(indice, parques):
    """Devuelve ({zona_id: m² de parque}, {zona_id: n.º de parques que la tocan})."""
    areas, conteo = {}, {}
    for f in parques:
        if not f.get("geometry"):
            continue
        for zona, m2 in repartir_area(indice, f["geometry"]).items():
            areas[zona] = areas.get(zona, 0.0) + m2
            conteo[zona] = conteo.get(zona, 0) + 1
    return areas, conteo


def normalizar(valores, percentil=0.95, referencia=None):
    """Divide por el percentil dado y recorta a [0, 1]. Todo 0 si el tope es 0.

    El percentil se calcula sobre `referencia` (por defecto, los mismos
    `valores`); así se puede calibrar la escala con un subconjunto.
    """
    if not valores:
        return []
    ordenados = sorted(referencia or valores)
    # Percentil por rango más cercano: el menor valor que deja por debajo
    # al menos `percentil` de los datos.
    tope = ordenados[max(math.ceil(percentil * len(ordenados)) - 1, 0)]
    if tope <= 0:
        return [0.0 for _ in valores]
    return [min(max(v, 0) / tope, 1.0) for v in valores]


def construir(capas):
    """Recibe {nombre_capa: [features]} y devuelve las filas del dataset."""
    upz = [f for f in capas["upz"] if f.get("geometry")]
    indice_upz = IndiceZonas(upz, "CODIGO_UPZ")
    indice_loc = IndiceZonas(
        [f for f in capas["localidades"] if f.get("geometry")], "LOCNOMBRE"
    )

    tm = contar_puntos(indice_upz, capas["estaciones_tm"] + capas["portales_tm"])
    sitp = contar_puntos(indice_upz, capas["paraderos_sitp"])
    parques, n_parques = repartir_parques(indice_upz, capas["parques"])

    incidentes = seguridad.incidentes_por_upz(capas["incidentes_upz"])
    delitos = seguridad.delitos_por_localidad(capas["delitos_localidad"])
    area_loc_km2 = {}
    for f in capas["localidades"]:
        if f.get("geometry"):
            clave = seguridad.clave_localidad(f["properties"]["LOCNOMBRE"])
            area_loc_km2[clave] = area_loc_km2.get(clave, 0.0) + area(f["geometry"]) / 1e6

    sedes = universidades.construir_sedes(capas["ies_snies"], capas["campus_pot"])

    filas = []
    for f in upz:
        codigo = f["properties"]["CODIGO_UPZ"]
        n_univ, d_univ = universidades.cercania(centroide(f["geometry"]), sedes)
        area_m2 = area(f["geometry"])
        area_km2 = area_m2 / 1e6
        n_tm, n_sitp = tm.get(codigo, 0), sitp.get(codigo, 0)
        verde = parques.get(codigo, 0.0)
        localidad = indice_loc.buscar_poligono(f["geometry"]) or ""
        clave_loc = seguridad.clave_localidad(localidad)
        n_inc = incidentes.get(str(codigo))
        n_del = delitos.get(clave_loc)
        km2_loc = area_loc_km2.get(clave_loc)
        filas.append({
            "codigo_upz": codigo,
            "nombre": f["properties"]["NOMBRE"],
            "localidad": localidad,
            "incidentes_123": "" if n_inc is None else round(n_inc, 1),
            "incidentes_123_km2": "" if n_inc is None or not area_km2 else round(n_inc / area_km2, 2),
            "delitos_localidad": "" if n_del is None else round(n_del, 1),
            "delitos_localidad_km2": "" if n_del is None or not km2_loc else round(n_del / km2_loc, 2),
            "tipo": tipo_de(codigo),
            "area_km2": round(area_km2, 3),
            "estaciones_tm": n_tm,
            "paraderos_sitp": n_sitp,
            "estaciones_tm_km2": round(n_tm / area_km2, 3) if area_km2 else 0.0,
            "paraderos_sitp_km2": round(n_sitp / area_km2, 3) if area_km2 else 0.0,
            "parques": n_parques.get(codigo, 0),
            "area_parques_m2": round(verde, 1),
            "verde_pct": round(100 * min(verde / area_m2, 1.0), 2) if area_m2 else 0.0,
            "universidades_2km": n_univ,
            "universidad_cercana_m": "" if d_univ is None else round(d_univ),
        })

    # La escala se calibra con las UPZ residenciales: los parques
    # metropolitanos o el aeropuerto no deben definir qué es "mucho verde".
    residenciales = [r for r in filas if r["tipo"] == RESIDENCIAL]

    def norm(campo):
        return normalizar([r[campo] for r in filas],
                          referencia=[r[campo] for r in residenciales])

    tm_n = norm("estaciones_tm_km2")
    sitp_n = norm("paraderos_sitp_km2")
    verde_n = norm("verde_pct")
    univ_n = norm("universidades_2km")
    for r, a, b, v, u in zip(filas, tm_n, sitp_n, verde_n, univ_n):
        r["transporte"] = round((a + b) / 2, 4)
        r["verdes"] = round(v, 4)
        r["universidades"] = round(u, 4)

    # Seguridad = 1 - riesgo normalizado; las UPZ sin dato quedan en None
    # y `seguridad.combinar` usa el otro componente.
    def seguridad_desde(campo):
        con_dato = [r for r in filas if r[campo] != ""]
        riesgo = normalizar([r[campo] for r in con_dato],
                            referencia=[r[campo] for r in con_dato if r["tipo"] == RESIDENCIAL])
        valores = {id(r): 1 - x for r, x in zip(con_dato, riesgo)}
        return [valores.get(id(r)) for r in filas]

    for r, s_upz, s_loc in zip(filas, seguridad_desde("incidentes_123_km2"),
                               seguridad_desde("delitos_localidad_km2")):
        r["seguridad"] = round(seguridad.combinar(s_upz, s_loc), 4)

    filas.sort(key=_orden_codigo)
    return filas


def _orden_codigo(fila):
    """Ordena por código numérico (1, 2, ..., 10) y deja al final los no numéricos."""
    codigo = str(fila["codigo_upz"])
    return (0, int(codigo), "") if codigo.isdigit() else (1, 0, codigo)


def escribir_csv(filas, ruta):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        escritor = csv.DictWriter(fh, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)


def main(argv=None):  # pragma: no cover - requiere red; cubierto por tests de integración
    argv = sys.argv[1:] if argv is None else argv
    ruta = Path(argv[0]) if argv else RUTA_SALIDA
    print("Descargando capas de Catastro Bogotá / IDECA, SDSCJ y SDP...")
    capas = fuentes.descargar_todo()
    for nombre, features in capas.items():
        print(f"  {nombre}: {len(features)}")
    filas = construir(capas)
    escribir_csv(filas, ruta)
    print(f"{len(filas)} UPZ escritas en {ruta}")


if __name__ == "__main__":  # pragma: no cover
    main()
