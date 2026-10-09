"""Diagnostics using codes and counters; never store text, URLs or profiles."""

from local_storage import BASE_DIR, save_json

EVENT_CODES = {
    "Enlace sin descripción recuperada": "sin_extraccion",
    "Responsabilidades o requisitos sin evidencia verificable": "evidencia_responsabilidades",
    "Identificación sin respaldo en la descripción": "identificacion",
    "Evaluación incompleta de dimensiones": "dimensiones",
    "Oferta duplicada": "duplicado",
    "Empresa actual excluida": "empresa_excluida",
    "No se pudo recuperar la página": "pagina_inaccesible",
    "Tavily no devolvió contenido para esta página": "sin_contenido",
    "Descripción vacía": "descripcion_vacia",
}


def sanitized_event(category, message):
    category = category if category in ("progreso", "descartada", "inaccesible", "error_tecnico") else "otro"
    return {"categoria": category, "codigo": EVENT_CODES.get(message, category)}


def save_diagnostics(result):
    # Explicit allowlist: never serialize full results or exceptions.
    data = {"fecha": result["fecha"], "error": result["error"],
             "llamadas": result["llamadas"], "eventos": result["eventos"],
             "metricas": result["metricas"]}
    try:
        save_json(BASE_DIR / '.local_data' / 'diagnostics.json', data)
    except OSError:
        pass
