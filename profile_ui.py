"""Form with a session draft; saving is the only profile write."""

import copy
import hashlib

import streamlit as st

from local_storage import PROFILE_FILE, save_json, read_json
from user_profile import (EXPERIENCE_OPTIONS, WORK_MODES, CURRENCIES, LANGUAGE_LEVELS, PREFERENCES,
                    add_option, normalize_identity, migrate_profile, validate_profile)
from career_history import render_entries, employer_to_exclude, entry_title, PERSONAL_FIELDS, start_entry, validate_entry
from skill_store import remove_skill, possible_equivalence, sources_for_skill, add_source
from validation import entry_is_complete


def optional_index(options, value):
    return options.index(value) if value in options else None


def start_editing(block=None, entry=None):
    for key_name in list(st.session_state):
        if key_name.startswith("editor_"):
            del st.session_state[key_name]
    st.session_state.draft = migrate_profile(st.session_state.profile)
    st.session_state.editing = True
    st.session_state.form_error = ""
    st.session_state.active_entry = None
    st.session_state.editing_block = block
    st.session_state.editing_entry_id = None
    if block in ("experiencias", "formacion", "proyectos"):
        start_entry(block, entry)
        st.session_state.editing_entry_id = st.session_state.active_entry["dato"]["id"]


def option_key(field, text):
    return "editor_" + field + "_" + hashlib.sha256(normalize_identity(text).encode()).hexdigest()[:16]


def render_text_options(field, label, limit, property_name=None, preference=False, levels=False):
    draft = st.session_state.draft
    options = [o[property_name] for o in draft[field]] if property_name else list(draft[field])
    st.markdown(f"**{label} · {len(options)}/{limit}**" if limit else f"**{label} · {len(options)}**")
    entry = "editor_nuevo_" + field
    left, right = st.columns([4, 1])
    left.text_input("Añadir " + label.lower(), key=entry, label_visibility="collapsed", placeholder=label)

    def add():
        try:
            existing = [o[property_name] for o in draft[field]] if property_name else draft[field]
            new_value = add_option(existing, st.session_state.get(entry, ""), limit)[-1]
            if property_name:
                value = {property_name: new_value, "preferencia": None} if preference else {property_name: new_value, "nivel": None}
            else:
                value = new_value
            draft[field].append(value)
            if field == "skills":
                draft["origen_skills"][new_value] = {"tipo": "Declaración del usuario"}
            st.session_state[entry] = ""
            st.session_state.form_error = ""
        except ValueError as error:
            st.session_state.form_error = str(error)
    right.button("Añadir", key="editor_anadir_" + field, on_click=add,
                   disabled=bool(limit and len(options) >= limit))

    for option in list(draft[field]):
        text = option[property_name] if property_name else option
        label_column, value_column, remove_column = st.columns([3, 2, 1])
        label_column.text(text)
        if preference:
            option["preferencia"] = value_column.selectbox("Preferencia de " + text, PREFERENCES,
                index=optional_index(PREFERENCES, option["preferencia"]), key=option_key(field + "_preferencia", text))
        if levels:
            option["nivel"] = value_column.selectbox("Nivel de " + text, LANGUAGE_LEVELS,
                index=optional_index(LANGUAGE_LEVELS, option["nivel"]), key=option_key(field + "_nivel", text))
        if field in ("skills", "idiomas"):
            def edit(text=text):
                st.session_state["editor_modificando_" + field] = text
                st.session_state["editor_nombre_" + field] = text
            label_column.button("Editar", key=option_key(field + "_editar", text), on_click=edit)
            if field == "skills" and draft["origen_skills"].get(text):
                label_column.caption("Origen: " + draft["origen_skills"][text].get("tipo", "Declaración del usuario"))
        def remove(text=text):
            if field == "skills":
                remove_skill(draft, text)
            else:
                draft[field] = [o for o in draft[field] if normalize_identity(o[property_name] if property_name else o) != normalize_identity(text)]
            for suffix in ("_preferencia", "_nivel"):
                st.session_state.pop(option_key(field + suffix, text), None)
            st.session_state.form_error = ""
        remove_column.button("Eliminar", key=option_key(field + "_eliminar", text),
                            on_click=remove, help="Eliminar " + text)
    previous = st.session_state.get("editor_modificando_" + field)
    if previous and previous in options:
        updated = st.text_input("Editar " + label.lower(), key="editor_nombre_" + field)
        if st.button("Aplicar cambio", key="editor_aplicar_" + field):
            try:
                others = [o for o in options if o != previous]
                name = add_option(others, updated, limit)[-1]
                if property_name:
                    for o in draft[field]:
                        if o[property_name] == previous:
                            o[property_name] = name
                else:
                    draft[field] = [name if o == previous else o for o in draft[field]]
                    origin = draft["origen_skills"].pop(previous, {"tipo": "Declaración del usuario"})
                    draft["origen_skills"][name] = {**origin, "editada_por_usuario": True}
                st.session_state.pop("editor_modificando_" + field, None)
                st.rerun()
            except ValueError as error:
                st.error(str(error))


