"""Capa de datos de Job Agent: única fuente de verdad para candidaturas y ofertas.

La usan el servidor web (app/servidor.py), la CLI del agente (app/cli.py) y, en el futuro,
cualquier versión completa de la app. Guarda JSON en datos/ con escritura atómica.

Modelo
------
Candidatura: id, empresa, puesto, url, estado, detalle, contacto, fecha_aplicacion,
    fecha_actualizacion, proximo_paso {fecha, texto} | None, cv_adaptado, oferta_id,
    eventos [{fecha, tipo: "estado"|"nota", texto}]
Oferta: id, url, empresa, puesto, encaje, estado_analisis ("recomendada"|"descartada"|
    "no verificada"), motivo_descarte, fecha_analisis, informe, datos, sencillo {que_harias,
    que_piden, que_ofrecen, por_que_encaja, gaps, candidatura}, puntuacion, rasgos [],
    decision {valor, motivo, fecha, aprendida} | None, candidatura_id
"""
import datetime as _dt
import json
import os
import tempfile
import threading

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_DATOS = os.path.join(RAIZ, "datos")
F_CAND = os.path.join(DIR_DATOS, "candidaturas.json")
F_OFER = os.path.join(DIR_DATOS, "ofertas.json")
F_PREF = os.path.join(RAIZ, "perfil", "preferencias.json")
F_BUSQ = os.path.join(DIR_DATOS, "busqueda.json")
CAMPOS_PREF = {"puestos": list, "ubicaciones": list, "mudarme_a": list, "modalidad": str,
               "salario_minimo": int, "salario_objetivo": int, "sectores": list, "valoro": list,
               "evitar": list, "descarto": list, "frases": dict}

# Categorías fijas de los campos que la persona describe con sus palabras (las traduce
# app/preferencias_ia.py). Etiquetas cortas: son las que ve en la app y las que usa el análisis.
CATALOGOS = {
    "sectores": ["IA", "SaaS B2B", "Empresa de producto", "Consumo y marketplaces", "Fintech", "Datos y cloud",
                 "Ciberseguridad", "Salud", "Movilidad", "Legaltech", "Educación", "Energía", "Retail",
                 "Sector público", "Startups", "Big tech"],
    "valoro": ["Ownership", "Aprendizaje técnico", "Impacto visible", "Flexibilidad", "Buen sueldo", "Equity",
               "Proyección internacional", "Estabilidad", "Buen equipo", "Mentoría", "Crecimiento rápido",
               "Propósito"],
    "evitar": ["PMO / coordinación", "Solo reporting", "Muchos viajes", "Mucha presencialidad", "Cuota de ventas",
               "Programar en producción", "Soporte técnico", "Rol muy junior", "Empresa muy grande",
               "Startup muy temprana", "Guardias o turnos"],
    "descarto": ["Consultoras", "PMO puro", "Venta con cuota", "Salario bajo el mínimo", "Media jornada",
                 "Otro idioma", "Prácticas o becas", "Freelance", "Presencial 100 %", "Fuera de mis ubicaciones"],
}

ESTADOS = ["por_aplicar", "enviada", "en_proceso", "oferta", "rechazada", "retirada"]
ETIQUETAS_ESTADO = {"por_aplicar": "Por aplicar", "enviada": "Enviada", "en_proceso": "En proceso",
                    "oferta": "Oferta", "rechazada": "Rechazada", "retirada": "Retirada"}
DECISIONES = ["interesa", "no interesa"]
# Etapas que ve la persona en "Mis candidaturas" (agrupan los estados internos)
ETAPAS = [
    {"id": "por_aplicar", "nombre": "Por aplicar", "estados": ["por_aplicar"]},
    {"id": "aplicada", "nombre": "Aplicada", "estados": ["enviada"]},
    {"id": "entrevistas", "nombre": "Entrevistas", "estados": ["en_proceso"]},
    {"id": "oferta", "nombre": "Oferta", "estados": ["oferta"]},
    {"id": "cerrada", "nombre": "Cerradas", "estados": ["rechazada", "retirada"]},
]
ACTIVOS = {"enviada", "en_proceso"}
DIAS_SIN_NOVEDAD = 14

