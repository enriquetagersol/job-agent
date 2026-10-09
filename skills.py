"""Explicit suggestions with sources; never added without confirmation."""

from wire_models import WireModel

import os
import json
from pathlib import Path
from typing import List

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from local_storage import PROFILE_FILE, save_json, read_json
from evaluation import quote_is_documented
from user_profile import add_option, normalize_identity, migrate_profile
from career_history import entry_title
from skill_store import (record_rejection, evidence_fingerprint, normalize, add_source,
                         possible_equivalence)


class SkillSuggestion(WireModel):
    skill: str
    field: str
    entry_id: str
    quote: str


class SkillSuggestions(WireModel):
    suggestions: List[SkillSuggestion]


def skill_sources(profile):
    sources = []
    for field, keys in (("experiencias", ("responsabilidades", "logros", "herramientas")),
                         ("formacion", ("contenidos", "proyectos")),
                         ("proyectos", ("descripcion", "contribucion", "herramientas"))):
        for entry in profile.get(field, []):
            text = "\n".join(entry.get(c, "").strip() for c in keys if entry.get(c, "").strip())
            if text:
                sources.append({"campo": field, "entrada_id": entry["id"], "texto": text})
    return sources


def filter_suggestions(suggestions, sources, existing, rejected=None):
    origins = {(f["campo"], f["entrada_id"]): f["texto"] for f in sources}
    seen = {normalize_identity(s) for s in existing}
    valid = []
    for suggestion in suggestions:
        text = origins.get((suggestion.field, suggestion.entry_id), "")
        fingerprint = evidence_fingerprint(suggestion.field, suggestion.entry_id, suggestion.quote)
        context = evidence_fingerprint(suggestion.field, suggestion.entry_id, text)
        if any((d["evidencia"] == fingerprint or d.get("contexto") == context) and (d["skill"] == normalize(suggestion.skill) or
               possible_equivalence(suggestion.skill, [d["skill"]])) for d in (rejected or [])):
            continue
        if not suggestion.skill.strip() or normalize_identity(suggestion.skill) in seen or not quote_is_documented(suggestion.quote, text):
            continue
        seen.add(normalize_identity(suggestion.skill))
        valid.append(suggestion.model_dump())
    return valid[:10]


def suggest_skills(profile):
    sources = skill_sources(profile)
    if not sources:
        return []
    load_dotenv(Path(__file__).parent / ".env")
    with OpenAI(max_retries=0, timeout=60.0) as model:
        response = model.responses.parse(model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
            instructions="Propón hasta diez skills a partir SOLO de los contenidos o tareas descritos. "
                "No uses títulos, aspiraciones ni preferencias. No asignes dominio ni experiencia. "
                "Aporta una cita literal continua y el campo/entrada_id exactos. La persona debe confirmarlas.",
            input=json.dumps({"fuentes": sources, "skills_existentes": profile["skills"]}, ensure_ascii=False),
            text_format=SkillSuggestions, reasoning={"effort": "none"}, max_output_tokens=1800, store=False)
        if response.status != "completed" or response.output_parsed is None:
            raise ValueError("Propuesta incompleta")
    return filter_suggestions(response.output_parsed.suggestions, sources, profile["skills"], profile.get("skills_rechazadas", []))


def render_suggestions(profile):
    with st.container():
        st.caption("Te sugerimos habilidades basadas en tu trayectoria. Revisa y añade las que te representan")
        if len(profile["skills"]) >= 10:
            st.caption("Has alcanzado el límite de 10 skills confirmadas. Elimina una para añadir otra; las propuestas pendientes no ocupan huecos.")
        sources = skill_sources(profile)
        if not sources:
            st.caption("Describe y guarda las tareas, conocimientos o herramientas de alguna experiencia, estudio o proyecto para proponer skills.")
        if st.button("Proponer skills", disabled=not sources):
            try:
                with st.spinner("Preparando propuestas…"):
                    suggestions = suggest_skills(profile)
                updated = migrate_profile(read_json(PROFILE_FILE, st.session_state.profile))
                updated["skills_propuestas"] = suggestions
                save_json(PROFILE_FILE, updated)
                st.session_state.profile = updated
                st.rerun()
            except Exception:
                st.error("No se pudieron preparar propuestas. El perfil no ha cambiado.")
        pending = filter_suggestions([SkillSuggestion(**p) for p in profile.get("skills_propuestas", [])],
                                       skill_sources(profile), profile["skills"], profile.get("skills_rechazadas", []))
        for p in pending:
            key_name = p["campo"] + p["entrada_id"] + normalize_identity(p["skill"])
            entry = next(e for e in profile[p["campo"]] if e["id"] == p["entrada_id"])
            st.write(p["skill"])
            st.caption("Se propone a partir de " + entry_title(p["campo"], entry) + ": «" + p["cita"] + "»")
            skill = st.text_input("Skill que confirmarás", value=p["skill"], key="skill_propuesta_" + key_name)
            equivalent = possible_equivalence(skill, profile["skills"])
            merge = False
            if equivalent:
                st.caption(f"Podría equivaler a «{equivalent}». Puedes fusionarlas o mantenerlas distintas.")
                merge = st.checkbox("Fusionar con " + equivalent, key="skill_fusionar_" + key_name)
            if st.button("Confirmar fusión" if merge else "Añadir", key="skill_confirmar_" + key_name,
                         disabled=len(profile["skills"]) >= 10 and not merge):
                try:
                    updated = migrate_profile(read_json(PROFILE_FILE, st.session_state.profile))
                    new_value = equivalent if merge else add_option(updated["skills"], skill, 10)[-1]
                    if not merge:
                        updated["skills"].append(new_value)
                    source = {"tipo": {"experiencias": "Experiencia laboral", "formacion": "Formación", "proyectos": "Proyecto"}[p["campo"]], "campo": p["campo"],
                        "entrada_id": p["entrada_id"], "cita": p["cita"], "confirmada_por_usuario": True,
                        "skill_original": p["skill"], "editada_por_usuario": skill.strip() != p["skill"]}
                    add_source(updated, new_value, source)
                    record_rejection(updated, p["skill"], source)
                    updated["skills_propuestas"] = [v for v in updated.get("skills_propuestas", []) if v != p]
                    save_json(PROFILE_FILE, updated)
                    st.session_state.profile = updated
                    st.session_state.profile_enriched = True
                    st.rerun()
                except (ValueError, OSError) as error:
                    st.error(str(error) if isinstance(error, ValueError) else "No se pudo guardar la skill.")
            if st.button("Descartar", key="skill_descartar_" + key_name):
                updated = migrate_profile(read_json(PROFILE_FILE, st.session_state.profile))
                record_rejection(updated, p["skill"], p)
                updated["skills_propuestas"] = [v for v in updated.get("skills_propuestas", []) if v != p]
                save_json(PROFILE_FILE, updated)
                st.session_state.profile = updated
                st.rerun()