def render_profile_form():
    if st.session_state.get('editing_block'):
        render_block_editor()
        return
    draft = st.session_state.draft
    draft.setdefault("empresa_actual", "")
    draft.setdefault("excluir_empresa_actual", False)
    st.subheader("Editar perfil" if st.session_state.profile else "Crear perfil")
    st.caption("Puedes guardar un perfil incompleto. Solo Guardar perfil guarda tus cambios; nada se envía mientras editas.")
    if st.session_state.get('form_error'):
        st.error(st.session_state.form_error)
    personal, career_history, preferences = st.tabs(["Datos personales", "Trayectoria profesional", "Preferencias de búsqueda"])
    with personal:
        for key_name, label in PERSONAL_FIELDS:
            draft["datos_cv"][key_name] = st.text_input(label, value=draft["datos_cv"][key_name], key="editor_cv_" + key_name)
    with career_history:
        for field in ("experiencias", "formacion", "proyectos"):
            render_entries(field, draft)
        with st.expander("Experiencia general registrada"):
            draft["experiencia"] = st.selectbox("Experiencia", EXPERIENCE_OPTIONS[1:],
                index=optional_index(EXPERIENCE_OPTIONS[1:], draft["experiencia"]), key="editor_experiencia") or "Sin especificar"
            st.caption("Este rango se conserva; no se convierte en empleos ni fechas.")
        render_text_options("skills", "Capacidades/skills", 10)
        render_text_options("idiomas", "Idiomas", None, "idioma", levels=True)
    with preferences:
        current_entries = [e for e in draft["experiencias"] if e.get("actual") and e.get("empresa")]
        if not draft["experiencias"]:
            draft["empresa_actual"] = st.text_input("Empresa actual", value=draft["empresa_actual"], key="editor_empresa_actual")
        elif len(current_entries) > 1:
            ids = [e["id"] for e in current_entries]
            draft["experiencia_excluida_id"] = st.selectbox("Empresa actual que quieres excluir", ids,
                format_func=lambda key_name: next(entry_title("experiencias", e) for e in current_entries if e["id"] == key_name),
                index=optional_index(ids, draft["experiencia_excluida_id"]), key="editor_empresa_elegida")
        st.caption("Empresa para excluir: " + (employer_to_exclude(draft) or "Sin seleccionar"))
        draft["excluir_empresa_actual"] = st.checkbox("Excluir ofertas de esta empresa", value=draft["excluir_empresa_actual"], key="editor_excluir_empresa")
        render_text_options("puestos_objetivo", "Puestos objetivo/de interés", 5)
        render_text_options("ubicaciones", "Ubicaciones", 5, "nombre", preference=True)
        draft["importancia_ubicacion"] = st.selectbox("Importancia global de la ubicación", PREFERENCES,
            index=optional_index(PREFERENCES, draft["importancia_ubicacion"]), key="editor_importancia_ubicacion")
        st.markdown("**Modalidad**")
        for mode in WORK_MODES:
            left, right = st.columns(2)
            selected = left.checkbox(mode, value=mode in draft["modalidades"], key="editor_modalidad_" + mode)
            preference = right.selectbox("Preferencia de " + mode, PREFERENCES,
                index=optional_index(PREFERENCES, draft["modalidades"].get(mode)),
                disabled=not selected, key="editor_preferencia_modalidad_" + mode)
            if selected:
                draft["modalidades"][mode] = preference
            else:
                draft["modalidades"].pop(mode, None)
        draft["importancia_modalidad"] = st.selectbox("Importancia global de la modalidad", PREFERENCES,
            index=optional_index(PREFERENCES, draft["importancia_modalidad"]), key="editor_importancia_modalidad")
        specify = st.checkbox("Especificar salario mínimo bruto anual", value=draft["salario_minimo"] is not None, key="editor_especificar_salario")
        amount, currency = st.columns(2)
        minimum = amount.number_input("Salario mínimo bruto anual", min_value=0.0,
            value=float(draft["salario_minimo"]) if draft["salario_minimo"] is not None else None, step=1000.0,
            disabled=not specify, key="editor_salario")
        draft["moneda"] = currency.selectbox("Moneda", CURRENCIES,
            index=optional_index(CURRENCIES, draft["moneda"]), disabled=not specify, key="editor_moneda")
        draft["salario_minimo"] = minimum if specify else None
        draft["importancia_salario"] = st.selectbox("Importancia del salario", PREFERENCES,
            index=optional_index(PREFERENCES, draft["importancia_salario"]), key="editor_importancia_salario")
        draft["que_buscas"] = st.text_area("¿Qué buscas?", value=draft["que_buscas"],
            max_chars=400, key="editor_que_buscas", help="Tus aspiraciones orientan los puestos; no acreditan experiencia ni capacidades.")
        st.caption(f"{len(draft['que_buscas'])}/400 caracteres")
    save, cancel = st.columns(2)
    if save.button("Guardar perfil", type="primary", key="editor_guardar"):
        try:
            # Text entered without clicking Add is neither lost nor added implicitly.
            if any(st.session_state.get("editor_nuevo_" + c, "").strip() for c in ("puestos_objetivo", "ubicaciones", "skills", "idiomas")):
                raise ValueError("Pulsa Añadir para guardar las opciones pendientes o borra su texto.")
            if st.session_state.get('active_entry'):
                raise ValueError("Guarda o cancela la entrada abierta antes de guardar el perfil.")
            validate_profile(draft, previous=read_json(PROFILE_FILE, {}))
            save_json(PROFILE_FILE, draft)
            st.session_state.profile = copy.deepcopy(draft)
            st.session_state.editing = False
            st.session_state.profile_saved = True
            st.session_state.draft = None
            st.rerun()
        except (OSError, ValueError) as error:
            st.error(str(error) if isinstance(error, ValueError) else "No se pudo guardar el perfil.")
    if cancel.button("Cancelar", key="editor_cancelar"):
        st.session_state.editing = False
        st.session_state.draft = None
        st.rerun()


