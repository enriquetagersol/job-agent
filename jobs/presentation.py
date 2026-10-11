"""Turn validated offer evaluations into reader-facing explanations. Separate interest, qualification and confirmed gaps, while preparing private vacancy follow-up topics independently of user questions."""

from jobs.evaluation import CRITERIA
from profiles.user_profile import employer_is_excluded
import re


def reader_reason(criterion):
    """Do not expose legacy comparison blocks or internal validation messages."""
    reason = criterion.reason.strip()
    if re.search(r"(?:Descripción|Oferta|Perfil)\s*:|evidencia verificable en ambos lados", reason, re.I):
        return ""
    if any(reason == quote.strip() for quote in criterion.listing_evidence_quotes):
        return ""
    return reason


def explain_listing(listing, separate_user=False, profile=None):
    sections = {"interes": [], "cumplidos": [], "parciales": [], "gaps": [], "pendientes": []}
    company = next((company for company in (profile or {}).get("companies_of_interest", [])
                    if employer_is_excluded(listing.company, company)), None)
    if company:
        sections["interes"].append(f"{listing.company} está entre las empresas donde te interesa trabajar. Los requisitos del puesto se valoran por separado.")
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
        reason = reader_reason(c)
        if c.points == "Sin datos":
            if separate_user:
                from profiles.profile_improvement import is_user_question
                if is_user_question(c, profile or {}):
                    continue
                if c.name in ("experiencia", "capacidades"):
                    sections["pendientes"].append("¿Qué experiencia y conocimientos exige la empresa para estas tareas? Falta precisarlo en la descripción.")
                    continue
            sections["pendientes"].append(questions[c.name] if separate_user else
                reason if "¿" in reason else questions[c.name])
        elif c.name == "capacidades" and c.declared_skills:
            if reason:
                sections["parciales"].append(reason)
            if not separate_user:
                sections["pendientes"].append("¿Qué proyectos o tareas has realizado con " + ", ".join(c.declared_skills) + "?")
        elif (c.name == "puesto" and c.points in (1, 2)) or (
                c.name in ("ubicacion", "modalidad", "salario") and c.compatibility in ("Compatible", "Parcial")):
            if reason:
                sections["interes"].append(reason)
        elif c.points == 2:
            if reason:
                sections["cumplidos"].append(reason)
        elif c.points == 1:
            if reason:
                sections["parciales"].append(reason)
        elif c.points == 0:
            if reason:
                sections["gaps"].append(reason)
    # Legacy free-text gaps mixed missing data and shortcomings. Only
    # criteria with evidence and an explicit mismatch produce gaps.
    sections["pendientes"].append("¿Sigue abierta esta vacante? Su actividad no está confirmada.")
    return {s: list(dict.fromkeys(lines)) for s, lines in sections.items()}


def vacancy_follow_up(listing, profile):
    """Private vacancy topics for future application records, never profile facts.

    Rebuilt from the current evaluation on each save, so verified new evidence
    replaces stale unknowns. User questions remain in profile improvement.
    """
    from profiles.profile_improvement import is_user_question
    return {
        "url": listing.url,
        "unknown_criteria": [c.name for c in listing.criteria
                             if c.points == "Sin datos" and not is_user_question(c, profile)],
        "questions": explain_listing(listing, separate_user=True, profile=profile)["pendientes"],
    }
