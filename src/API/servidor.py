"""Servidor HTTP local: sirve el front (src/FRONT) y la API (/api/...).

Uso:  cd src && python3 -m API.servidor [puerto]     (por defecto 8000)
Luego abrir http://localhost:8000
"""
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from API import rutas

CARPETA_FRONT = Path(__file__).resolve().parents[1] / "FRONT"
PUERTO_POR_DEFECTO = 8000


class Manejador(SimpleHTTPRequestHandler):
    """Rutas /api/* en JSON; todo lo demás, archivos estáticos de FRONT."""

    silencioso = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(CARPETA_FRONT), **kwargs)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path.startswith("/api/"):
            self._api(url)
        else:
            super().do_GET()

    def _api(self, url):
        ruta = rutas.RUTAS.get(url.path)
        if ruta is None:
            self._json(404, {"error": f"Ruta no encontrada: {url.path}"})
            return
        params = dict(parse_qsl(url.query, keep_blank_values=True))
        try:
            cuerpo = ruta(params)
        except rutas.ErrorParametros as e:
            self._json(400, {"error": str(e)})
            return
        except rutas.ErrorNoDisponible as e:
            self._json(404, {"error": str(e)})
            return
        self._json(200, cuerpo)

    def _json(self, estado, cuerpo):
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, formato, *args):
        if not self.silencioso:  # pragma: no cover - solo imprime en consola
            super().log_message(formato, *args)


def crear_servidor(host="127.0.0.1", puerto=PUERTO_POR_DEFECTO):
    return ThreadingHTTPServer((host, puerto), Manejador)


def main(argv=None):  # pragma: no cover - bucle bloqueante
    argv = sys.argv[1:] if argv is None else argv
    puerto = int(argv[0]) if argv else PUERTO_POR_DEFECTO
    servidor = crear_servidor(puerto=puerto)
    print(f"Sirviendo en http://localhost:{puerto}  (Ctrl+C para detener)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        servidor.server_close()


if __name__ == "__main__":  # pragma: no cover
    main()