_lock = threading.Lock()


def hoy():
    return _dt.date.today().isoformat()


def _leer(ruta, vacio):
    if not os.path.exists(ruta):
        return vacio
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _escribir(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ruta), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def _siguiente_id(items, prefijo):
    n = max((int(i["id"][len(prefijo):]) for i in items if i["id"].startswith(prefijo)), default=0)
    return f"{prefijo}{n + 1:03d}"


def _norm_url(u):
    return (u or "").strip().rstrip("/")


# ---------- lectura ----------

def cargar():
    with _lock:
        c = _leer(F_CAND, {"candidaturas": [], "lecturas": []})
        o = _leer(F_OFER, {"ofertas": []})
    return c, o


def candidaturas():
    return cargar()[0]["candidaturas"]


def ofertas():
    return cargar()[1]["ofertas"]


# ---------- candidaturas ----------

def crear_candidatura(empresa, puesto, estado="por_aplicar", **campos):
    if estado not in ESTADOS:
        raise ValueError(f"estado inválido: {estado}")
    with _lock:
        doc = _leer(F_CAND, {"candidaturas": [], "lecturas": []})
        c = {"id": _siguiente_id(doc["candidaturas"], "c"), "empresa": empresa, "puesto": puesto,
             "url": "", "estado": estado, "detalle": "", "contacto": "", "fecha_aplicacion": None,
             "fecha_actualizacion": hoy(), "proximo_paso": None, "cv_adaptado": "",
             "oferta_id": None, "eventos": [{"fecha": hoy(), "tipo": "estado",
                                             "texto": f"Creada como {ETIQUETAS_ESTADO[estado]}"}]}
        c.update({k: v for k, v in campos.items() if k in c and k not in ("id", "eventos")})
        if estado == "enviada" and not c["fecha_aplicacion"]:
            c["fecha_aplicacion"] = hoy()
        doc["candidaturas"].append(c)
        _escribir(F_CAND, doc)
        return c


CAMPOS_EXTRA = {"cv_trabajo", "prioridad", "descripcion"}  # campos opcionales que pueden no existir en candidaturas antiguas


def info_oferta(c):
    """(enlace, descripción, oferta) con lo que se sabe del puesto de una candidatura."""
    oferta = next((o for o in ofertas() if o["id"] == c.get("oferta_id")), None)
    url = c.get("url") if (c.get("url") or "").startswith("http") else ((oferta or {}).get("url") if ((oferta or {}).get("url") or "").startswith("http") else "")
    desc = c.get("descripcion") or (oferta or {}).get("descripcion") or ""
    return url, desc, oferta


def puede_generar_cv(c):
    """Solo se generan CVs para candidaturas que interesan y aún no se han enviado. Basta con el enlace, la
    descripción del puesto o el análisis de la oferta."""
    if c["estado"] != "por_aplicar":
        return False, "Solo para candidaturas en «Por aplicar» (las que te interesan)."
    url, desc, oferta = info_oferta(c)
    if not (url or desc or (oferta or {}).get("sencillo")):
        return False, "Necesito el enlace a la oferta o su descripción (puedes pegarla en Slack)."
    if (c.get("cv_trabajo") or {}).get("estado") == "generando":
        return False, "Ya se está generando."
    return True, ""


def _fecha_valida(f):
    try:
        d = _dt.date.fromisoformat(f)
    except (TypeError, ValueError):
        raise ValueError(f"fecha inválida: {f}")
    if d > _dt.date.today():
        raise ValueError("La fecha de una novedad no puede ser futura.")
    return d.isoformat()


