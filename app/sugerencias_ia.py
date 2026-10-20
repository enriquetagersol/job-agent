"""Sugiere el próximo paso de cada candidatura (Claude; sin API key, unas reglas sencillas).

Se recalcula cuando se apunta una novedad (en la app, por Slack o desde el correo) salvo que esa misma
actualización ya traiga un próximo paso concreto. La sugerencia se guarda en proximo_paso con
"sugerido": true; si la persona lo edita, pasa a ser suyo.
"""
import datetime as _dt
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import datos
import cv_ia

CERRADOS = {"rechazada", "retirada"}

SISTEMA = """Eres Job Agent. Propones el PRÓXIMO PASO de una candidatura de empleo de la persona: una acción \
concreta que puede hacer la persona, en español, en imperativo y en menos de 70 caracteres (p. ej. «Follow-up al \
recruiter si no responde», «Preparar la entrevista con el CTO», «Enviar nota de agradecimiento»).

Criterios:
- Básate solo en los datos de la candidatura (etapa, fechas, notas). No inventes hechos, nombres ni citas.
- Si ya hay un próximo paso con fecha futura que sigue siendo válido (p. ej. una entrevista fijada), mantenlo.
- Fecha (AAAA-MM-DD, hoy es <hoy>): la de un evento ya fijado en las notas, o la recomendable para actuar: \
follow-up unos 7 días después de aplicar o de la última respuesta sin novedad; nota de agradecimiento el día \
siguiente a una entrevista; preparar una entrevista 1-2 días antes. Nunca una fecha pasada: si ya toca, hoy.
- «Por aplicar»: preparar el CV y enviar la candidatura. «Oferta»: lo que toque para negociar o responder.
- Si no hay nada útil que hacer, devuelve texto vacío."""

ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["texto", "fecha"],
           "properties": {"texto": {"type": "string"}, "fecha": {"type": "string"}}}


def _resumen(c):
    return {"empresa": c["empresa"], "puesto": c["puesto"], "etapa": datos.ETIQUETAS_ESTADO[c["estado"]],
            "detalle": c.get("detalle"), "contacto": c.get("contacto"), "fecha_aplicacion": c.get("fecha_aplicacion"),
            "ultima_novedad": c.get("fecha_actualizacion"), "proximo_paso_actual": c.get("proximo_paso"),
            "cv_adaptado_listo": bool(c.get("cv_adaptado")), "historial": c.get("eventos", [])[-8:]}


def _reglas(c):
    hoy = _dt.date.today()
    base = _dt.date.fromisoformat(c.get("fecha_actualizacion") or hoy.isoformat())
    fecha = lambda d: max(hoy, base + _dt.timedelta(days=d)).isoformat()  # noqa: E731
    if c["estado"] == "por_aplicar":
        return {"texto": "Enviar la candidatura" if c.get("cv_adaptado") else "Preparar el CV y enviar la candidatura",
                "fecha": hoy.isoformat()}
    if c["estado"] == "enviada":
        return {"texto": "Hacer follow-up si no hay respuesta", "fecha": fecha(7)}
    if c["estado"] == "en_proceso":
        return {"texto": "Pedir actualización sobre el proceso", "fecha": fecha(7)}
    if c["estado"] == "oferta":
        return {"texto": "Responder a la oferta", "fecha": fecha(3)}
    return None


def _claude(cliente, c):
    r = cliente.beta.messages.create(
        model=cv_ia.MODELO, max_tokens=1500,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        system=SISTEMA.replace("<hoy>", datos.hoy()),
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
        messages=[{"role": "user", "content": json.dumps(_resumen(c), ensure_ascii=False)}],
    )
    t = [b.text for b in r.content if b.type == "text"]
    if r.stop_reason == "refusal" or not t:
        return _reglas(c)
    s = json.loads(t[-1])
    if not s["texto"].strip():
        return None
    try:
        f = max(_dt.date.fromisoformat(s["fecha"]), _dt.date.today()).isoformat()
    except ValueError:
        f = ""
    return {"texto": s["texto"].strip()[:90], "fecha": f}


def _cliente():
    if not cv_ia.disponibilidad()[0]:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=cv_ia._api_key(), max_retries=2)


def sugerir(cid, cliente=None):
    """Calcula y guarda la sugerencia para una candidatura. Devuelve el próximo paso guardado."""
    c = next((x for x in datos.candidaturas() if x["id"] == cid), None)
    if c is None:
        return None
    if c["estado"] in CERRADOS:
        s = None
    else:
        cliente = cliente or _cliente()
        try:
            s = _claude(cliente, c) if cliente else _reglas(c)
        except Exception:  # noqa: BLE001 - si falla la API, una sugerencia sencilla
            s = _reglas(c)
    paso = {**s, "sugerido": True} if s else None
    datos.actualizar_candidatura(cid, tocar_fecha=False, proximo_paso=paso)
    return paso


def sugerir_en_segundo_plano(cid):
    threading.Thread(target=sugerir, args=(cid,), daemon=True).start()


def sugerir_todas():
    """Recalcula las sugerencias de todas las candidaturas abiertas (en paralelo)."""
    cliente = _cliente()
    ids = [c["id"] for c in datos.candidaturas() if c["estado"] not in CERRADOS]
    with ThreadPoolExecutor(max_workers=5) as ex:
        return dict(zip(ids, ex.map(lambda i: sugerir(i, cliente), ids)))


def hay_novedad(campos, nota):
    """¿Esta actualización es una novedad que pide recalcular el próximo paso?"""
    return bool(nota or campos.get("estado")) and "proximo_paso" not in campos
