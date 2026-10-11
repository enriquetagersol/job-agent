"""Manage professional experience, education, projects and personal contact fields. Supply entry editors, validation helpers and current-employer selection to profile and CV features."""

import copy
import uuid
import streamlit as st
from shared.validation import missing_entry_fields, entry_is_complete

MONTHS = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")
ENTRY_FIELDS = {
    "experiencias": {"empresa": "Empresa", "puesto": "Puesto", "responsabilidades": "Descripción de responsabilidades",
                     "logros": "Logros (opcional)", "herramientas": "Herramientas utilizadas (opcional)"},
    "formacion": {"institucion": "Institución", "estudios": "Estudios, titulación o curso",
                  "contenidos": "Contenidos aprendidos (opcional)", "proyectos": "Proyectos realizados (opcional)"},
    "proyectos": {"nombre": "Nombre", "descripcion": "Descripción", "contribucion": "Contribución personal",
                  "herramientas": "Tecnologías o herramientas utilizadas", "enlace": "Enlace (opcional)"},
}
ADD_BUTTON_LABELS = {"experiencias": "Añadir experiencia", "formacion": "Añadir estudios", "proyectos": "Añadir proyecto"}
PERSONAL_FIELDS = (("nombre", "Nombre"), ("apellidos", "Apellidos"), ("telefono", "Número de teléfono"),
                    ("email", "Email"), ("linkedin", "Enlace a LinkedIn"))


def ensure_career_defaults(profile):
    profile.setdefault("companies_of_interest", [])
    profile.setdefault("conversation_preferences", [])
    for field in ENTRY_FIELDS:
        profile.setdefault(field, [])
    profile.setdefault("datos_cv", {"nombre": "", "email": "", "telefono": "", "enlaces": ""})
    for field, _ in PERSONAL_FIELDS:
        profile["datos_cv"].setdefault(field, "")
    profile.setdefault("origen_skills", {})
    for skill in profile.get("skills", []):
        profile["origen_skills"].setdefault(skill, {"tipo": "Perfil anterior (sin origen detallado)"})
    profile.setdefault("experiencia_excluida_id", None)
    return profile


def validate_entry(field, entry, require_complete=True):
    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
        raise ValueError("Entrada de trayectoria inválida.")
    if not isinstance(entry.get("actual", False), bool):
        raise ValueError("La casilla de actividad actual debe ser verdadera o falsa.")
    for key_name in ENTRY_FIELDS[field]:
        if not isinstance(entry.get(key_name, ""), str):
            raise ValueError("Los datos de trayectoria deben ser texto.")
    if require_complete and field != "proyectos":
        missing_fields = missing_entry_fields(field, entry)
        if missing_fields:
            raise ValueError("Completa los campos obligatorios: " + "; ".join(missing_fields))
    if field == "proyectos":
        return entry
    dates = []
    for key_name in ("inicio", "fin"):
        date = entry.get(key_name, {})
        month, year = date.get("mes"), date.get("ano")
        if month is not None and (type(month) is not int or not 1 <= month <= 12):
            raise ValueError("Mes inválido.")
        if year is not None and (type(year) is not int or not 1 <= year <= 9999):
            raise ValueError("Año inválido.")
        dates.append((year, month))
    if not entry.get("actual"):
        (ai, mi), (af, mf) = dates
        if ai and af and (af < ai or (af == ai and mi and mf and mf < mi)):
            raise ValueError("La fecha de fin no puede ser anterior a la de inicio.")
    return entry


def employer_to_exclude(profile):
    experiences = profile.get("experiencias", [])
    current_entries = [e for e in experiences if e.get("actual") and e.get("empresa", "").strip()]
    if not experiences:
        return profile.get("empresa_actual", "")
    if len(current_entries) == 1:
        return current_entries[0]["empresa"]
    return next((e["empresa"] for e in current_entries if e["id"] == profile.get("experiencia_excluida_id")), "")


def format_date(date):
    return " ".join(str(v) for v in (MONTHS[date["mes"] - 1] if date.get("mes") else "", date.get("ano") or "") if v)


def entry_title(field, entry):
    keys = {"experiencias": ("puesto", "empresa"), "formacion": ("estudios", "institucion"), "proyectos": ("nombre",)}[field]
    return " · ".join(entry.get(k, "") for k in keys if entry.get(k)) or "Entrada sin completar"


