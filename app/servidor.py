"""Servidor local de Job Agent (solo Python estándar). Sirve la interfaz y una API JSON sobre
app/datos.py. Escucha solo en 127.0.0.1.

Uso: python3 -I app/servidor.py [--puerto 8765] [--abrir]

API
  GET    /api/estado                      todo: candidaturas, ofertas, seguimiento, métricas
  POST   /api/candidaturas                {empresa, puesto, estado?, url?, detalle?, contacto?}
  PATCH  /api/candidaturas/<id>           {campos..., nota?}
  DELETE /api/candidaturas/<id>
  POST   /api/ofertas/<id>/decision       {valor, motivo?}
  POST   /api/candidaturas/<id>/cv        genera un CV adaptado con la API de Claude (en segundo plano)
  PUT    /api/preferencias                guarda las preferencias editables
  POST   /api/preferencias/interpretar    {campo, texto} -> categorías fijas (lenguaje natural)
  POST   /api/cv                          {nombre, datos_b64}: sube el CV y genera perfil + CV maestro
  POST   /api/busqueda                    lanza una búsqueda de ofertas con la API de Claude (en segundo plano)
  GET    /archivo/<ruta>                  PDFs/Markdown de cv/adaptados y resultados (solo lectura)

Para escalar a la app completa, añade aquí rutas como POST /api/buscar o /api/adaptar-cv que
llamen a la API de Claude y escriban con app/datos.py; la interfaz no necesita cambiar.
"""
import argparse, json, mimetypes, os, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datos  # noqa: E402
import cv_ia  # noqa: E402
import busqueda_ia  # noqa: E402
import preferencias_ia  # noqa: E402
import perfil_ia  # noqa: E402
import sugerencias_ia  # noqa: E402
import aprendizaje_ia  # noqa: E402
import fichas_empresas  # noqa: E402

ESTATICOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
ARCHIVOS_PERMITIDOS = [os.path.join(datos.RAIZ, "cv"), os.path.join(datos.RAIZ, "resultados")]
MAX_CUERPO = 16 * 1024 * 1024


