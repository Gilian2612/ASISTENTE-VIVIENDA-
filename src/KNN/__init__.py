# Marca la carpeta KNN/ como un paquete de Python, para poder hacer
# `from KNN.knn import recomendar` (usado por tests/ y por coverage con --cov=KNN).
# Se ejecuta una sola vez, al importar el paquete. Se deja vacío a propósito:
# si se quisiera exponer atajos, se haría aquí, p. ej.
#     from .knn import recomendar
#     __all__ = ["recomendar"]
