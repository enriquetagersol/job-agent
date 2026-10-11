"""Shared rules for forms and actions, without external calls."""

import re


def meaningful_text(value):
    return (isinstance(value, str) and value.strip().casefold() not in (
        "sin especificar", "no especificado", "no especificada", "no documentado", "sin datos")
        and bool(re.search(r"\w", value.strip())))


def missing_entry_fields(field, entry):
    required = {"experiencias": (("empresa", "Empresa"), ("puesto", "Puesto"), ("responsabilidades", "Descripción de responsabilidades")),
                  "formacion": (("institucion", "Institución"), ("estudios", "Estudios/titulación")),
                  "proyectos": (("nombre", "Nombre del proyecto"), ("descripcion", "Descripción del proyecto"), ("contribucion", "Contribución personal"))}
    missing_fields = [label for key_name, label in required[field] if not meaningful_text(entry.get(key_name))]
    if field != "proyectos":
        for key_name, label in (("inicio", "Fecha de inicio"), ("fin", "Fecha de fin")):
            if key_name == "fin" and entry.get("actual") is True:
                continue
            date = entry.get(key_name) or {}
            if not isinstance(date, dict):
                date = {}
            if type(date.get("mes")) is not int or not 1 <= date["mes"] <= 12:
                missing_fields.append(label + " · mes")
            if type(date.get("ano")) is not int or not 1 <= date["ano"] <= 9999:
                missing_fields.append(label + " · año")
    return missing_fields


def entry_is_complete(field, entry):
    if missing_entry_fields(field, entry):
        return False
    if field != "proyectos" and not entry.get("actual"):
        start_date, end_date = entry["inicio"], entry["fin"]
        return (end_date["ano"], end_date["mes"]) >= (start_date["ano"], start_date["mes"])
    return True


def has_search_information(profile):
    if "confirmado" in profile:
        confirmed, preferences = profile["confirmado"], profile.get("preferencias", {})
    else:
        confirmed = preferences = profile
    for field, keys in (("experiencias", ("empresa", "puesto", "responsabilidades", "logros", "herramientas")),
                         ("formacion", ("institucion", "estudios", "contenidos", "proyectos")),
                         ("proyectos", ("nombre", "descripcion", "contribucion", "herramientas"))):
        if any(meaningful_text(e.get(k)) for e in confirmed.get(field, []) for k in keys):
            return True
    if any(meaningful_text(s) for s in confirmed.get("skills", [])) or any(meaningful_text(i.get("idioma")) for i in confirmed.get("idiomas", [])):
        return True
    if confirmed.get("experiencia") in ("Sin experiencia", "<1 año", "1–3 años", "4–6 años", ">6 años"):
        return True
    if meaningful_text(confirmed.get("experiencia_detalle_confirmado")):
        return True
    if any(meaningful_text(r.get("respuesta")) for r in confirmed.get("aclaraciones", confirmed.get("respuestas_confirmadas", {})).values()):
        return True
    return (any(meaningful_text(p) for p in preferences.get("conversation_preferences", [])) or
            any(meaningful_text(c) for c in preferences.get("companies_of_interest", [])) or
            meaningful_text(preferences.get("search_company")) or
            meaningful_text(preferences.get("search_location")) or
            any(meaningful_text(p) for p in preferences.get("puestos_objetivo", [])) or
            any(meaningful_text(u.get("nombre")) for u in preferences.get("ubicaciones", [])) or
            any(m in ("Presencial", "Híbrido", "Remoto") and p in (None, "Baja", "Media", "Alta")
                for m, p in preferences.get("modalidades", {}).items()) or
            (type(preferences.get("salario_minimo")) in (int, float) and preferences["salario_minimo"] > 0) or
            meaningful_text(preferences.get("que_buscas")))


def require_search_information(profile):
    if not has_search_information(profile):
        raise ValueError("No hay suficiente información para buscar. Añade información sobre tu trayectoria o lo que buscas")


def missing_cv_fields(profile):
    data = profile.get("datos_cv", {})
    missing_fields = []
    if not meaningful_text(data.get("nombre")):
        missing_fields.append("Nombre")
    if not meaningful_text(data.get("apellidos")):
        missing_fields.append("Apellidos")
    email = data.get("email", "")
    if not isinstance(email, str) or not re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", email.strip()):
        missing_fields.append("Email con formato válido")
    if not any(entry_is_complete(field, e) for field in ("experiencias", "formacion", "proyectos") for e in profile.get(field, [])):
        missing_fields.append("Al menos una experiencia, formación o proyecto completo")
        for field, label in (("experiencias", "Experiencia"), ("formacion", "Formación"), ("proyectos", "Proyecto")):
            for i, entry in enumerate(profile.get(field, []), 1):
                missing_fields.extend(f"{label} {i}: {f}" for f in missing_entry_fields(field, entry))
                if not missing_entry_fields(field, entry) and not entry_is_complete(field, entry):
                    missing_fields.append(f"{label} {i}: fecha de fin anterior al inicio")
    return missing_fields


def require_cv_information(profile):
    missing_fields = missing_cv_fields(profile)
    if missing_fields:
        raise ValueError("Completa los campos obligatorios para generar tu CV: " + "; ".join(missing_fields))
