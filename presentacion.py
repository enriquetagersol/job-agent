"""Explicaciones sin puntuaciones ni mensajes internos de validación."""

from evaluacion import CRITERIOS


def explicar_oferta(oferta, separar_usuario=False, perfil=None):
    secciones = {"interes": [], "cumplidos": [], "parciales": [], "gaps": [], "pendientes": []}
    preguntas = {
        "capacidades": "¿Cómo has aplicado los conocimientos que pide este puesto en proyectos o trabajo real?",
        "experiencia": "¿Has construido soluciones, gestionado proyectos o trabajado con clientes en un contexto parecido al de este puesto?",
        "idiomas": "¿Qué idiomas y niveles exige esta oferta? Falta confirmarlo en la publicación.",
        "ubicacion": "¿La ubicación de la oferta es compatible con los lugares donde quieres trabajar?",
        "modalidad": "¿Qué modalidad ofrece la empresa y cómo se ajusta a tus preferencias?",
        "salario": "¿Cuál es el salario bruto anual y en qué moneda? Falta información comparable con tu mínimo.",
        "puesto": f"¿Las funciones de {oferta.puesto} corresponden al tipo de trabajo que buscas?",
    }
    for c in oferta.criterios:
        if c.puntos == "Sin datos":
            if separar_usuario:
                from mejoras import pendiente_usuario
                if pendiente_usuario(c, perfil or {}):
                    continue
                if c.nombre in ("experiencia", "capacidades"):
                    secciones["pendientes"].append("¿Qué experiencia y conocimientos exige la empresa para estas tareas? Falta precisarlo en la descripción.")
                    continue
            secciones["pendientes"].append(preguntas[c.nombre] if separar_usuario else
                c.motivo if "¿" in c.motivo else preguntas[c.nombre])
        elif c.nombre == "capacidades" and c.skills_declaradas:
            secciones["parciales"].append(c.motivo)
            if not separar_usuario:
                secciones["pendientes"].append("¿Qué proyectos o tareas has realizado con " + ", ".join(c.skills_declaradas) + "?")
        elif (c.nombre == "puesto" and c.puntos in (1, 2)) or (
                c.nombre in ("ubicacion", "modalidad", "salario") and c.compatibilidad in ("Compatible", "Parcial")):
            secciones["interes"].append(c.motivo)
        elif c.puntos == 2:
            secciones["cumplidos"].append(c.motivo)
        elif c.puntos == 1:
            secciones["parciales"].append(c.motivo)
        elif c.puntos == 0:
            secciones["gaps"].append(c.motivo)
    # Los gaps libres antiguos mezclaban datos ausentes y carencias. Solo los
    # criterios con evidencia y un incumplimiento explícito producen gaps.
    secciones["pendientes"].append("¿Sigue abierta esta vacante? Su actividad no está confirmada.")
    return {s: list(dict.fromkeys(lineas)) for s, lineas in secciones.items()}