class Manejador(BaseHTTPRequestHandler):
    server_version = "JobAgent/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("JOBAGENT_LOG"):
            super().log_message(fmt, *args)

    # ---------- utilidades ----------
    def _json(self, codigo, cuerpo):
        datos_b = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos_b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos_b)

    def _fichero(self, ruta):
        if not os.path.isfile(ruta):
            return self._json(404, {"error": "no encontrado"})
        tipo = mimetypes.guess_type(ruta)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/json"):
            tipo += "; charset=utf-8"
        with open(ruta, "rb") as f:
            cont = f.read()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cont)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cont)

    def _cuerpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_CUERPO:
            raise ValueError("El archivo es demasiado grande.")
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _mismo_origen(self):
        # Evita que otras webs abiertas en el navegador modifiquen los datos.
        origen = self.headers.get("Origin")
        return origen is None or urlparse(origen).hostname in ("127.0.0.1", "localhost")

    def _partes(self):
        return [p for p in urlparse(self.path).path.split("/") if p]

    # ---------- GET ----------
    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta in ("/", "/index.html"):
            return self._fichero(os.path.join(ESTATICOS, "index.html"))
        if ruta.startswith("/static/"):
            destino = os.path.realpath(os.path.join(ESTATICOS, unquote(ruta[len("/static/"):])))
            if not destino.startswith(os.path.realpath(ESTATICOS) + os.sep):
                return self._json(403, {"error": "prohibido"})
            return self._fichero(destino)
        if ruta == "/api/estado":
            ok, motivo = cv_ia.disponibilidad()
            correo = datos._leer(os.path.join(datos.DIR_DATOS, "correo_estado.json"), {})
            return self._json(200, {**datos.estado_completo(), "ia": {"disponible": ok, "motivo": motivo},
                                    "perfil": perfil_ia.estado(), "aviso_correo": correo.get("ofertas_correo", {}),
                                    "cv_general": cv_ia.estado_general(), "empresas": fichas_empresas.para_la_app()})
        if ruta.startswith("/archivo/"):
            destino = os.path.realpath(os.path.join(datos.RAIZ, unquote(ruta[len("/archivo/"):])))
            if not any(destino.startswith(os.path.realpath(p) + os.sep) for p in ARCHIVOS_PERMITIDOS):
                return self._json(403, {"error": "prohibido"})
            return self._fichero(destino)
        return self._json(404, {"error": "no encontrado"})

    # ---------- escritura ----------
    def _escritura(self, fn):
        if not self._mismo_origen():
            return self._json(403, {"error": "origen no permitido"})
        try:
            return self._json(200, fn())
        except KeyError as e:
            return self._json(404, {"error": f"no existe {e}"})
        except (ValueError, json.JSONDecodeError) as e:
            return self._json(400, {"error": str(e)})

    def do_POST(self):
        p = self._partes()
        if p == ["api", "candidaturas"]:
            def crear():
                b = self._cuerpo()
                if not b.get("empresa") or not b.get("puesto"):
                    raise ValueError("empresa y puesto son obligatorios")
                c = datos.crear_candidatura(b.pop("empresa"), b.pop("puesto"), b.pop("estado", "por_aplicar"), **b)
                fichas_empresas.completar_en_segundo_plano()
                return c
            return self._escritura(crear)
        if p == ["api", "candidaturas", "orden"]:
            def ordenar():
                ids = self._cuerpo().get("ids")
                if not isinstance(ids, list):
                    raise ValueError("ids debe ser una lista")
                datos.ordenar_candidaturas([str(i) for i in ids])
                return {"ok": True}
            return self._escritura(ordenar)
        if p == ["api", "cv", "general"]:
            return self._escritura(lambda: (cv_ia.lanzar_general(self._cuerpo().get("idioma")), {"ok": True})[1])
        if p == ["api", "cv", "proponer"]:
            def proponer():
                import maestro_ia
                pr = maestro_ia.proponer(self._cuerpo().get("texto", ""))
                return {**pr, "lineas": maestro_ia.describir(pr)}
            return self._escritura(proponer)
        if p == ["api", "cv", "aplicar"]:
            def aplicar():
                import maestro_ia
                maestro_ia.aplicar(self._cuerpo().get("id", ""))
                return {"ok": True}
            return self._escritura(aplicar)
        if p == ["api", "preferencias", "interpretar"]:
            def interpretar():
                b = self._cuerpo()
                return preferencias_ia.interpretar(b.get("campo"), b.get("texto"))
            return self._escritura(interpretar)
        if p == ["api", "cv"]:
            def subir():
                b = self._cuerpo()
                perfil_ia.recibir(b.get("nombre"), b.get("datos_b64"))
                return {"ok": True}
            return self._escritura(subir)
        if p == ["api", "busqueda"]:
            return self._escritura(lambda: (busqueda_ia.lanzar(), {"ok": True})[1])
        if len(p) == 4 and p[:2] == ["api", "candidaturas"] and p[3] == "cv":
            def lanzar_cv():
                ok, motivo = cv_ia.disponibilidad()
                if not ok:
                    raise ValueError(motivo)
                c = next((x for x in datos.candidaturas() if x["id"] == p[2]), None)
                if c is None:
                    raise KeyError(p[2])
                ok, motivo = datos.puede_generar_cv(c)
                if not ok:
                    raise ValueError(motivo)
                datos.actualizar_candidatura(p[2], tocar_fecha=False,
                                             cv_trabajo={"estado": "generando", "mensaje": ""})
                threading.Thread(target=cv_ia.generar, args=(p[2],), daemon=True).start()
                return {"ok": True, "estado": "generando"}
            return self._escritura(lanzar_cv)
        if len(p) == 4 and p[:2] == ["api", "ofertas"] and p[3] == "decision":
            def decidir():
                b = self._cuerpo()
                o = datos.decidir_oferta(p[2], b.get("valor"), b.get("motivo", ""))
                aprendizaje_ia.programar()  # aprende de la decisión (y su motivo) en un minuto
                fichas_empresas.completar_en_segundo_plano()
                return o
            return self._escritura(decidir)
        return self._json(404, {"error": "no encontrado"})

    def do_PATCH(self):
        p = self._partes()
        if len(p) == 3 and p[:2] == ["api", "candidaturas"]:
            def act():
                b = self._cuerpo()
                nota, fecha_nota = b.pop("nota", None), b.pop("fecha_nota", None)
                corregir = b.pop("corregir_fecha_novedad", None)
                c = datos.actualizar_candidatura(p[2], nota=nota, fecha_nota=fecha_nota,
                                                 corregir_fecha_novedad=corregir, **b)
                if sugerencias_ia.hay_novedad(b, nota):
                    sugerencias_ia.sugerir_en_segundo_plano(p[2])
                if b.get("estado"):
                    fichas_empresas.completar_en_segundo_plano()
                return c
            return self._escritura(act)
        return self._json(404, {"error": "no encontrado"})

    def do_PUT(self):
        if self._partes() == ["api", "preferencias"]:
            return self._escritura(lambda: datos.guardar_preferencias(self._cuerpo()))
        return self._json(404, {"error": "no encontrado"})

    def do_DELETE(self):
        p = self._partes()
        if len(p) == 3 and p[:2] == ["api", "candidaturas"]:
            return self._escritura(lambda: (datos.borrar_candidatura(p[2]), {"ok": True})[1])
        return self._json(404, {"error": "no encontrado"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=int(os.environ.get("PORT", 8765)))
    ap.add_argument("--abrir", action="store_true", help="abre el navegador al arrancar")
    a = ap.parse_args()
    # Un CV que se estaba generando cuando se cerró la app ya no terminará.
    for c in datos.candidaturas():
        if (c.get("cv_trabajo") or {}).get("estado") == "generando":
            datos.actualizar_candidatura(c["id"], tocar_fecha=False, cv_trabajo={
                "estado": "error", "mensaje": "Se interrumpió al cerrar la app. Vuelve a intentarlo."})
    if cv_ia.estado_general().get("estado") == "generando":
        cv_ia._guardar_general(estado="error", mensaje="Se interrumpió al cerrar la app. Vuelve a intentarlo.")
    pe = perfil_ia.estado()
    if pe.get("estado") == "analizando":
        perfil_ia._guardar_estado(estado="error", mensaje="El análisis se interrumpió al cerrar la app. Sube el CV de nuevo.")
    if datos.estado_busqueda().get("estado") == "buscando":
        e = datos.estado_busqueda()
        e.update(estado="error", mensaje="La búsqueda se interrumpió al cerrar la app. Vuelve a lanzarla.")
        datos.guardar_estado_busqueda(e)
    srv = ThreadingHTTPServer(("127.0.0.1", a.puerto), Manejador)
    url = f"http://127.0.0.1:{a.puerto}"
    print(f"Job Agent en {url}  (Ctrl+C para parar)", flush=True)
    try:
        import slack_bot
        print(slack_bot.arrancar(), flush=True)
    except ImportError:
        pass  # sin slack_bolt instalado: la app funciona igual
    # Deja cargado el SDK de Claude para que la primera sugerencia no tarde
    threading.Thread(target=lambda: __import__("anthropic"), daemon=True).start()
    import correo_ia
    correo_ia.vigilar(intervalo=120)
    fichas_empresas.vigilar()  # fichas de las empresas de sus candidaturas activas (pestaña Empresas)  # con Gmail conectado: procesa cada correo nuevo al llegar (mira cada 2 min)
    if a.abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
