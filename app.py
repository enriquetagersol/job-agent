"""Interfaz local: streamlit run app.py."""

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from agente import buscar_ofertas, reevaluar_ofertas
from mejoras import mostrar_mejoras
from cv import mostrar_cv
from datos_locales import (ARCHIVO_PERFIL, cargar_evaluaciones, cargar_perfil, contexto_busqueda,
                          guardar_evaluaciones, huella_contexto)
from evaluacion import CRITERIOS, normalizar_pesos, ordenar_evaluaciones
from formulario import iniciar_edicion, mostrar_formulario, mostrar_resumen
from perfil import migrar_perfil
from presentacion import explicar_oferta
from validaciones import informacion_busqueda

st.set_page_config(page_title="Job Agent", page_icon="🔎", layout="wide")
st.title("Encuentra ofertas que encajen contigo")
st.caption("Preferencias para ordenar oportunidades, con evidencia y sin filtros excluyentes.")

if "perfil" not in st.session_state:
    try:
        st.session_state.perfil = cargar_perfil()
        st.session_state.guardadas = cargar_evaluaciones()
    except (OSError, ValueError):
        st.error("No se pudieron leer los datos locales. No se sobrescribirán los archivos.")
        st.stop()
    st.session_state.perfil_guardado = ARCHIVO_PERFIL.exists()
    st.session_state.editando = not st.session_state.perfil_guardado
    st.session_state.buscando = False
    st.session_state.busqueda_pendiente = False
    st.session_state.candado_busqueda = threading.Lock()
    if st.session_state.editando:
        iniciar_edicion()

# Compatibilidad con una sesión que estuviese abierta antes de esta actualización.
for clave, valor in (("editando", False), ("buscando", False), ("busqueda_pendiente", False)):
    if clave not in st.session_state:
        st.session_state[clave] = valor
if "candado_busqueda" not in st.session_state:
    st.session_state.candado_busqueda = threading.Lock()
if st.session_state.editando and not st.session_state.get("borrador"):
    iniciar_edicion()

if st.session_state.editando:
    mostrar_formulario()
    st.stop()

if not st.session_state.get("perfil_guardado", bool(st.session_state.perfil)):
    st.info("Todavía no tienes un perfil guardado. Puedes crearlo y completarlo poco a poco.")
    st.button("Crear perfil", on_click=iniciar_edicion)
    st.stop()

perfil = migrar_perfil(st.session_state.perfil)
mostrar_resumen(perfil, deshabilitar_edicion=st.session_state.busqueda_pendiente or st.session_state.buscando)
contexto = contexto_busqueda(perfil)
pesos = normalizar_pesos(perfil)
guardadas = st.session_state.guardadas
obsoletas = bool(guardadas and guardadas.get("huella") != huella_contexto(contexto))
puede_buscar = informacion_busqueda(contexto["perfil"])

def solicitar_busqueda():
    if puede_buscar and not st.session_state.buscando and not st.session_state.busqueda_pendiente:
        st.session_state.busqueda_pendiente = True


iniciar = st.session_state.busqueda_pendiente and not st.session_state.buscando and puede_buscar
if iniciar:
    st.session_state.buscando = True
    st.session_state.busqueda_pendiente = False
columna_boton, columna_estado = st.columns([1, 4], gap="small")
with columna_boton:
    st.button("Buscar ofertas", type="primary", on_click=solicitar_busqueda,
              disabled=st.session_state.buscando or not puede_buscar)
with columna_estado:
    if st.session_state.buscando:
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
if not puede_buscar:
    st.info("No hay suficiente información para buscar. Añade información sobre tu trayectoria o lo que buscas")
if not st.session_state.buscando:
    mostrar_cv(perfil)

if iniciar:
    candado = st.session_state.candado_busqueda
    if not candado.acquire(blocking=False):
        st.warning("Ya hay una búsqueda en curso.")
    else:
        try:
            with st.container():
                resultado = buscar_ofertas(contexto)
                st.session_state.ultimo_intento = resultado
                if not resultado["error"]:
                    try:
                        nuevas = guardar_evaluaciones(contexto, resultado)
                    except OSError:
                        nuevas = {"contexto": contexto, "huella": huella_contexto(contexto), **resultado}
                        st.session_state.aviso_guardado = "Resultados disponibles en sesión, pero no se pudieron guardar en disco."
                    st.session_state.guardadas = nuevas
        finally:
            st.session_state.buscando = False
            candado.release()
        st.rerun()

