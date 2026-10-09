"""Explanations without scores or internal validation messages."""

from evaluation import CRITERIA


def explain_listing(listing, separate_user=False, profile=None):
    sections = {"interes": [], "cumplidos": [], "parciales": [], "gaps": [], "pendientes": []}
    questions = {
        "capacidades": "¿Cómo has aplicado los conocimientos que pide este puesto en proyectos o trabajo real?",
        "experiencia": "¿Has construido soluciones, gestionado proyectos o trabajado con clientes en un contexto parecido al de este puesto?",
        "idiomas": "¿Qué idiomas y niveles exige esta oferta? Falta confirmarlo en la publicación.",
        "ubicacion": "¿La ubicación de la oferta es compatible con los lugares donde quieres trabajar?",
        "modalidad": "¿Qué modalidad ofrece la empresa y cómo se ajusta a tus preferencias?",
        "salario": "¿Cuál es el salario bruto anual y en qué moneda? Falta información comparable con tu mínimo.",
        "puesto": f"¿Las funciones de {listing.role} corresponden al tipo de trabajo que buscas?",
    }
    for c in listing.criteria:
        if c.points == "Sin datos":
            if separate_user:
                from profile_improvement import is_user_question
                if is_user_question(c, profile or {}):
                    continue
                if c.name in ("experiencia", "capacidades"):
                    sections["pendientes"].append("¿Qué experiencia y conocimientos exige la empresa para estas tareas? Falta precisarlo en la descripción.")
                    continue
            sections["pendientes"].append(questions[c.name] if separate_user else
                c.reason if "¿" in c.reason else questions[c.name])
        elif c.name == "capacidades" and c.declared_skills:
            sections["parciales"].append(c.reason)
            if not separate_user:
                sections["pendientes"].append("¿Qué proyectos o tareas has realizado con " + ", ".join(c.declared_skills) + "?")
        elif (c.name == "puesto" and c.points in (1, 2)) or (
                c.name in ("ubicacion", "modalidad", "salario") and c.compatibility in ("Compatible", "Parcial")):
            sections["interes"].append(c.reason)
        elif c.points == 2:
            sections["cumplidos"].append(c.reason)
        elif c.points == 1:
            sections["parciales"].append(c.reason)
        elif c.points == 0:
            sections["gaps"].append(c.reason)
    # Legacy free-text gaps mixed missing data and shortcomings. Only
    # criteria with evidence and an explicit mismatch produce gaps.
    sections["pendientes"].append("¿Sigue abierta esta vacante? Su actividad no está confirmada.")
    return {s: list(dict.fromkeys(lines)) for s, lines in sections.items()}