def actualizar_candidatura(cid, nota=None, tocar_fecha=True, fecha_nota=None, origen=None,
                           corregir_fecha_novedad=None, **campos):
    """Actualiza campos. Si cambia el estado, registra un evento. `nota` añade un evento de nota.
    `fecha_nota`: fecha real de la novedad (por defecto hoy); fecha los eventos y la «última novedad».
    `origen`: de dónde viene la novedad (p. ej. "correo"). `corregir_fecha_novedad`: cambia la fecha de la
    última novedad ya apuntada (sin añadir otra).
    `tocar_fecha=False` no cambia fecha_actualizacion (para cambios internos de la app)."""
    cuando = _fecha_valida(fecha_nota) if fecha_nota else hoy()
    if campos.get("fecha_actualizacion"):
        campos["fecha_actualizacion"] = _fecha_valida(campos["fecha_actualizacion"])
        tocar_fecha = False
    with _lock:
        doc = _leer(F_CAND, {"candidaturas": [], "lecturas": []})
        c = next((x for x in doc["candidaturas"] if x["id"] == cid), None)
        if c is None:
            raise KeyError(cid)
        nuevo = campos.get("estado")
        if nuevo is not None and nuevo not in ESTADOS:
            raise ValueError(f"estado inválido: {nuevo}")
        if nuevo and nuevo != c["estado"]:
            c["eventos"].append({"fecha": cuando, "tipo": "estado",
                                 "texto": f"{ETIQUETAS_ESTADO[c['estado']]} → {ETIQUETAS_ESTADO[nuevo]}"})
            if nuevo == "enviada" and not c.get("fecha_aplicacion"):
                c["fecha_aplicacion"] = cuando
        for k, v in campos.items():
            if (k in c or k in CAMPOS_EXTRA) and k not in ("id", "eventos"):
                c[k] = v
        if nota:
            c["eventos"].append({"fecha": cuando, "tipo": "nota", "texto": nota, **({"origen": origen} if origen else {})})
        if corregir_fecha_novedad and c["eventos"]:
            c["eventos"][-1]["fecha"] = _fecha_valida(corregir_fecha_novedad)
            c["fecha_actualizacion"] = c["eventos"][-1]["fecha"]
            tocar_fecha = False
        c["eventos"].sort(key=lambda e: e.get("fecha") or "")  # una novedad con fecha pasada va en su sitio
        if tocar_fecha:  # la última novedad no retrocede al apuntar algo antiguo
            c["fecha_actualizacion"] = max(cuando, c.get("fecha_actualizacion") or "")
        _escribir(F_CAND, doc)
        return c


def ordenar_candidaturas(ids):
    """Guarda el orden de prioridad que la persona ha dado arrastrando en la tabla (0 = más prioritaria)."""
    pos = {cid: i for i, cid in enumerate(ids)}
    with _lock:
        doc = _leer(F_CAND, {"candidaturas": [], "lecturas": []})
        for c in doc["candidaturas"]:
            if c["id"] in pos:
                c["prioridad"] = pos[c["id"]]
        _escribir(F_CAND, doc)


def borrar_candidatura(cid):
    with _lock:
        doc = _leer(F_CAND, {"candidaturas": [], "lecturas": []})
        doc["candidaturas"] = [x for x in doc["candidaturas"] if x["id"] != cid]
        _escribir(F_CAND, doc)
    with _lock:
        od = _leer(F_OFER, {"ofertas": []})
        for o in od["ofertas"]:
            if o.get("candidatura_id") == cid:
                o["candidatura_id"] = None
        _escribir(F_OFER, od)


# ---------- ofertas ----------

