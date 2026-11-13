"""Fichas de los puestos a los que ha aplicado (pestaña Ofertas → «Aplicadas»): qué haría, por qué encaja y por qué no.

Si una candidatura aplicada no tiene ficha, Job Agent busca la oferta en la web por puesto y empresa (o analiza la
descripción que haya pegado) una sola vez; si no la encuentra, lo apunta y ella puede corregir el puesto o pegar la
descripción. También se puede volver a buscar a mano (p. ej. para reaplicar).
Completar a mano:  .venv/bin/python -I app/fichas_puestos.py
"""
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datos  # noqa: E402
import cv_ia  # noqa: E402

APLICADA = ("enviada", "en_proceso", "oferta", "rechazada")
_lock = threading.Lock()
buscando = set()  # candidaturas cuya oferta se está buscando ahora (la app lo enseña en la tarjeta)


def es_aplicada(c):
    return c["estado"] in APLICADA or bool(c.get("fecha_aplicacion"))


def analizar(cid, cambios=None, solo_guardar=False):
    """Guarda lo que ella haya corregido (empresa, puesto, enlace, descripción) y, salvo `solo_guardar`, busca la
    oferta en la web o analiza la descripción, y la une a la candidatura. Si no la encuentra, lo apunta."""
    import correo_ia
    if not any(x["id"] == cid for x in datos.candidaturas()):
        raise KeyError(cid)
    cambios = {k: str(v).strip() for k, v in (cambios or {}).items() if k in ("empresa", "puesto", "url", "descripcion")}
    if cambios.get("empresa") == "" or cambios.get("puesto") == "":
        raise ValueError("La empresa y el puesto no pueden quedar vacíos.")
    if cambios:
        datos.actualizar_candidatura(cid, tocar_fecha=False, ficha_no_encontrada=None, **cambios)
    if solo_guardar:
        return None
    c = next(x for x in datos.candidaturas() if x["id"] == cid)
    buscando.add(cid)
    try:
        o = correo_ia.investigar_oferta(url=c.get("url") or "", empresa=c["empresa"], puesto=c["puesto"],
                                        texto=c.get("descripcion") or "")
    except ValueError:
        datos.actualizar_candidatura(cid, tocar_fecha=False, ficha_no_encontrada=datos.hoy())
        raise
    finally:
        buscando.discard(cid)
    datos.enlazar_oferta(cid, o["id"])
    datos.actualizar_candidatura(cid, tocar_fecha=False, ficha_no_encontrada=None)
    return o


def pendientes():
    """Aplicadas sin ficha que aún no se han intentado buscar."""
    con_ficha = {o["id"] for o in datos.ofertas() if o.get("sencillo")}
    return [c for c in datos.candidaturas()
            if es_aplicada(c) and c.get("oferta_id") not in con_ficha and not c.get("ficha_no_encontrada")]


def completar():
    """Busca la ficha de las aplicadas que no la tienen (una vez cada una). Devuelve cuántas ha encontrado."""
    if not datos.ajuste("fichas_puestos") or not cv_ia.disponibilidad()[0] or not _lock.acquire(blocking=False):
        return 0
    try:
        def una(c):
            try:
                return analizar(c["id"]) is not None
            except Exception:  # noqa: BLE001 - no encontrada o error: queda apuntado y no se reintenta solo
                return False
        with ThreadPoolExecutor(max_workers=3) as ex:
            return sum(ex.map(una, pendientes()))
    finally:
        _lock.release()


def completar_en_segundo_plano():
    if datos.ajuste("fichas_puestos") and pendientes():
        threading.Thread(target=completar, daemon=True).start()


if __name__ == "__main__":
    print(f"Fichas encontradas: {completar()}")
