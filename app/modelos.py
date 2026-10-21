"""Qué modelo de Claude usa cada tarea, para gastar lo justo.

- Haiku (≈40 veces más barato que Opus): tareas mecánicas o cortas.
- Sonnet (la mitad que Opus): tareas que necesitan criterio (analizar ofertas, CVs, chat).
Para cambiar el modelo de una tarea, cambia aquí su línea.
"""
HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"

TAREAS = {
    # Haiku: clasificar, filtrar, resumir
    "clasificar_correo": HAIKU,
    "criba_titulo": HAIKU,
    "proximo_paso": HAIKU,
    "preferencias": HAIKU,
    "aprendizaje": HAIKU,
    "ficha_empresa": HAIKU,
    "empresa_desc": HAIKU,
    "chat": HAIKU,        # el chat de Slack; lo que hace a fondo (CVs, investigar ofertas) usa su propio modelo
    # Sonnet: criterio y textos que vas a enviar
    "analizar_oferta": SONNET,
    "investigar_oferta": SONNET,
    "cv": SONNET,
    "cv_general": SONNET,
    "perfil": SONNET,
    "cv_maestro": SONNET,
}

# $ por millón de tokens: entrada, salida, escritura de caché, lectura de caché
PRECIOS = {
    HAIKU: {"in": 0.10, "out": 0.50, "cache_w": 0.125, "cache_r": 0.01},
    SONNET: {"in": 2.0, "out": 10.0, "cache_w": 2.5, "cache_r": 0.20},
    OPUS: {"in": 4.0, "out": 20.0, "cache_w": 5.0, "cache_r": 0.20},
}


def para(tarea):
    return TAREAS.get(tarea, SONNET)


def busqueda_web(modelo, max_uses=3, **extra):
    """Herramienta de búsqueda web compatible con el modelo (Haiku usa la versión básica)."""
    tipo = "web_search_20250305" if modelo == HAIKU else "web_search_20260209"
    return {"type": tipo, "name": "web_search", "max_uses": max_uses, **extra}


def lectura_web(modelo, max_uses=3, **extra):
    tipo = "web_fetch_20250910" if modelo == HAIKU else "web_fetch_20260209"
    return {"type": tipo, "name": "web_fetch", "max_uses": max_uses, **extra}


def coste(modelo, uso):
    p = PRECIOS.get(modelo, PRECIOS[SONNET])
    return round(sum(uso.get(k, 0) * p[k] for k in p) / 1e6, 4)
