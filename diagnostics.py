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


def record_chat_event(tool, code, error_type=None):
    """Record only allowlisted technical metadata, never arguments or exceptions."""
    from datetime import datetime, timezone
    from local_storage import read_json
    tools = {'remember_search_preference', 'forget_search_preference', 'add_company_interest', 'remove_company_interest', 'search_jobs', 'get_recommendations'}
    codes = {'success', 'action_rejected', 'invalid_arguments', 'persistence_error', 'conversation_error'}
    errors = {'ValueError', 'ValidationError', 'JSONDecodeError', 'OSError', 'PermissionError',
              'FileNotFoundError', 'APIError', 'APIConnectionError', 'AuthenticationError',
              'RateLimitError', 'BadRequestError', 'APITimeoutError'}
    path = BASE_DIR / '.local_data' / 'chat_diagnostics.json'
    event = {'date': datetime.now(timezone.utc).isoformat(),
             'tool': tool if tool in tools else 'other', 'code': code if code in codes else 'other',
             'error_type': error_type if error_type in errors else None}
    try:
        previous = read_json(path, [])
        save_json(path, [*(previous if isinstance(previous, list) else [])[-49:], event])
    except (OSError, ValueError):
        pass
