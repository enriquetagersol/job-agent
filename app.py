"""Local interface: streamlit run app.py."""

import threading
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
weights = normalize_weights(profile)
saved_results = st.session_state.saved_results
outdated = bool(saved_results and saved_results.get("huella") != context_fingerprint(context))
can_search = has_search_information(context["perfil"])

def request_search():
    if can_search and not st.session_state.searching and not st.session_state.search_pending:
        st.session_state.search_pending = True


start = st.session_state.search_pending and not st.session_state.searching and can_search
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
                result = search_listings(context)
                st.session_state.last_attempt = result
                if not result["error"]:
                    try:
                        new_results = save_evaluations(context, result)
                    except OSError:
                        new_results = {"contexto": context, "huella": context_fingerprint(context), **result}
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


def render_listing(item):
    listing = item["oferta"]
    with st.container(border=True):
        st.subheader(f"{listing.role} · {listing.company}")
        st.text("Ubicación: " + listing.location)
        st.link_button("Ver publicación", listing.url)
        explanations = explain_listing(listing, separate_user=True, profile=profile)
        for key_name, title in (("interes", "Motivos de interés"), ("cumplidos", "Requisitos que cumple"),
                              ("parciales", "Coincidencias parciales"), ("gaps", "Gaps"),
                              ("pendientes", "Sobre la oferta · Información pendiente de confirmar")):
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
                            "gaps": "No hay incumplimientos confirmados.",
                            "pendientes": "No hay preguntas pendientes."}[key_name])
        with st.expander("Ver detalles"):
            for criterion in listing.criteria:
                st.write("**" + CRITERIA[criterion.name] + "**")
                st.text("Descripción: " + ("; ".join(criterion.listing_evidence_quotes) or criterion.listing_evidence))
                st.text("Perfil: " + ("; ".join(criterion.profile_evidence_quotes) or criterion.profile_evidence))

if saved_results:
    st.subheader("Resultado de Busqueda" if outdated else "Resultados de búsqueda")
    try:
        date = datetime.fromisoformat(saved_results["fecha"].replace("Z", "+00:00"))
        visible = date.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M (%Z)")
    except (KeyError, TypeError, ValueError):
        visible = "No documentado"
    st.caption(f"Búsqueda: {visible}")
    try:
        result_weights = normalize_weights(saved_results.get("contexto", {}).get("perfil", {}).get("preferencias", {})) if outdated else weights
        ranked = rank_evaluations(saved_results.get("evaluaciones", []), result_weights)
    except ValueError:
        st.error("Las evaluaciones anteriores no son compatibles. Hace falta una nueva búsqueda.")
        ranked = []
    if not ranked:
        st.info("No hay ofertas evaluables.")
    for item in ranked[:5]:
        render_listing(item)
    render_profile_improvement([item["oferta"] for item in ranked[:5]], profile)
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