def start_entry(field, entry=None):
    for key_name in list(st.session_state):
        if key_name.startswith("editor_entrada_"):
            del st.session_state[key_name]
    record = copy.deepcopy(entry) if entry else {"id": uuid.uuid4().hex}
    st.session_state.active_entry = {"campo": field, "dato": record}


def render_date_editor(label, date, key_name, disabled=False):
    month, year = st.columns(2)
    selected = month.selectbox("Mes de " + label, MONTHS,
        index=date["mes"] - 1 if date.get("mes") else None, disabled=disabled, key=key_name + "_mes")
    value = year.number_input("Año de " + label, min_value=1, max_value=9999,
        value=date.get("ano"), step=1, disabled=disabled, key=key_name + "_ano")
    return {"mes": MONTHS.index(selected) + 1 if selected else None, "ano": value}


def render_entries(field, profile, editor_only=False):
    st.markdown("**" + {"experiencias": "Experiencia laboral", "formacion": "Formación", "proyectos": "Proyectos"}[field] + "**")
    for entry in ([] if editor_only else list(profile[field])):
        with st.container(border=True):
            st.write(entry_title(field, entry))
            if not entry_is_complete(field, entry):
                st.caption("Pendiente de completar")
            if field != "proyectos":
                dates = [format_date(entry.get("inicio", {})), "Actualidad" if entry.get("actual") else format_date(entry.get("fin", {}))]
                st.caption(" - ".join(f for f in dates if f))
            description = entry.get("responsabilidades") or entry.get("contenidos") or entry.get("descripcion")
            if description:
                st.text(description[:180] + ("…" if len(description) > 180 else ""))
            edit_column, remove_column = st.columns(2)
            edit_column.button("Editar", key="editor_editar_" + entry["id"], on_click=start_entry,
                          args=(field, entry), disabled=bool(st.session_state.get('active_entry')))
            def remove(identifier=entry["id"]):
                profile[field] = [e for e in profile[field] if e["id"] != identifier]
                if (st.session_state.get('active_entry') or {}).get("dato", {}).get("id") == identifier:
                    st.session_state.active_entry = None
            remove_column.button("Eliminar", key="editor_eliminar_" + entry["id"], on_click=remove)
    if not editor_only:
        st.button(ADD_BUTTON_LABELS[field], key="editor_anadir_" + field, on_click=start_entry, args=(field,),
                  disabled=bool(st.session_state.get('active_entry')))
    active = st.session_state.get('active_entry')
    if not active or active["campo"] != field:
        return
    record = active["dato"]
    with st.container(border=True):
        st.caption("Esta entrada se incorpora al borrador. Guardar perfil confirma todos los cambios.")
        for key_name, label in ENTRY_FIELDS[field].items():
            if key_name in ({"experiencias": ("empresa", "puesto", "responsabilidades"), "formacion": ("institucion", "estudios")}.get(field, ())):
                label += " *"
            function = st.text_area if key_name in ("responsabilidades", "logros", "contenidos", "proyectos", "descripcion", "contribucion", "herramientas") else st.text_input
            record[key_name] = function(label, value=record.get(key_name, ""), key="editor_entrada_" + key_name)
        if field != "proyectos":
            record["actual"] = st.checkbox("Trabajo aquí actualmente" if field == "experiencias" else "En curso",
                value=record.get("actual", False), key="editor_entrada_actual")
            record["inicio"] = render_date_editor("inicio *", record.get("inicio", {}), "editor_entrada_inicio")
            end_date = render_date_editor("fin" if record["actual"] else "fin *", record.get("fin", {}), "editor_entrada_fin", disabled=record["actual"])
            if not record["actual"]:
                record["fin"] = end_date
        add, cancel = st.columns(2)
        if add.button("Guardar entrada", key="editor_entrada_guardar"):
            try:
                validate_entry(field, record)
                profile[field] = [copy.deepcopy(record) if e["id"] == record["id"] else e for e in profile[field]] if any(e["id"] == record["id"] for e in profile[field]) else [*profile[field], copy.deepcopy(record)]
                st.session_state.active_entry = None
                st.rerun()
            except ValueError as error:
                st.error(str(error))
        if cancel.button("Cancelar entrada", key="editor_entrada_cancelar"):
            st.session_state.active_entry = None
            st.rerun()
