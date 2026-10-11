"""Local interface: streamlit run app.py."""

import threading
import copy
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from agent import search_listings, reevaluate_listings
from profile_improvement import render_profile_improvement
from cv import render_cv
from local_storage import (PROFILE_FILE, load_evaluations, load_profile, search_context,
                          save_evaluations, context_fingerprint)
from evaluation import CRITERIA, normalize_weights, rank_evaluations
from profile_ui import start_editing, render_profile_form, render_profile_summary
from user_profile import migrate_profile
from presentation import explain_listing
from validation import has_search_information
from offer_feedback import load_feedback, effective_profile, available_batch, vacancy_id
from feedback_ui import render_offer_actions, render_learning
from chat_ui import render_chat

st.set_page_config(page_title="Job Agent", page_icon="🔎", layout="wide")
st.title("Encuentra ofertas que encajen contigo")
st.caption("Preferencias para ordenar oportunidades, con evidencia y sin filtros excluyentes.")

if 'profile' not in st.session_state:
    try:
        st.session_state.profile = load_profile()
        st.session_state.saved_results = load_evaluations()
    except (OSError, ValueError):
        st.error("No se pudieron leer los datos locales. No se sobrescribirán los archivos.")
        st.stop()
    st.session_state.profile_saved = PROFILE_FILE.exists()
    st.session_state.editing = not st.session_state.profile_saved
    st.session_state.searching = False
    st.session_state.search_pending = False
    st.session_state.search_lock = threading.Lock()
    if st.session_state.editing:
        start_editing()

# Compatibility with sessions opened before this update.
for key_name, value in (('editing', False), ('searching', False), ('search_pending', False)):
    if key_name not in st.session_state:
        st.session_state[key_name] = value
if 'search_lock' not in st.session_state:
    st.session_state.search_lock = threading.Lock()
if st.session_state.editing and not st.session_state.get('draft'):
    start_editing()

if st.session_state.editing:
    render_profile_form()
    st.stop()

if not st.session_state.get('profile_saved', bool(st.session_state.profile)):
    st.info("Todavía no tienes un perfil guardado. Puedes crearlo y completarlo poco a poco.")
    st.button("Crear perfil", on_click=start_editing)
    st.stop()

profile = migrate_profile(st.session_state.profile)
render_profile_summary(profile, disable_editing=st.session_state.search_pending or st.session_state.searching)
context = search_context(profile)
feedback_path = PROFILE_FILE.parent / '.local_data' / 'offer_feedback.json'
try:
    feedback = load_feedback(feedback_path, profile)
except (OSError, ValueError):
    st.error("No se pudieron leer las acciones sobre ofertas. No se sobrescribirán los datos.")
    st.stop()
weights = normalize_weights(effective_profile(feedback, profile))
render_learning(feedback, feedback_path)
saved_results = st.session_state.saved_results
comparison_context = saved_results.get("contexto") if saved_results else None
if comparison_context:
    comparison_context = copy.deepcopy(comparison_context)
    comparison_context.pop("directed_search", None)
    comparison_context.get("perfil", {}).get("preferencias", {}).pop("search_company", None)
    comparison_context.get("perfil", {}).get("preferencias", {}).pop("search_location", None)
outdated = bool(saved_results and (context_fingerprint(comparison_context) if comparison_context else
    saved_results.get("huella")) != context_fingerprint(context))
can_search = has_search_information(context["perfil"])
render_chat(profile, PROFILE_FILE, can_search, busy=st.session_state.searching or st.session_state.search_pending)

def request_search():
    if can_search and not st.session_state.searching and not st.session_state.search_pending:
        st.session_state.search_pending = True
        st.session_state.pending_search_context = context


def show_next_batch(identifiers):
    """Update navigation before rendering to avoid stale cards after a rerun."""
    st.session_state.hidden_offers = [*st.session_state.get("hidden_offers", []), *identifiers]


def restore_previous_batches():
    st.session_state.hidden_offers = []


search_request_context = st.session_state.get("pending_search_context", context)
start = st.session_state.search_pending and not st.session_state.searching and has_search_information(search_request_context["perfil"])
if start:
    st.session_state.searching = True
    st.session_state.search_pending = False
button_column, status_column = st.columns([1, 4], gap="small")
with button_column:
    st.button("Buscar ofertas", type="primary", on_click=request_search,
              disabled=st.session_state.searching or not can_search)
with status_column:
    if st.session_state.searching:
        st.markdown("""
<style>
.estado-busqueda { display: flex; align-items: center; min-height: 2.5rem; }
.circulo-busqueda { width: 1rem; height: 1rem; margin-right: .6rem;
    border: 2px solid rgba(128,128,128,.3); border-top-color: currentColor;
    border-radius: 50%; animation: giro-busqueda .8s linear infinite; }
@keyframes giro-busqueda { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
    .circulo-busqueda { animation: none; }
}
</style>
<div class="estado-busqueda" role="status" aria-label="Buscando">
    <span class="circulo-busqueda" aria-hidden="true"></span>Buscando…
</div>
""", unsafe_allow_html=True)
if not can_search:
    st.info("No hay suficiente información para buscar. Añade información sobre tu trayectoria o lo que buscas")
if not st.session_state.searching:
    render_cv(profile)

if start:
    lock = st.session_state.search_lock
    if not lock.acquire(blocking=False):
        st.warning("Ya hay una búsqueda en curso.")
    else:
        try:
            with st.container():
                result = search_listings(search_request_context)
                st.session_state.last_attempt = result
                if not result["error"]:
                    try:
                        new_results = save_evaluations(search_request_context, result)
                    except OSError:
                        new_results = {"contexto": search_request_context, "huella": context_fingerprint(search_request_context), **result}
                        st.session_state.save_warning = "Resultados disponibles en sesión, pero no se pudieron guardar en disco."
                    st.session_state.saved_results = new_results
        finally:
            st.session_state.searching = False
            lock.release()
        st.rerun()

