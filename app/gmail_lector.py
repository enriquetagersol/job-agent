"""Lee los correos de la etiqueta «JOB SEARCH» de Gmail con permiso de SOLO LECTURA (gmail.readonly).
Lo usa el agente de Slack («revisa mi correo»). Nunca envía, borra ni modifica nada.

Credenciales (fuera del proyecto): el cliente OAuth de tipo «App de escritorio» y el token de acceso
se guardan en el Llavero de macOS. Conectar (una vez): «Conectar Gmail.command», o
  .venv/bin/python -I app/gmail_lector.py --autorizar ~/Downloads/client_secret_….json
Probar:  .venv/bin/python -I app/gmail_lector.py --probar
"""
import base64
import datetime as _dt
import hashlib
import html
import json
import os
import re
import secrets
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datos  # noqa: E402

ETIQUETA = "JOB SEARCH"
ALCANCE = "https://www.googleapis.com/auth/gmail.readonly"
API = "https://gmail.googleapis.com/gmail/v1/users/me/"
LLAVERO_CLIENTE = "job-agent-gmail-cliente"
LLAVERO_TOKEN = "job-agent-gmail-token"
F_CORREO = os.path.join(datos.DIR_DATOS, "correo_estado.json")
MAX_TEXTO = 4000
_cache = {"token": None, "caduca": 0}


def _ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


# ---------- Llavero ----------

def _llavero_leer(servicio):
    if sys.platform != "darwin":
        return os.environ.get(servicio.upper().replace("-", "_"))
    r = subprocess.run(["security", "find-generic-password", "-s", servicio, "-w"],
                       capture_output=True, text=True, timeout=10)
    return r.stdout.strip() or None


def _llavero_guardar(servicio, valor):
    subprocess.run(["security", "delete-generic-password", "-s", servicio], capture_output=True, timeout=10)
    r = subprocess.run(["security", "add-generic-password", "-s", servicio, "-a", "gmail", "-w", valor],
                       capture_output=True, text=True, timeout=10)
    if r.returncode:
        raise RuntimeError("No se pudo guardar en el Llavero.")


def _cliente():
    t = _llavero_leer(LLAVERO_CLIENTE)
    return json.loads(t)["installed"] if t else None


def disponibilidad():
    if not _cliente():
        return False, "Gmail no está conectado: doble clic en «Conectar Gmail.command»."
    if not _llavero_leer(LLAVERO_TOKEN):
        return False, "Falta autorizar Gmail: doble clic en «Conectar Gmail.command»."
    return True, ""


# ---------- OAuth (app de escritorio, redirección a 127.0.0.1 con PKCE) ----------

def _post(url, campos):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(campos).encode(), method="POST")
    with urllib.request.urlopen(req, context=_ssl(), timeout=30) as r:
        return json.load(r)


def autorizar(ruta_cliente):
    d = json.load(open(os.path.expanduser(ruta_cliente), encoding="utf-8"))
    if "installed" not in d:
        raise SystemExit("Ese archivo no es de un cliente «App de escritorio». Crea uno de ese tipo en Google Cloud.")
    c = d["installed"]
    verificador = secrets.token_urlsafe(64)
    reto = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    estado = secrets.token_urlsafe(24)
    recibido = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" not in q and "error" not in q:
                self.send_response(404); self.end_headers(); return
            recibido.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>Listo. Ya puedes cerrar esta pestaña y volver a Job Agent.</h2>".encode())

    srv = HTTPServer(("127.0.0.1", 0), H)
    redir = f"http://127.0.0.1:{srv.server_port}"
    url = c["auth_uri"] + "?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": redir, "response_type": "code", "scope": ALCANCE,
        "access_type": "offline", "prompt": "consent", "state": estado,
        "code_challenge": reto, "code_challenge_method": "S256"})
    print("Se abrirá el navegador para que autorices a Job Agent a LEER tu Gmail…")
    webbrowser.open(url)
    srv.timeout = 300
    while not recibido:
        srv.handle_request()
    srv.server_close()
    if recibido.get("state") != estado or "code" not in recibido:
        raise SystemExit(f"No se completó la autorización ({recibido.get('error', 'respuesta no válida')}).")
    tok = _post(c["token_uri"], {"code": recibido["code"], "client_id": c["client_id"],
                                 "client_secret": c.get("client_secret", ""), "redirect_uri": redir,
                                 "grant_type": "authorization_code", "code_verifier": verificador})
    if "refresh_token" not in tok:
        raise SystemExit("Google no devolvió un token de larga duración. Vuelve a intentarlo.")
    if ALCANCE not in tok.get("scope", ""):
        raise SystemExit("No se concedió el permiso de lectura de Gmail.")
    _llavero_guardar(LLAVERO_CLIENTE, json.dumps(d))
    _llavero_guardar(LLAVERO_TOKEN, tok["refresh_token"])
    print("✅ Gmail conectado (solo lectura).")


