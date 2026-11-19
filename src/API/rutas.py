"""Lógica de las rutas de la API, separada del servidor para poder probarla sin red.

Cada ruta recibe un dict con los parámetros de la query string y devuelve un
dict serializable a JSON. Los parámetros inválidos lanzan `ErrorParametros`
(el servidor responde 400).
"""
from KNN import knn

# ¿Buscas que sea zona industrial?  sí / no / sin preferencia
VALORES_INDUSTRIAL = {"si": True, "no": False, "": None}

PRESUPUESTO_MAXIMO = 10_000_000_000


class ErrorParametros(ValueError):
    """Parámetro faltante o fuera de rango."""


def _entero(params, nombre, minimo, maximo, defecto=None):
    valor = params.get(nombre, "")
    if valor == "":
        if defecto is None:
            raise ErrorParametros(f"Falta el parámetro '{nombre}'")
        return defecto
    try:
        numero = int(valor)
    except ValueError:
        raise ErrorParametros(f"'{nombre}' debe ser un número entero") from None
    if not minimo <= numero <= maximo:
        raise ErrorParametros(f"'{nombre}' debe estar entre {minimo} y {maximo}")
    return numero


def leer_perfil(params):
    """Valida la query y devuelve (importancias, presupuesto, k, industrial)."""
    importancias = [_entero(params, v, 1, 5) for v in knn.VARIABLES]
    presupuesto = _entero(params, "presupuesto", 0, PRESUPUESTO_MAXIMO)
    k = _entero(params, "k", 1, max(len(knn.ZONAS), 1), defecto=3)
    industrial = params.get("industrial", "").strip().lower()
    if industrial not in VALORES_INDUSTRIAL:
        raise ErrorParametros("'industrial' debe ser 'si', 'no' o vacío (sin preferencia)")
    return importancias, presupuesto, k, VALORES_INDUSTRIAL[industrial]


def zonas(_params=None):
    """GET /api/zonas: todas las zonas con sus variables normalizadas."""
    lista = []
    for nombre, (vector, arriendo) in knn.ZONAS.items():
        meta = knn.METADATOS.get(nombre, {})
        lista.append({
            "nombre": nombre,
            "codigo_upz": meta.get("codigo_upz", ""),
            "localidad": knn.formato_nombre(meta.get("localidad", "")),
            "tipo": meta.get("tipo", "residencial"),
            "arriendo": arriendo,
            "norm": dict(zip(knn.VARIABLES, vector)),
        })
    return {
        "variables": knn.VARIABLES,
        "provisionales": knn.VARIABLES_PROVISIONALES,
        "zonas": lista,
    }


def recomendar(params):
    """GET /api/recomendar?transporte=..&seguridad=..&precio=..&universidades=..
    &verdes=..&presupuesto=..[&k=3][&industrial=si|no]"""
    importancias, presupuesto, k, industrial = leer_perfil(params)
    resultados = knn.recomendar(importancias, presupuesto, k=k, industrial=industrial)
    return {
        "resultados": [
            {
                "nombre": nombre,
                "codigo_upz": knn.METADATOS.get(nombre, {}).get("codigo_upz", ""),
                "similitud": similitud,
            }
            for nombre, similitud in resultados
        ]
    }


RUTAS = {
    "/api/zonas": zonas,
    "/api/recomendar": recomendar,
}
