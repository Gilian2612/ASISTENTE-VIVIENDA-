"""Variable `universidades`: sedes de educación superior cerca de cada UPZ.

Fuentes (todas públicas, ArcGIS REST):
1. SNIES (Ministerio de Educación), publicado por Catastro Bogotá / ATENEA:
   `educacion/infraestructuraeducativa` capa 1. Una sede principal por
   institución, con coordenadas. Se excluyen las inactivas (ESTADO "00").
2. POT, Decreto 555 de 2021 (SDP), "Ecosistema de educación superior":
   predios de campus, con sedes secundarias. Los predios con el mismo nombre
   a menos de 500 m se agrupan como una sola sede.
3. SEDES_MANUALES: sedes del SNIES que solo traen dirección y no aparecen en
   el POT; sus coordenadas se escribieron a mano (aproximadas) a partir de
   esa dirección.

Para no contar dos veces, un punto del SNIES o manual que cae dentro de un
predio del POT se descarta (el predio ya representa ese campus).

Indicador: número de sedes a <= 2 km del centroide de la UPZ (distancia
caminable o en bicicleta).
"""
import unicodedata

from ETL.geometria import area, centroide, distancia, punto_en_poligono, wgs84_a_ctm12

RADIO_M = 2000
DISTANCIA_MISMA_SEDE_M = 500

# (nombre, dirección SNIES, latitud, longitud, nota)
# Coordenadas APROXIMADAS ubicadas a mano a partir de la dirección del SNIES
# (el geocodificador oficial de IDECA requiere clave API).
SEDES_MANUALES = [
    ("FUNDACION ESCUELA COLOMBIANA DE HOTELERIA Y TURISMO", "AUTOPISTA NORTE 106 63",
     4.6926, -74.0557, "aproximada"),
    ("FUNDACION UNIVERSIDAD DE AMERICA", "AVENIDA CIRCUNVALAR 20 53",
     4.6011, -74.0635, "aproximada"),
    ("POLITECNICO GRANCOLOMBIANO", "CL 57 3 00 ESTE",
     4.6406, -74.0571, "aproximada"),
    ("UNIVERSIDAD ESCUELA COLOMBIANA DE INGENIERIA JULIO GARAVITO", "AUTOPISTA NORTE KM 13",
     4.7826, -74.0424, "aproximada"),
    ("UNIVERSITARIA AGUSTINIANA - UNIAGUSTINIANA", "AV CIUDAD DE CALI 11 B 95",
     4.6445, -74.1565, "aproximada"),
    ("CORPORACION UNIVERSITARIA TALLER CINCO", "AUTOPISTA NORTE KM 19 (VIA A CHIA)",
     4.8270, -74.0386, "aproximada; fuera del perímetro urbano de Bogotá"),
    ("ESCUELA MILITAR DE CADETES GENERAL JOSE MARIA CORDOVA", "CL 80 38 00 (AVENIDA SUBA)",
     4.6868, -74.0700, "aproximada"),
    ("ESCUELA DE INGENIEROS MILITARES", "KR 50 18 06 PUENTE ARANDA",
     4.6295, -74.1060, "aproximada"),
]


def normalizar_nombre(nombre):
    """Mayúsculas sin tildes ni espacios repetidos, para agrupar por nombre."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", nombre or "")
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.upper().split())


def sedes_snies(features):
    """Sedes activas del SNIES con coordenadas: [{"nombre", "x", "y", "fuente"}]."""
    sedes = []
    for f in features:
        props, geom = f["properties"], f.get("geometry")
        coords = (geom or {}).get("coordinates") or []
        if props.get("ESTADO") == "00" or len(coords) < 2:
            continue
        sedes.append({"nombre": props.get("NOMBRE", ""), "x": coords[0], "y": coords[1],
                      "fuente": "SNIES"})
    return sedes


def sedes_manuales(tabla=None):
    """Sedes escritas a mano, convertidas a EPSG:9377."""
    tabla = SEDES_MANUALES if tabla is None else tabla
    sedes = []
    for nombre, _direccion, lat, lon, _nota in tabla:
        x, y = wgs84_a_ctm12(lon, lat)
        sedes.append({"nombre": nombre, "x": x, "y": y, "fuente": "manual"})
    return sedes


def campus_pot(features):
    """Agrupa los predios del POT en sedes.

    Predios con el mismo nombre (normalizado) y centroides a menos de
    `DISTANCIA_MISMA_SEDE_M` se unen en una sede, ubicada en el centroide
    ponderado por área. Devuelve [{"nombre", "x", "y", "fuente", "geometrias"}].
    """
    grupos = []
    for f in features:
        geom = f.get("geometry")
        if not geom:
            continue
        nombre = normalizar_nombre(f["properties"].get("NOMBRE"))
        cx, cy = centroide(geom)
        a = area(geom)
        for g in grupos:
            if g["nombre"] == nombre and distancia((cx, cy), (g["x"], g["y"])) < DISTANCIA_MISMA_SEDE_M:
                total = g["area"] + a
                if total > 0:
                    g["x"] = (g["x"] * g["area"] + cx * a) / total
                    g["y"] = (g["y"] * g["area"] + cy * a) / total
                g["area"] = total
                g["geometrias"].append(geom)
                break
        else:
            grupos.append({"nombre": nombre, "x": cx, "y": cy, "area": a,
                           "fuente": "POT", "geometrias": [geom]})
    for g in grupos:
        del g["area"]
    return grupos


def unificar(snies, campus, manuales):
    """Todas las sedes, sin contar dos veces un punto que cae dentro de un campus."""
    def dentro_de_campus(sede):
        return any(
            punto_en_poligono(sede["x"], sede["y"], geom)
            for c in campus for geom in c["geometrias"]
        )

    puntos = [s for s in snies + manuales if not dentro_de_campus(s)]
    return [{k: c[k] for k in ("nombre", "x", "y", "fuente")} for c in campus] + puntos


def construir_sedes(features_snies, features_pot, tabla_manual=None):
    """Lista final de sedes a partir de las dos capas y la tabla manual."""
    return unificar(sedes_snies(features_snies), campus_pot(features_pot),
                    sedes_manuales(tabla_manual))


def cercania(centro, sedes, radio=RADIO_M):
    """(sedes a <= radio del centro, distancia en m a la más cercana o None)."""
    distancias = [distancia(centro, (s["x"], s["y"])) for s in sedes]
    cercanas = sum(1 for d in distancias if d <= radio)
    return cercanas, (min(distancias) if distancias else None)
