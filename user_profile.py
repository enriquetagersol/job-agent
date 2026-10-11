"""Profile editing without external calls or inferences about the user."""

import copy
import re
import unicodedata
from career_history import ensure_career_defaults, validate_entry

PREFERENCES = ("Baja", "Media", "Alta")
WORK_MODES = ("Presencial", "Híbrido", "Remoto")
EXPERIENCE_OPTIONS = ("Sin especificar", "Sin experiencia", "<1 año", "1–3 años", "4–6 años", ">6 años")
LANGUAGE_LEVELS = ("Básico", "Intermedio", "Alto", "Nativo/bilingüe")
CURRENCIES = ("EUR", "GBP", "USD", "CAD", "CHF", "MXN", "ARS", "COP", "CLP", "BRL")


def normalize_identity(text):
    text = " ".join(text.split()).casefold()
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def add_option(options, text, limit=None):
    text = " ".join(text.split())
    if not text:
        raise ValueError("La opción no puede estar vacía.")
    if normalize_identity(text) in {normalize_identity(o) for o in options}:
        raise ValueError("Esa opción ya está añadida.")
    if limit is not None and len(options) >= limit:
        raise ValueError(f"Ya has añadido el máximo de {limit} opciones.")
    return [*options, text]


def remove_option(options, text):
    return [o for o in options if normalize_identity(o) != normalize_identity(text)]


def migrate_profile(previous):
    """Preserve legacy data; migrate only explicit equivalents."""
    if previous.get("version_perfil") == 3:
        profile = copy.deepcopy(previous)
        profile.setdefault("empresa_actual", "")
        profile.setdefault("excluir_empresa_actual", False)
        return ensure_career_defaults(profile)
    target_roles = [previous["puesto"]] if str(previous.get("puesto", "")).strip() else []
    locations = [{"nombre": previous["ubicacion"], "preferencia": None}] if str(previous.get("ubicacion", "")).strip() else []
    skills = [previous["capacidades"]] if str(previous.get("capacidades", "")).strip() else []
    experience = previous.get("experiencia_profesional", "")
    if experience not in EXPERIENCE_OPTIONS:
        match = re.fullmatch(r"\s*(\d+)\s*años?\s*", experience, re.IGNORECASE)
        if match:
            years = int(match[1])
            experience = "Sin experiencia" if years == 0 else "1–3 años" if years <= 3 else "4–6 años" if years <= 6 else ">6 años"
        else:
            experience = "Sin especificar"
    mode = previous.get("modalidad", previous.get("preferencias_laborales", ""))
    modes = {m: None for m in WORK_MODES if normalize_identity(m) == normalize_identity(mode)}
    return ensure_career_defaults({"version_perfil": 3, "puestos_objetivo": target_roles, "ubicaciones": locations,
            "modalidades": modes, "skills": skills, "idiomas": [],
            "experiencia": experience, "salario_minimo": None, "moneda": None,
            "importancia_ubicacion": None, "importancia_modalidad": None,
            "importancia_salario": None, "que_buscas": "",
            "empresa_actual": previous.get("empresa_actual", ""),
            "excluir_empresa_actual": previous.get("excluir_empresa_actual", False),
            "datos_anteriores": copy.deepcopy(previous)})


def validate_profile(profile, previous=None):
    companies = []
    for company in profile.get("companies_of_interest", []):
        companies = add_option(companies, company)
    for field in ("experiencias", "formacion", "proyectos"):
        ids = set()
        for entry in profile.get(field, []):
            old_entry = next((e for e in (previous or {}).get(field, []) if e.get("id") == entry.get("id")), None)
            if entry != old_entry:
                validate_entry(field, entry)
            if entry["id"] in ids:
                raise ValueError("Entrada de trayectoria duplicada.")
            ids.add(entry["id"])
    if not isinstance(profile.get("empresa_actual", ""), str) or not isinstance(profile.get("excluir_empresa_actual", False), bool):
        raise ValueError("Empresa actual o exclusión inválida.")
    for field, limit in (("puestos_objetivo", 5), ("skills", 10)):
        options = []
        for value in profile[field]:
            options = add_option(options, value, limit)
    options = []
    for location in profile["ubicaciones"]:
        options = add_option(options, location["nombre"], 5)
        if location["preferencia"] is not None and location["preferencia"] not in PREFERENCES:
            raise ValueError("Preferencia de ubicación inválida.")
    for mode, preference in profile["modalidades"].items():
        if mode not in WORK_MODES or (preference is not None and preference not in PREFERENCES):
            raise ValueError("Modalidad o preferencia inválida.")
    options = []
    for language in profile["idiomas"]:
        options = add_option(options, language["idioma"])
        if language["nivel"] is not None and language["nivel"] not in LANGUAGE_LEVELS:
            raise ValueError("Nivel de idioma inválido.")
    minimum = profile["salario_minimo"]
    if minimum is not None and (isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or minimum < 0):
        raise ValueError("El salario mínimo debe ser no negativo o estar sin especificar.")
    if (profile["moneda"] is not None and profile["moneda"] not in CURRENCIES) or profile["experiencia"] not in EXPERIENCE_OPTIONS:
        raise ValueError("Moneda o experiencia inválida.")
    for field in ("importancia_ubicacion", "importancia_modalidad", "importancia_salario"):
        if profile[field] is not None and profile[field] not in PREFERENCES:
            raise ValueError("Importancia inválida.")
    if len(profile["que_buscas"]) > 400:
        raise ValueError("¿Qué buscas? admite un máximo de 400 caracteres.")
    return profile


def profile_for_model(profile):
    profile = migrate_profile(profile)
    # Do not send unknown fields or legacy preferences replaced by the user.
    confirmed = {field: copy.deepcopy(profile[field]) for field in
        ("skills", "idiomas", "experiencia")}
    confirmed["aclaraciones"] = copy.deepcopy(profile.get("respuestas_confirmadas", {}))
    for field in ("experiencias", "formacion", "proyectos", "origen_skills"):
        confirmed[field] = copy.deepcopy(profile[field])
    previous = profile.get("datos_anteriores", {})
    if profile["experiencia"] == "Sin especificar" and previous.get("experiencia_profesional"):
        confirmed["experiencia_detalle_confirmado"] = previous["experiencia_profesional"]
    preferences = {field: copy.deepcopy(profile[field]) for field in
        ("puestos_objetivo", "ubicaciones", "modalidades", "salario_minimo", "moneda",
         "importancia_ubicacion", "importancia_modalidad", "importancia_salario", "que_buscas")}
    preferences["conversation_preferences"] = copy.deepcopy(profile.get("conversation_preferences", []))
    preferences["companies_of_interest"] = copy.deepcopy(profile["companies_of_interest"])
    return {"confirmado": confirmed, "preferencias": preferences}


def employer_is_excluded(company, current_employer):
    def normalize(name):
        words = re.findall(r"\w+", normalize_identity(name))
        legal_suffixes = {"ltd", "limited", "inc", "incorporated", "llc", "plc", "sa", "sl", "corp", "corporation"}
        while words and words[-1] in legal_suffixes:
            words.pop()
        return " ".join(words)
    current = normalize(current_employer)
    return bool(current) and normalize(company) == current
