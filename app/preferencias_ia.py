"""Traduce lo que la persona escribe con sus palabras a las categorías fijas de datos.CATALOGOS.

Con API key usa Claude (llamada corta y barata); sin ella, un traductor local por palabras clave.
"""
import json
import re
import unicodedata

import datos
import cv_ia
import modelos

DESCRIPCION = {
    "sectores": "sectores, tipos de empresa o productos que le atraen",
    "valoro": "lo que más valora de un trabajo",
    "evitar": "lo que prefiere evitar en un trabajo (resta, pero no descarta)",
    "descarto": "lo que le haría descartar una oferta sin dudarlo",
}

# Traductor local: palabras clave (sin tildes, en minúsculas) -> categoría
CLAVES = {
    "sectores": {
        "IA": r"\bia\b|inteligencia artificial|\bai\b|llm|agente|machine learning|genai|generativa",
        "SaaS B2B": r"saas|b2b|software para empresas",
        "Empresa de producto": r"producto|tecnologic|\btech\b",
        "Consumo y marketplaces": r"consumo|marketplace|b2c|ocio|entretenimiento|e-?commerce",
        "Fintech": r"fintech|banca|banco|pagos|finanz|seguro",
        "Datos y cloud": r"datos|data|cloud|nube|infraestructura",
        "Ciberseguridad": r"ciberseguridad|seguridad|ciber",
        "Salud": r"salud|health|medic|farma|biotec",
        "Movilidad": r"movilidad|transporte|logistic|coche",
        "Legaltech": r"legal|abogad",
        "Educación": r"educaci|edtech|formaci",
        "Energía": r"energ|sostenib|clima|renovable",
        "Retail": r"retail|tienda|moda",
        "Sector público": r"public|gobierno|administraci",
        "Startups": r"startup|scale.?up|emergente",
        "Big tech": r"big tech|gran tecnologic|google|amazon|microsoft|meta\b|apple",
    },
    "valoro": {
        "Ownership": r"ownership|responsab|autonom|decidir|duen|liderar",
        "Aprendizaje técnico": r"aprend|tecnic|formaci|crecer tecnic",
        "Impacto visible": r"impacto|resultado|ver lo que|se use|se usa|usen|utilic",
        "Flexibilidad": r"flexib|concilia|horario|remoto|teletrabajo",
        "Buen sueldo": r"sueldo|salario|dinero|pagar bien|retribuci",
        "Equity": r"equity|acciones|stock",
        "Proyección internacional": r"internacional|global|extranjero|idiomas",
        "Estabilidad": r"estab|segur|indefinid",
        "Buen equipo": r"equipo|compañer|ambiente|cultura|gente",
        "Mentoría": r"mentor|aprender de|referente|jefe que",
        "Crecimiento rápido": r"crecimiento|promoci|ascen|carrera",
        "Propósito": r"proposito|mision|social|sentido",
    },
    "evitar": {
        "PMO / coordinación": r"pmo|coordinaci|seguimiento|perseguir",
        "Solo reporting": r"reporting|informes|excel|reportar",
        "Muchos viajes": r"viaj",
        "Mucha presencialidad": r"presencial|oficina|desplaz",
        "Cuota de ventas": r"cuota|vender|ventas|comercial",
        "Programar en producción": r"programar|codigo|picar|developer|desarroll",
        "Soporte técnico": r"soporte|ticket|helpdesk",
        "Rol muy junior": r"junior|becari|demasiado basico",
        "Empresa muy grande": r"muy grande|corporaci|burocra|multinacional",
        "Startup muy temprana": r"muy temprana|seed|demasiado pequen|caos",
        "Guardias o turnos": r"guardia|turno|fines de semana|nocturn",
    },
    "descarto": {
        "Consultoras": r"consultor|outsourcing|body ?shopping",
        "PMO puro": r"pmo",
        "Venta con cuota": r"cuota|venta pura|comercial puro",
        "Salario bajo el mínimo": r"salario|sueldo|cobrar menos|por debajo",
        "Media jornada": r"media jornada|jornada parcial|part.?time|jornada completa",
        "Otro idioma": r"idioma|aleman|frances|italiano|neerland",
        "Prácticas o becas": r"practica|beca|intern",
        "Freelance": r"freelance|autonomo",
        "Presencial 100 %": r"100 ?% presencial|totalmente presencial|presencial 100|todos los dias en la oficina",
        "Fuera de mis ubicaciones": r"mudarme|reubica|fuera de madrid|otra ciudad|otro pais",
    },
}


def _normal(t):
    return unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()


def _local(campo, texto):
    t = _normal(texto)
    return [c for c, rx in CLAVES[campo].items() if re.search(rx, t)]


def _claude(campo, texto):
    import anthropic
    cliente = anthropic.Anthropic(api_key=cv_ia._api_key(), max_retries=2)
    opciones = datos.CATALOGOS[campo]
    r = cliente.beta.messages.create(
        model=modelos.para("preferencias"), max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": {
            "type": "object", "additionalProperties": False, "required": ["categorias"],
            "properties": {"categorias": {"type": "array", "items": {"type": "string", "enum": opciones}}}}}},
        system=("Traduces lo que escribe una persona que busca trabajo a categorías de una lista fija. "
                "Elige solo las categorías que lo que dice implica claramente; si nada encaja, devuelve una lista vacía."),
        messages=[{"role": "user", "content": f"Campo: {DESCRIPCION[campo]}.\nCategorías posibles: "
                   f"{', '.join(opciones)}.\n\nLo que ha escrito: «{texto}»"}],
    )
    if r.stop_reason == "refusal":
        return None
    t = [b.text for b in r.content if b.type == "text"]
    return json.loads(t[-1])["categorias"] if t else None


def interpretar(campo, texto):
    if campo not in datos.CATALOGOS:
        raise ValueError("campo no válido")
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Escribe algo")
    if cv_ia.disponibilidad()[0]:
        try:
            cats = _claude(campo, texto)
            if cats is not None:
                return {"categorias": cats, "metodo": "claude"}
        except Exception:  # noqa: BLE001 - si falla la API, usamos el traductor local
            pass
    return {"categorias": _local(campo, texto), "metodo": "local"}
