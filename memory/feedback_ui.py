"""Render save/discard actions and optional discard reasons for offer cards. Persist reversible feedback and show dismissible automatic-priority notices without making external calls."""

import streamlit as st
from shared.local_storage import save_json
from memory.offer_feedback import (REASONS, CRITERION_FIELDS, vacancy_id, set_offer_action,
                            undo_adjustment)



def persist(path, state):
    save_json(path, state)
    st.rerun()


def render_offer_actions(listing, state, path, view="recommendations"):
    data = listing.model_dump()
    key = vacancy_id(data)
    record = state["offers"].get(key, {})
    prefix = view + "_" + key
    save, discard = st.columns(2)
    if save.button("Quitar de guardadas" if record.get("saved") else "Guardar", key=prefix + "_save"):
        set_offer_action(state, data, "saved", not record.get("saved"))
        persist(path, state)
    if record.get("discarded"):
        reason = REASONS.get(record.get("reason"), "Sin motivo")
        st.caption("Descartada · " + reason + " · " + record.get("discarded_date", "")[:10])
        if record.get("text"):
            st.text(record["text"])
        if discard.button("Deshacer descarte", key=prefix + "_undo_discard"):
            set_offer_action(state, data, "discarded", False)
            persist(path, state)
    elif discard.button("Descartar", key=prefix + "_discard"):
        st.session_state["discard_editor"] = prefix
        st.rerun()
    if st.session_state.get("discard_editor") == prefix and not record.get("discarded"):
        reason = st.selectbox("Motivo (opcional)", [None, *REASONS],
            format_func=lambda value: REASONS.get(value, "Sin motivo"), key=prefix + "_reason")
        scope = "specific"
        if reason in CRITERION_FIELDS:
            choice = st.radio("¿Qué quieres indicar?", ["Esta opción no me interesa", "Este criterio pesa más para mí"],
                              key=prefix + "_scope")
            scope = "global" if choice == "Este criterio pesa más para mí" else "specific"
        text = st.text_area("Comentario (opcional)", key=prefix + "_text")
        confirm, without_reason, cancel = st.columns(3)
        if confirm.button("Confirmar descarte", key=prefix + "_confirm"):
            set_offer_action(state, data, "discarded", reason=reason, text=text, scope=scope)
            st.session_state.discard_editor = None
            persist(path, state)
        if without_reason.button("Descartar sin indicar motivo", key=prefix + "_without_reason"):
            set_offer_action(state, data, "discarded")
            st.session_state.discard_editor = None
            persist(path, state)
        if cancel.button("Cancelar", key=prefix + "_cancel"):
            st.session_state.discard_editor = None
            st.rerun()


def render_learning(state, path):
    for adjustment in state["adjustments"]:
        if not adjustment["active"] or adjustment["kind"] != "automatic" or adjustment.get("notice_dismissed"):
            continue
        criterion = adjustment["criterion"]
        st.info(f"Importancia de {REASONS[criterion].lower()}: {adjustment['to']}, tras {len(adjustment['signals'])} descartes indicando que pesa más para ti.")
        undo, dismiss = st.columns(2)
        if undo.button("Deshacer", key="undo_adjustment_" + adjustment["id"]):
            undo_adjustment(state, adjustment["id"])
            persist(path, state)
        if dismiss.button("Cerrar aviso", key="dismiss_adjustment_" + adjustment["id"]):
            adjustment["notice_dismissed"] = True
            persist(path, state)