def _token():
    if _cache["token"] and time.time() < _cache["caduca"] - 60:
        return _cache["token"]
    c, refresco = _cliente(), _llavero_leer(LLAVERO_TOKEN)
    if not (c and refresco):
        raise RuntimeError(disponibilidad()[1])
    try:
        t = _post(c["token_uri"], {"client_id": c["client_id"], "client_secret": c.get("client_secret", ""),
                                   "refresh_token": refresco, "grant_type": "refresh_token"})
    except urllib.error.HTTPError as e:
        if e.code in (400, 401):
            raise RuntimeError("Google ha caducado el permiso de Gmail: vuelve a «Conectar Gmail.command».")
        raise
    _cache.update(token=t["access_token"], caduca=time.time() + t.get("expires_in", 3600))
    return _cache["token"]


def _api(ruta, **params):
    q = urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(API + ruta + ("?" + q if q else ""),
                                 headers={"Authorization": f"Bearer {_token()}"})
    with urllib.request.urlopen(req, context=_ssl(), timeout=30) as r:
        return json.load(r)


# ---------- lectura ----------

def _texto(parte):
    """Texto del mensaje: text/plain si existe; si no, el HTML sin etiquetas."""
    planos, htmls = [], []

    def recorrer(p):
        mime, cuerpo = p.get("mimeType", ""), (p.get("body") or {}).get("data")
        if cuerpo and mime == "text/plain":
            planos.append(base64.urlsafe_b64decode(cuerpo + "==").decode("utf-8", "ignore"))
        elif cuerpo and mime == "text/html":
            htmls.append(base64.urlsafe_b64decode(cuerpo + "==").decode("utf-8", "ignore"))
        for h in p.get("parts") or []:
            recorrer(h)

    recorrer(parte)
    if planos:
        t = "\n".join(planos)
    else:
        t = re.sub(r"(?is)<(script|style).*?</\1>", " ", "\n".join(htmls))
        t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"\n\s*>.*", "", t)  # quita citas de respuestas anteriores
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", t)).strip()[:MAX_TEXTO]


def ultima_revision():
    return datos._leer(F_CORREO, {}).get("ultima_revision")


def marcar_revision():
    with datos._lock:
        e = datos._leer(F_CORREO, {})
        e["ultima_revision"] = _dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
        datos._escribir(F_CORREO, e)


def correos(desde=None, maximo=30):
    """Correos de la etiqueta JOB SEARCH recibidos desde `desde` (ISO; por defecto la última revisión)."""
    desde = desde or ultima_revision() or (_dt.date.today() - _dt.timedelta(days=7)).isoformat()
    inicio = _dt.datetime.fromisoformat(desde.replace("Z", "+00:00"))
    if inicio.tzinfo is None:
        inicio = inicio.astimezone()
    etiqueta = next((l for l in _api("labels")["labels"] if l["name"].lower() == ETIQUETA.lower()), None)
    if etiqueta is None:
        raise RuntimeError(f"No encuentro la etiqueta «{ETIQUETA}» en Gmail.")
    ids, pagina = [], None
    while len(ids) < maximo:
        r = _api("messages", labelIds=etiqueta["id"], q=f"after:{int(inicio.timestamp()) - 86400}",
                 maxResults=min(50, maximo), **({"pageToken": pagina} if pagina else {}))
        ids += [m["id"] for m in r.get("messages", [])]
        pagina = r.get("nextPageToken")
        if not pagina:
            break
    salida = []
    for mid in ids[:maximo]:
        m = _api(f"messages/{mid}", format="full")
        fecha = _dt.datetime.fromtimestamp(int(m["internalDate"]) / 1000).astimezone()
        if fecha < inicio:
            continue
        cab = {h["name"].lower(): h["value"] for h in m["payload"].get("headers", [])}
        salida.append({"fecha": fecha.strftime("%Y-%m-%d %H:%M"), "de": cab.get("from", ""), "para": cab.get("to", ""),
                       "asunto": cab.get("subject", ""), "enviado_por_ella": "SENT" in m.get("labelIds", []),
                       "texto": _texto(m["payload"])})
    return sorted(salida, key=lambda c: c["fecha"]), desde


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--autorizar":
        autorizar(sys.argv[2])
    elif sys.argv[1:] == ["--probar"]:
        cs, desde = correos(maximo=10)
        print(f"{len(cs)} correo(s) en «{ETIQUETA}» desde {desde}:")
        for c in cs:
            print(f"  {c['fecha']} · {c['asunto'][:70]}")
    else:
        print(__doc__)