def close_editor():
    st.session_state.editing = False
    st.session_state.draft = None
    st.session_state.editing_block = None
    st.session_state.active_entry = None
    st.rerun()


def render_block_editor():
    field = st.session_state.editing_block
    draft = st.session_state.draft
    labels = {"puestos_objetivo": "Puestos objetivo", "ubicaciones": "Ubicaciones", "modalidades": "Modalidad",
                 "salario": "Salario", "skills": "Skills", "idiomas": "Idiomas", "que_buscas": "¿Qué buscas?"}
    st.subheader("Editar " + labels.get(field, field.replace("cv:", "")))
    keys = [field]
    if field.startswith("cv:"):
        key_name = field[3:]
        label = dict(PERSONAL_FIELDS)[key_name]
        draft["datos_cv"][key_name] = st.text_input(label, value=draft["datos_cv"][key_name], key="editor_cv_" + key_name)
    elif field in ("experiencias", "formacion", "proyectos"):
        render_entries(field, draft, editor_only=True)
    elif field in ("skills", "puestos_objetivo", "idiomas", "ubicaciones"):
        render_text_options(field, labels[field], {"skills": 10, "puestos_objetivo": 5, "ubicaciones": 5}.get(field),
                      {"idiomas": "idioma", "ubicaciones": "nombre"}.get(field),
                      preference=field == "ubicaciones", levels=field == "idiomas")
        if field == "skills":
            keys += ["origen_skills", "skills_rechazadas", "archivo_fuentes_skills"]
        if field == "ubicaciones":
            keys += ["importancia_ubicacion"]
            draft["importancia_ubicacion"] = st.selectbox("Importancia global de la ubicación", PREFERENCES,
                index=optional_index(PREFERENCES, draft["importancia_ubicacion"]), key="editor_importancia_ubicacion")
    elif field == "modalidades":
        keys += ["importancia_modalidad"]
        for mode in WORK_MODES:
            selected = st.checkbox(mode, value=mode in draft["modalidades"], key="editor_modalidad_" + mode)
            preference = st.selectbox("Preferencia de " + mode, PREFERENCES,
                index=optional_index(PREFERENCES, draft["modalidades"].get(mode)),
                disabled=not selected, key="editor_preferencia_modalidad_" + mode)
            if selected:
                draft["modalidades"][mode] = preference
            else:
                draft["modalidades"].pop(mode, None)
        draft["importancia_modalidad"] = st.selectbox("Importancia global de la modalidad", PREFERENCES,
            index=optional_index(PREFERENCES, draft["importancia_modalidad"]), key="editor_importancia_modalidad")
    elif field == "salario":
        keys = ["salario_minimo", "moneda", "importancia_salario"]
        specify = st.checkbox("Especificar salario mínimo bruto anual", value=draft["salario_minimo"] is not None, key="editor_especificar_salario")
        minimum = st.number_input("Salario mínimo bruto anual", min_value=0.0,
            value=float(draft["salario_minimo"]) if draft["salario_minimo"] is not None else None,
            step=1000.0, disabled=not specify, key="editor_salario")
        draft["salario_minimo"] = minimum if specify else None
        draft["moneda"] = st.selectbox("Moneda", CURRENCIES,
            index=optional_index(CURRENCIES, draft["moneda"]), disabled=not specify, key="editor_moneda")
        draft["importancia_salario"] = st.selectbox("Importancia del salario", PREFERENCES,
            index=optional_index(PREFERENCES, draft["importancia_salario"]), key="editor_importancia_salario")
    elif field == "que_buscas":
        draft[field] = st.text_area("¿Qué buscas?", value=draft[field], max_chars=400, key="editor_que_buscas")
        st.caption(f"{len(draft[field])}/400 caracteres")
    if st.session_state.get('form_error'):
        st.error(st.session_state.form_error)
    save, cancel = st.columns(2)
    if save.button("Guardar", key="editor_guardar_individual", type="primary"):
        try:
            if st.session_state.get("editor_nuevo_" + field, "").strip():
                raise ValueError("Pulsa Añadir o borra el texto pendiente antes de guardar.")
            updated = migrate_profile(read_json(PROFILE_FILE, st.session_state.profile))
            if field.startswith("cv:"):
                updated["datos_cv"][field[3:]] = draft["datos_cv"][field[3:]]
            elif field in ("experiencias", "formacion", "proyectos"):
                active = st.session_state.get('active_entry')
                identifier = st.session_state.editing_entry_id
                entry = copy.deepcopy(active["dato"]) if active else next(e for e in draft[field] if e["id"] == identifier)
                validate_entry(field, entry)
                updated[field] = [entry if e["id"] == identifier else e for e in updated[field]]
                if not any(e["id"] == identifier for e in updated[field]):
                    updated[field].append(entry)
            else:
                for key_name in keys:
                    updated[key_name] = copy.deepcopy(draft.get(key_name, {} if key_name != "skills_rechazadas" else []))
            validate_profile(updated, previous=read_json(PROFILE_FILE, {}))
            save_json(PROFILE_FILE, updated)
            st.session_state.profile = updated
            close_editor()
        except (ValueError, OSError) as error:
            st.error(str(error) if isinstance(error, ValueError) else "No se pudo guardar el cambio.")
    if cancel.button("Cancelar", key="editor_cancelar_individual"):
        close_editor()


