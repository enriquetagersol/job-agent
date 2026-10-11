"""Collect relevant unanswered user questions from offer evaluations. Persist literal answers only after confirmation and expose review, edit and removal controls for profile enrichment."""

import copy
import hashlib
import streamlit as st
from shared.local_storage import PROFILE_FILE, save_json
from profiles.user_profile import normalize_identity, migrate_profile
from jobs.evaluation import quote_is_documented


def is_user_question(c, profile):
    evidence = c.listing_evidence_quotes or c.listing_evidence
    if c.name == "capacidades" and c.declared_skills:
        return True
    if c.points != "Sin datos" or not evidence or evidence == "No documentado":
        return False
    if c.name in ("experiencia", "capacidades"):
        return True
    if c.name == "puesto":
        return not c.profile_evidence_quotes and not profile.get("que_buscas", "").strip()
    if c.name == "idiomas":
        return not c.profile_evidence_quotes and c.profile_evidence.strip() in ("", "No documentado", "Sin datos")
    return False


def user_questions(job_listings, profile):
    candidates = {}
    for listing in job_listings:
        for c in listing.criteria:
            questions = []
            if not is_user_question(c, profile):
                continue
            if c.name == "puesto":
                questions.append(("work_interests", "¿Qué tareas te gustaría realizar en tu próximo puesto? Describe qué trabajo buscas, además del título."))
            if c.name == "experiencia":
                recorded = [e.get(k, "") for field, keys in (
                    ("experiencias", ("responsabilidades", "logros")),
                    ("proyectos", ("descripcion", "contribucion")),
                    ("formacion", ("contenidos", "proyectos"))) for e in profile.get(field, [])
                    for k in keys if e.get(k)]
                if not recorded:
                    questions.append(("experiencia_tareas", "¿Qué tareas o proyectos has realizado? Indica si fueron laborales, académicos o personales, tu papel y la duración."))
                elif not c.profile_evidence_quotes:
                    quote = "; ".join(c.listing_evidence_quotes) or c.listing_evidence
                    if not any(quote_is_documented(quote, t) for t in recorded):
                        key_name = "experiencia:" + hashlib.sha256(normalize_identity(quote).encode()).hexdigest()[:16]
                        questions.append((key_name, f"Tu experiencia ya está registrada. Para el requisito «{quote}», ¿qué dato adicional puedes confirmar que todavía no figure en ella?"))
            if c.name == "capacidades" and c.declared_skills:
                for skill in c.declared_skills:
                    applied = any(quote_is_documented(skill, " ".join(e.get(k, "") for k in keys))
                        and any(e.get(k, "").strip() for k in tasks)
                        for field, keys, tasks in (("experiencias", ("herramientas", "responsabilidades", "logros"), ("responsabilidades", "logros")),
                            ("proyectos", ("herramientas", "descripcion", "contribucion"), ("contribucion",))) for e in profile.get(field, []))
                    if not applied:
                        questions.append(("skill:" + normalize_identity(skill), f"¿Cómo has utilizado {skill}? Describe una tarea o proyecto, su contexto y qué hiciste tú."))
            elif c.name == "capacidades":
                quote = "; ".join(c.listing_evidence_quotes) or c.listing_evidence
                texts = [e.get(k, "") for field, keys in (
                    ("experiencias", ("responsabilidades", "logros", "herramientas")),
                    ("formacion", ("contenidos", "proyectos")),
                    ("proyectos", ("descripcion", "contribucion", "herramientas")))
                    for e in profile.get(field, []) for k in keys]
                if not any(quote_is_documented(quote, t) for t in texts):
                    key_name = "requisito:" + hashlib.sha256(normalize_identity(quote).encode()).hexdigest()[:16]
                    questions.append((key_name, f"La oferta pide «{quote}». ¿Qué conocimientos o práctica puedes describir sobre ese requisito?"))
            if c.name == "idiomas":
                questions.append(("idiomas", "¿Qué idiomas conoces y qué nivel declaras para cada uno?"))
            for key_name, question in questions:
                record = candidates.setdefault(key_name, {"pregunta": question, "relevancia": 0})
                record["relevancia"] += 1
    answered = profile.get("respuestas_confirmadas", {})
    skipped = profile.get("preguntas_omitidas", [])
    return [(k, v["pregunta"]) for k, v in sorted(candidates.items(), key=lambda pair: -pair[1]["relevancia"])
            if k not in answered and k not in skipped][:3]


def save_answer_change(key_name, question, response=None, skip=False):
    profile = migrate_profile(st.session_state.profile)
    if skip:
        profile.setdefault("preguntas_omitidas", []).append(key_name)
    elif response is None:
        profile.setdefault("respuestas_confirmadas", {}).pop(key_name, None)
    else:
        profile.setdefault("respuestas_confirmadas", {})[key_name] = {"pregunta": question, "respuesta": response.strip()}
    save_json(PROFILE_FILE, profile)
    st.session_state.profile = profile
    if not skip:
        st.session_state.profile_enriched = True
    st.rerun()


def render_profile_improvement(job_listings, profile):
    questions = user_questions(job_listings, profile)
    answers = profile.get("respuestas_confirmadas", {})
    if not questions and not answers and not profile.get("preguntas_omitidas"):
        return
    st.subheader("Mejorar mi perfil")
    st.caption("Puedes responder u omitir. Solo se guardará una respuesta después de tu confirmación.")
    for key_name, question in questions:
        st.write(question)
        response = st.text_area("Tu respuesta", key="respuesta_" + key_name)
        if st.button("Proponer información", key="proponer_" + key_name, disabled=not response.strip()):
            st.session_state["propuesta_" + key_name] = response.strip()
        suggestion = st.session_state.get("propuesta_" + key_name)
        if suggestion:
            st.write("Se añadirá a tu perfil como declaración literal:")
            st.text(suggestion)
            if st.button("Confirmar y guardar", key="confirmar_" + key_name):
                save_answer_change(key_name, question, suggestion)
        if st.button("Omitir", key="omitir_" + key_name):
            save_answer_change(key_name, question, skip=True)
    for key_name, record in answers.items():
        with st.expander(record["pregunta"]):
            st.text(record["respuesta"])
            new_value = st.text_area("Editar respuesta", value=record["respuesta"], key="editar_respuesta_" + key_name)
            if st.button("Proponer cambio", key="cambio_" + key_name, disabled=not new_value.strip()):
                st.session_state["cambio_propuesto_" + key_name] = new_value.strip()
            change = st.session_state.get("cambio_propuesto_" + key_name)
            if change:
                st.text("Se guardará: " + change)
                if st.button("Confirmar cambio", key="guardar_cambio_" + key_name):
                    save_answer_change(key_name, record["pregunta"], change)
            if st.button("Borrar respuesta", key="borrar_" + key_name):
                save_answer_change(key_name, record["pregunta"])
    if profile.get("preguntas_omitidas") and st.button("Volver a mostrar preguntas omitidas"):
        updated = copy.deepcopy(st.session_state.profile)
        updated["preguntas_omitidas"] = []
        save_json(PROFILE_FILE, updated)
        st.session_state.profile = updated
        st.rerun()
