"""Diagnóstico por códigos y contadores; nunca guarda texto, URLs ni perfiles."""

from datos_locales import BASE, guardar_json

CODIGOS = {
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


def evento_seguro(categoria, mensaje):
    categoria = categoria if categoria in ("progreso", "descartada", "inaccesible", "error_tecnico") else "otro"
    return {"categoria": categoria, "codigo": CODIGOS.get(mensaje, categoria)}


def guardar_diagnostico(resultado):
    # Lista explícita: nunca se serializa el resultado ni excepciones completas.
    datos = {"fecha": resultado["fecha"], "error": resultado["error"],
             "llamadas": resultado["llamadas"], "eventos": resultado["eventos"],
             "metricas": resultado["metricas"]}
    try:
        guardar_json(BASE / ".datos" / "diagnostico.json", datos)
    except OSError:
        pass