if st.session_state.get('last_attempt', {}).get("error"):
    st.error("El último intento tuvo un error técnico. Se conservan los resultados anteriores, si existen.")
if st.session_state.get('save_warning'):
    st.warning(st.session_state.save_warning)


def render_listing(item, view="recommendations"):
    listing = item["oferta"]
    with st.container(border=True):
        st.subheader(f"{listing.role} · {listing.company}")
        st.text("Ubicación: " + listing.location)
        st.link_button("Ver publicación", listing.url)
        render_offer_actions(listing, feedback, feedback_path, view)
        explanations = explain_listing(listing, separate_user=True, profile=profile)
        for key_name, title in (("interes", "Motivos de interés"), ("cumplidos", "Requisitos que cumple"),
                              ("parciales", "Coincidencias parciales"), ("gaps", "Gaps")):
            st.write("**" + title + "**")
            for explanation in explanations[key_name]:
                st.text("• " + explanation)
            if not explanations[key_name]:
                role = next(c for c in listing.criteria if c.name == "puesto")
                missing_interest = ("Falta una descripción de las funciones para compararlas con tus objetivos."
                    if not role.listing_evidence_quotes else "Falta concretar qué funciones buscas para relacionarlas con esta oferta."
                    if not role.profile_evidence_quotes else "La evaluación no ha identificado una coincidencia con tus objetivos o preferencias.")
                st.caption({"interes": missing_interest,
                            "cumplidos": "Todavía no hay requisitos plenamente acreditados.",
                            "parciales": "No se han identificado coincidencias parciales.",
                            "gaps": "No hay incumplimientos confirmados."}[key_name])
        with st.expander("Ver detalles"):
            for criterion in listing.criteria:
                st.write("**" + CRITERIA[criterion.name] + "**")
                st.text("Descripción: " + ("; ".join(criterion.listing_evidence_quotes) or criterion.listing_evidence))
                st.text("Perfil: " + ("; ".join(criterion.profile_evidence_quotes) or criterion.profile_evidence))

search_tab, collection_tab = st.tabs(["Resultados de búsqueda", "Guardadas y descartadas"])
with search_tab:
    if saved_results:
        st.subheader("Resultado de Busqueda" if outdated else "Resultados de búsqueda")
        try:
            date = datetime.fromisoformat(saved_results["fecha"].replace("Z", "+00:00"))
            visible = date.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M (%Z)")
        except (KeyError, TypeError, ValueError):
            visible = "No documentado"
        st.caption(f"Búsqueda: {visible}")
        try:
            ranked = rank_evaluations(saved_results.get("evaluaciones", []), weights)
        except ValueError:
            st.error("Las evaluaciones anteriores no son compatibles. Hace falta una nueva búsqueda.")
            ranked = []
        if not ranked:
            st.info("No hay ofertas evaluables.")
        fingerprint = saved_results.get("huella", "") + str(saved_results.get("fecha", "")) + str(saved_results.get("actualizada", ""))
        if st.session_state.get("batch_context") != fingerprint:
            st.session_state.batch_context = fingerprint
            st.session_state.hidden_offers = []
        batch = available_batch(ranked, feedback, st.session_state.get("hidden_offers", []))
        for item in batch:
            render_listing(item)
        st.button("Mostrar otras ofertas", disabled=not batch, on_click=show_next_batch,
                  args=(tuple(vacancy_id(item["oferta"].model_dump()) for item in batch),))
        if not batch:
            st.info("No quedan más ofertas disponibles en esta búsqueda.")
            st.button("Buscar más ofertas", on_click=request_search, disabled=not can_search or st.session_state.searching)
            if st.session_state.get("hidden_offers"):
                st.button("Volver a las ofertas anteriores", on_click=restore_previous_batches)
        render_profile_improvement([item["oferta"] for item in batch], profile)
        if st.session_state.get('profile_enriched') or outdated:
            if st.button("Actualizar recomendaciones", disabled=st.session_state.searching):
                try:
                    with st.spinner("Actualizando recomendaciones…"):
                        result = reevaluate_listings(context, saved_results)
                        new_results = save_evaluations(context, result)
                        st.session_state.saved_results = new_results
                        st.session_state.profile_enriched = False
                    st.rerun()
                except Exception:
                    st.error("No se pudieron actualizar las recomendaciones. Se conservan los resultados anteriores.")



def close_offer_dialog():
    st.session_state.pop('selected_offer', None)


@st.dialog("Detalle de oferta", width="large", on_dismiss=close_offer_dialog)
def show_offer_dialog(identifier):
    record = feedback['offers'].get(identifier)
    if not record:
        close_offer_dialog()
        st.rerun()
    items = rank_evaluations([record['listing']], weights)
    if items:
        render_listing(items[0], view='collection_dialog')


with collection_tab:
    saved_tab, discarded_tab = st.tabs(["Guardadas", "Descartadas"])
    for action, tab in (("saved", saved_tab), ("discarded", discarded_tab)):
        with tab:
            records = [(identifier, record) for identifier, record in feedback['offers'].items() if record.get(action)]
            if not records:
                st.caption("No hay ofertas en esta lista.")
            for identifier, record in records:
                if st.button(record['listing']['puesto'], key='collection_' + action + '_' + identifier,
                             type='tertiary', use_container_width=True):
                    st.session_state.selected_offer = identifier

if st.session_state.get('selected_offer'):
    show_offer_dialog(st.session_state.selected_offer)
