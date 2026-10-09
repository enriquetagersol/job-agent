"""Single skill list, sources and persistent suggestion decisions."""

import hashlib
import json

def normalize(text):
    return " ".join(text.split()).casefold()


def evidence_fingerprint(field, entry_id, quote):
    return hashlib.sha256(json.dumps([field, entry_id, normalize(quote)], ensure_ascii=False).encode()).hexdigest()


def record_rejection(profile, skill, source):
    field = source.get("campo", "")
    identifier = source.get("entrada_id", "")
    if not field and identifier:
        field = next((c for c in ("experiencias", "formacion", "proyectos") if any(e["id"] == identifier for e in profile.get(c, []))), "")
    entry = next((e for e in profile.get(field, []) if e["id"] == identifier), {})
    keys = {"experiencias": ("responsabilidades", "logros", "herramientas"), "formacion": ("contenidos", "proyectos"),
              "proyectos": ("descripcion", "contribucion", "herramientas")}.get(field, ())
    text = "\n".join(entry.get(k, "").strip() for k in keys if entry.get(k, "").strip())
    decision = {"skill": normalize(skill), "evidencia": evidence_fingerprint(
        field, identifier, source.get("cita", "")), "contexto": evidence_fingerprint(field, identifier, text)}
    items = profile.setdefault("skills_rechazadas", [])
    if decision not in items:
        items.append(decision)


def sources_for_skill(profile, skill):
    origin = profile.get("origen_skills", {}).get(skill, {})
    return origin.get("fuentes", [origin] if origin else [])


def remove_skill(profile, skill):
    sources = sources_for_skill(profile, skill)
    for source in sources:
        record_rejection(profile, skill, source)
        if source.get("skill_original"):
            record_rejection(profile, source["skill_original"], source)
    if not any(f.get("entrada_id") for f in sources):
        for field in ("experiencias", "formacion", "proyectos"):
            for entry in profile.get(field, []):
                record_rejection(profile, skill, {"campo": field, "entrada_id": entry["id"]})
    file_path = profile.setdefault("archivo_fuentes_skills", {}).setdefault(skill, [])
    for source in sources:
        if source not in file_path:
            file_path.append(source)
    profile["skills"] = [s for s in profile["skills"] if normalize(s) != normalize(skill)]
    profile["origen_skills"].pop(skill, None)


def possible_equivalence(skill, existing):
    groups = ({"project management", "gestion de proyectos", "gestión de proyectos"},
              {"communication", "comunicación", "comunicacion"},
              {"artificial intelligence", "inteligencia artificial", "ia", "ai"},
              {"machine learning", "aprendizaje automático", "aprendizaje automatico"})
    for group in groups:
        if normalize(skill) in group:
            return next((s for s in existing if normalize(s) in group), None)
    return None


def add_source(profile, skill, source):
    sources = sources_for_skill(profile, skill)
    if source not in sources:
        sources.append(source)
    profile["origen_skills"][skill] = {"tipo": sources[0].get("tipo", "Declaración confirmada") if len(sources) == 1 else "Fuentes múltiples", "fuentes": sources}