def remove_confirmed_skill(skill):
    updated = migrate_profile(read_json(PROFILE_FILE, st.session_state.profile))
    remove_skill(updated, skill)
    save_json(PROFILE_FILE, updated)
    st.session_state.profile = updated


def remove_saved_entry(field, identifier):
    updated = migrate_profile(read_json(PROFILE_FILE, st.session_state.profile))
    updated[field] = [e for e in updated[field] if e["id"] != identifier]
    save_json(PROFILE_FILE, updated)
    st.session_state.profile = updated


def render_edit_button(field, disabled=False):
    st.button("Editar", key="resumen_editar_" + field, on_click=start_editing, args=(field,), disabled=disabled)


def render_editable_summary(field, text, disabled=False):
    value, edit = st.columns([5, 1])
    value.write(text)
    with edit:
        render_edit_button(field, disabled)


def merge_confirmed_skills(keep, merge):
    updated = migrate_profile(read_json(PROFILE_FILE, st.session_state.profile))
    sources = copy.deepcopy(sources_for_skill(updated, merge))
    remove_skill(updated, merge)
    for source in sources:
        add_source(updated, keep, source)
    save_json(PROFILE_FILE, updated)
    st.session_state.profile = updated


def render_profile_summary(profile, disable_editing=False):
    profile = migrate_profile(profile)
    st.subheader("Tu perfil")
    personal, career_history, preferences = st.tabs(["Datos personales", "Trayectoria profesional", "Preferencias de búsqueda"])
    with personal:
        for field, label in PERSONAL_FIELDS:
            render_editable_summary("cv:" + field, label + ": " + (profile["datos_cv"][field] or "Sin especificar"), disable_editing)
    with career_history:
        for field, label in (("experiencias", "Experiencia laboral"), ("formacion", "Formación"), ("proyectos", "Proyectos")):
            st.write("**" + label + "**")
            for entry in profile[field]:
                with st.container(border=True):
                    st.write(entry_title(field, entry))
                    if not entry_is_complete(field, entry):
                        st.caption("Pendiente de completar")
                    edit, remove = st.columns(2)
                    edit.button("Editar", key="resumen_entrada_" + entry["id"], on_click=start_editing,
                                  args=(field, entry), disabled=disable_editing)
                    remove.button("Eliminar", key="resumen_eliminar_" + entry["id"], on_click=remove_saved_entry,
                                    args=(field, entry["id"]), disabled=disable_editing)
            if not profile[field]:
                st.caption("Todavía sin registrar")
            st.button({"experiencias": "Añadir experiencia", "formacion": "Añadir estudios", "proyectos": "Añadir proyecto"}[field],
                key="resumen_anadir_" + field, on_click=start_editing, args=(field,), disabled=disable_editing)
        st.caption("Experiencia general registrada: " + profile["experiencia"])
        render_editable_summary("skills", f"**Skills confirmadas · {len(profile['skills'])}/10**", disable_editing)
        for skill in profile["skills"]:
            value, remove = st.columns([5, 1])
            value.text(skill)
            remove.button("Eliminar", key=option_key("resumen_skill_eliminar", skill), on_click=remove_confirmed_skill,
                            args=(skill,), disabled=disable_editing)
        for i, skill in enumerate(profile["skills"]):
            equivalent = possible_equivalence(skill, profile["skills"][i + 1:])
            if equivalent:
                st.caption(f"«{skill}» y «{equivalent}» podrían ser equivalentes. Si confirmas la fusión, se conservará «{skill}» y sus fuentes.")
                st.button("Confirmar fusión", key=option_key("fusion_confirmadas", skill),
                    on_click=merge_confirmed_skills, args=(skill, equivalent), disabled=disable_editing)
        if not disable_editing:
            from skills import render_suggestions
            render_suggestions(profile)
        render_editable_summary("idiomas", "**Idiomas:** " + ("; ".join(f"{i['idioma']} ({i['nivel'] or 'Sin especificar'})" for i in profile["idiomas"]) or "Sin especificar"), disable_editing)
    with preferences:
        st.write("**Empresa para excluir:** " + (employer_to_exclude(profile) or "Sin seleccionar"))
        st.caption("Excluir ofertas de esta empresa: " + ("Sí" if profile["excluir_empresa_actual"] else "No"))
        render_editable_summary("puestos_objetivo", "**Puestos objetivo:** " + (", ".join(profile["puestos_objetivo"]) or "No especificado"), disable_editing)
        render_editable_summary("ubicaciones", "**Ubicaciones:** " + ("; ".join(f"{u['nombre']} ({u['preferencia'] or 'Sin especificar'})" for u in profile["ubicaciones"]) or "No especificado"), disable_editing)
        st.caption("Importancia global de ubicación: " + (profile["importancia_ubicacion"] or "Sin especificar"))
        render_editable_summary("modalidades", "**Modalidades:** " + ("; ".join(f"{m} ({p or 'Sin especificar'})" for m, p in profile["modalidades"].items()) or "No especificado"), disable_editing)
        st.caption("Importancia global de modalidad: " + (profile["importancia_modalidad"] or "Sin especificar"))
        salary = "No especificado" if profile["salario_minimo"] is None else f"{profile['salario_minimo']:,.2f} {profile['moneda'] or 'moneda sin especificar'} bruto anual"
        render_editable_summary("salario", "**Salario mínimo:** " + salary, disable_editing)
        st.caption("Importancia del salario: " + (profile["importancia_salario"] or "Sin especificar"))
        render_editable_summary("que_buscas", "**¿Qué buscas?**", disable_editing)
        st.text(profile["que_buscas"] or "No especificado")
    st.button("Editar perfil", on_click=start_editing, disabled=disable_editing)
