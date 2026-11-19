"""Tipo de uso predominante de cada UPZ (HARDCODEADO).

La capa oficial de UPZ no publica el tipo. El POT (Decreto 190 de 2004)
clasifica las UPZ en 8 tipos; aquí solo se marcan las que importan para el
recomendador:

- "industrial": predominantemente industrial (tipo 8 del POT).
- "dotacional": grandes equipamientos o parques (tipo 7): poca o ninguna
  vivienda.
- "residencial": todas las demás (residenciales, comerciales, centralidades,
  en desarrollo). Es el valor por defecto.

`verificado` indica si la clasificación tiene una fuente citada; las demás
son por conocimiento del territorio y deben confirmarse con la SDP.
"""

INDUSTRIAL = "industrial"
DOTACIONAL = "dotacional"
RESIDENCIAL = "residencial"

# codigo_upz: (tipo, verificado, fuente)
TIPOS_UPZ = {
    # Predominantemente industrial
    "108": (INDUSTRIAL, True, "Decreto 62 de 2007 (reglamenta UPZ 108 Zona Industrial)"),
    "111": (INDUSTRIAL, True, "Decreto 62 de 2007 (reglamenta UPZ 111 Puente Aranda)"),
    "76": (INDUSTRIAL, True, "Alcaldía Local de Fontibón: UPZ predominantemente industrial"),
    "77": (INDUSTRIAL, True, "Alcaldía Local de Fontibón: UPZ predominantemente industrial"),
    "112": (INDUSTRIAL, True, "IDIGER, caracterización Fontibón: UPZ predominantemente industrial"),
    # Predominantemente dotacional (parques metropolitanos y grandes equipamientos)
    "60": (DOTACIONAL, False, "Parque Entrenubes (por verificar)"),
    "63": (DOTACIONAL, False, "Relleno Doña Juana / El Mochuelo (por verificar)"),
    "103": (DOTACIONAL, False, "Parque Salitre (por verificar)"),
    "104": (DOTACIONAL, False, "Parque Simón Bolívar - CAN (por verificar)"),
    "105": (DOTACIONAL, False, "Jardín Botánico (por verificar)"),
    "117": (DOTACIONAL, False, "Aeropuerto El Dorado (por verificar)"),
}


def tipo_de(codigo_upz):
    """Tipo de la UPZ; "residencial" si no está en la tabla."""
    return TIPOS_UPZ.get(str(codigo_upz), (RESIDENCIAL, False, ""))[0]