def importar_ofertas(nuevas, informe=""):
    """Añade o actualiza ofertas (clave: URL). Devuelve (añadidas, actualizadas).
    Cada importación es un «lote»: las ofertas añadidas en el último lote se marcan como nuevas."""
    lote = _dt.datetime.now().isoformat(timespec="seconds")
    with _lock:
        doc = _leer(F_OFER, {"ofertas": []})
        por_url = {_norm_url(o["url"]): o for o in doc["ofertas"]}
        anad = act = 0
        for n in nuevas:
            u = _norm_url(n.get("url"))
            if u and u in por_url:
                o = por_url[u]
                for k, v in n.items():
                    if k not in ("id", "decision", "candidatura_id") and v not in (None, "", [], {}):
                        o[k] = v
                act += 1
            else:
                o = {"id": _siguiente_id(doc["ofertas"], "o"), "url": n.get("url", ""), "empresa": "",
                     "puesto": "", "encaje": None, "estado_analisis": "recomendada", "motivo_descarte": "",
                     "fecha_analisis": hoy(), "informe": informe, "datos": "", "empresa_desc": "", "descripcion": "", "sencillo": {},
                     "puntuacion": "", "rasgos": [], "decision": None, "candidatura_id": None, "lote": lote}
                o.update({k: v for k, v in n.items() if k in o and k != "id"})
                doc["ofertas"].append(o)
                if u:
                    por_url[u] = o
                anad += 1
        if anad:
            doc["ultimo_lote"] = lote
        _escribir(F_OFER, doc)
        return anad, act


def decidir_oferta(oid, valor, motivo=""):
    """Registra la decisión (Sí = 'interesa' / No = 'no interesa'). 'interesa' crea una candidatura
    'por aplicar' si la oferta no tenía ya una enlazada."""
    if valor not in DECISIONES:
        raise ValueError(f"decisión inválida: {valor}")
    with _lock:
        doc = _leer(F_OFER, {"ofertas": []})
        o = next((x for x in doc["ofertas"] if x["id"] == oid), None)
        if o is None:
            raise KeyError(oid)
        o["decision"] = {"valor": valor, "motivo": motivo, "fecha": hoy(), "aprendida": False}
        o.pop("nota_previa", None)
        _escribir(F_OFER, doc)
    if valor == "no interesa" and o.get("candidatura_id"):
        # Si la tenía guardada y aún no la había enviado, la candidatura pasa a retirada.
        c = next((x for x in candidaturas() if x["id"] == o["candidatura_id"]), None)
        if c and c["estado"] == "por_aplicar":
            actualizar_candidatura(c["id"], estado="retirada", nota="Ya no le interesa")
    if valor == "interesa" and not o.get("candidatura_id"):
        c = crear_candidatura(o["empresa"], o["puesto"], estado="por_aplicar",
                              url=o["url"] if (o["url"] or "").startswith("http") else "", oferta_id=o["id"],
                              detalle=f"Desde ofertas (encaje {o.get('encaje')})")
        with _lock:
            doc = _leer(F_OFER, {"ofertas": []})
            for x in doc["ofertas"]:
                if x["id"] == oid:
                    x["candidatura_id"] = c["id"]
                    o = x
            _escribir(F_OFER, doc)
    return o


def marcar_decisiones_aprendidas(ids):
    with _lock:
        doc = _leer(F_OFER, {"ofertas": []})
        for o in doc["ofertas"]:
            if o["id"] in ids and o.get("decision"):
                o["decision"]["aprendida"] = True
        _escribir(F_OFER, doc)


# ---------- preferencias editables (las usa la búsqueda de la app y mandan sobre preferencias.md) ----------

def preferencias():
    vacio = {list: [], int: 0, str: "", dict: {}}
    p = _leer(F_PREF, {k: vacio[t] for k, t in CAMPOS_PREF.items()})
    p.setdefault("frases", {})
    return p


def guardar_preferencias(nuevas):
    p = preferencias()
    for k, t in CAMPOS_PREF.items():
        if k not in nuevas:
            continue
        v = nuevas[k]
        if t is list:
            if not isinstance(v, list):
                raise ValueError(f"{k} debe ser una lista")
            v = [str(x).strip() for x in v if str(x).strip()]
            if k in CATALOGOS:  # solo categorías del catálogo, en su orden
                v = [c for c in CATALOGOS[k] if c in v]
        elif t is dict:
            if not isinstance(v, dict):
                raise ValueError(f"{k} debe ser un objeto")
            v = {c: [str(x).strip() for x in fr if str(x).strip()][-10:] for c, fr in v.items() if c in CATALOGOS}
        elif t is int:
            v = int(v or 0)
        else:
            v = str(v or "").strip()
        p[k] = v
    p["actualizado"] = hoy()
    with _lock:
        _escribir(F_PREF, p)
    return p