if st.session_state.get("ultimo_intento", {}).get("error"):
    st.error("El último intento tuvo un error técnico. Se conservan los resultados anteriores, si existen.")
if st.session_state.get("aviso_guardado"):
    st.warning(st.session_state.aviso_guardado)


def mostrar_oferta(item):
    oferta = item["oferta"]
    with st.container(border=True):
        st.subheader(f"{oferta.puesto} · {oferta.empresa}")
        st.text("Ubicación: " + oferta.ubicacion)
        st.link_button("Ver publicación", oferta.enlace)
        explicaciones = explicar_oferta(oferta, separar_usuario=True, perfil=perfil)
        for clave, titulo in (("interes", "Motivos de interés"), ("cumplidos", "Requisitos que cumple"),
                              ("parciales", "Coincidencias parciales"), ("gaps", "Gaps"),
                              ("pendientes", "Sobre la oferta · Información pendiente de confirmar")):
            st.write("**" + titulo + "**")
            for explicacion in explicaciones[clave]:
                st.text("• " + explicacion)
            if not explicaciones[clave]:
                puesto = next(c for c in oferta.criterios if c.nombre == "puesto")
                falta_interes = ("Falta una descripción de las funciones para compararlas con tus objetivos."
                    if not puesto.evidencias_oferta else "Falta concretar qué funciones buscas para relacionarlas con esta oferta."
                    if not puesto.evidencias_perfil else "La evaluación no ha identificado una coincidencia con tus objetivos o preferencias.")
                st.caption({"interes": falta_interes,
                            "cumplidos": "Todavía no hay requisitos plenamente acreditados.",
                            "parciales": "No se han identificado coincidencias parciales.",
                            "gaps": "No hay incumplimientos confirmados.",
                            "pendientes": "No hay preguntas pendientes."}[clave])
        with st.expander("Ver detalles"):
            for criterio in oferta.criterios:
                st.write("**" + CRITERIOS[criterio.nombre] + "**")
                st.text("Descripción: " + ("; ".join(criterio.evidencias_oferta) or criterio.evidencia_oferta))
                st.text("Perfil: " + ("; ".join(criterio.evidencias_perfil) or criterio.evidencia_perfil))

if guardadas:
    st.subheader("Resultado de Busqueda" if obsoletas else "Resultados de búsqueda")
    try:
        fecha = datetime.fromisoformat(guardadas["fecha"].replace("Z", "+00:00"))
        visible = fecha.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M (%Z)")
    except (KeyError, TypeError, ValueError):
        visible = "No documentado"
    st.caption(f"Búsqueda: {visible}")
    try:
        pesos_resultados = normalizar_pesos(guardadas.get("contexto", {}).get("perfil", {}).get("preferencias", {})) if obsoletas else pesos
        ordenadas = ordenar_evaluaciones(guardadas.get("evaluaciones", []), pesos_resultados)
    except ValueError:
        st.error("Las evaluaciones anteriores no son compatibles. Hace falta una nueva búsqueda.")
        ordenadas = []
    if not ordenadas:
        st.info("No hay ofertas evaluables.")
    for item in ordenadas[:5]:
        mostrar_oferta(item)
    mostrar_mejoras([item["oferta"] for item in ordenadas[:5]], perfil)
    if st.session_state.get("perfil_enriquecido") or obsoletas:
        if st.button("Actualizar recomendaciones", disabled=st.session_state.buscando):
            try:
                with st.spinner("Actualizando recomendaciones…"):
                    resultado = reevaluar_ofertas(contexto, guardadas)
                    nuevas = guardar_evaluaciones(contexto, resultado)
                    st.session_state.guardadas = nuevas
                    st.session_state.perfil_enriquecido = False
                st.rerun()
            except Exception:
                st.error("No se pudieron actualizar las recomendaciones. Se conservan los resultados anteriores.")