# ---------- estado de la búsqueda lanzada desde la app ----------

def estado_busqueda():
    return _leer(F_BUSQ, {"estado": "inactivo"})


def guardar_estado_busqueda(e):
    with _lock:
        _escribir(F_BUSQ, e)


# ---------- vistas derivadas ----------

def _dias_desde(fecha):
    try:
        return (_dt.date.today() - _dt.date.fromisoformat(fecha)).days
    except (TypeError, ValueError):
        return None


def seguimiento():
    cs = candidaturas()
    sin_novedad = []
    for c in cs:
        d = _dias_desde(c.get("fecha_actualizacion"))
        if c["estado"] in ACTIVOS and (d is None or d >= DIAS_SIN_NOVEDAD):
            sin_novedad.append({**c, "dias": d})
    sin_novedad.sort(key=lambda c: -(c["dias"] if c["dias"] is not None else 9999))
    proximos = sorted([c for c in cs if c.get("proximo_paso") and c["proximo_paso"].get("texto")],
                      key=lambda c: c["proximo_paso"].get("fecha") or "9999")
    por_aplicar = [c for c in cs if c["estado"] == "por_aplicar"]
    return {"sin_novedad": sin_novedad, "proximos": proximos, "por_aplicar": por_aplicar,
            "umbral_dias": DIAS_SIN_NOVEDAD}


def metricas():
    cs = candidaturas()
    os_ = ofertas()
    por_estado = {e: sum(1 for c in cs if c["estado"] == e) for e in ESTADOS}
    aplicadas = [c for c in cs if c["estado"] != "por_aplicar"]
    con_respuesta = [c for c in aplicadas if c["estado"] in ("en_proceso", "oferta", "rechazada")]
    entrevista = [c for c in aplicadas if c["estado"] in ("en_proceso", "oferta")
                  or "entrevista" in (c.get("detalle") or "").lower()]
    decisiones = {d: sum(1 for o in os_ if (o.get("decision") or {}).get("valor") == d) for d in DECISIONES}
    rechazos = [{"empresa": c["empresa"], "puesto": c["puesto"], "detalle": c.get("detalle", "")}
                for c in cs if c["estado"] == "rechazada"]
    return {
        "por_estado": por_estado,
        "total_aplicadas": len(aplicadas),
        "con_respuesta": len(con_respuesta),
        "tasa_respuesta": round(100 * len(con_respuesta) / len(aplicadas)) if aplicadas else 0,
        "llegan_a_entrevista": len(entrevista),
        "ofertas_analizadas": len(os_),
        "ofertas_recomendadas": sum(1 for o in os_ if o.get("estado_analisis") == "recomendada"),
        "pendientes_decidir": sum(1 for o in os_ if o.get("estado_analisis") == "recomendada"
                                  and not o.get("decision")),
        "decisiones": decisiones,
        "decisiones_sin_aprender": sum(1 for o in os_ if (o.get("decision") or {}).get("aprendida") is False),
        "rechazos": rechazos,
        "lecturas": cargar()[0].get("lecturas", []),
    }


def estado_completo():
    c, o = cargar()
    return {"candidaturas": c["candidaturas"], "ofertas": o["ofertas"], "seguimiento": seguimiento(),
            "metricas": metricas(), "estados": ESTADOS, "etiquetas_estado": ETIQUETAS_ESTADO, "etapas": ETAPAS,
            "preferencias": preferencias(), "catalogos": CATALOGOS, "busqueda": estado_busqueda(),
            "decisiones": DECISIONES, "hoy": hoy(), "ultimo_lote": o.get("ultimo_lote")}
