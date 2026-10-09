"""Preguntas locales y respuestas literales que requieren confirmación."""

import copy
import hashlib
import streamlit as st
from datos_locales import ARCHIVO_PERFIL, guardar_json
from perfil import identidad, migrar_perfil
from evaluacion import cita_documentada


def pendiente_usuario(c, perfil):
    evidencia = c.evidencias_oferta or c.evidencia_oferta
    if c.nombre == "capacidades" and c.skills_declaradas:
        return True
    if c.puntos != "Sin datos" or not evidencia or evidencia == "No documentado":
        return False
    if c.nombre in ("experiencia", "capacidades"):
        return True
    if c.nombre == "idiomas":
        return not c.evidencias_perfil and c.evidencia_perfil.strip() in ("", "No documentado", "Sin datos")
    return False


def preguntas_usuario(ofertas, perfil):
    candidatas = {}
    for oferta in ofertas:
        for c in oferta.criterios:
            preguntas = []
            if not pendiente_usuario(c, perfil):
                continue
            if c.nombre == "experiencia":
                registradas = [e.get(k, "") for campo, claves in (
                    ("experiencias", ("responsabilidades", "logros")),
                    ("proyectos", ("descripcion", "contribucion")),
                    ("formacion", ("contenidos", "proyectos"))) for e in perfil.get(campo, [])
                    for k in claves if e.get(k)]
                if not registradas:
                    preguntas.append(("experiencia_tareas", "¿Qué tareas o proyectos has realizado? Indica si fueron laborales, académicos o personales, tu papel y la duración."))
                elif not c.evidencias_perfil:
                    cita = "; ".join(c.evidencias_oferta) or c.evidencia_oferta
                    if not any(cita_documentada(cita, t) for t in registradas):
                        clave = "experiencia:" + hashlib.sha256(identidad(cita).encode()).hexdigest()[:16]
                        preguntas.append((clave, f"Tu experiencia ya está registrada. Para el requisito «{cita}», ¿qué dato adicional puedes confirmar que todavía no figure en ella?"))
            if c.nombre == "capacidades" and c.skills_declaradas:
                for skill in c.skills_declaradas:
                    aplicada = any(cita_documentada(skill, " ".join(e.get(k, "") for k in claves))
                        and any(e.get(k, "").strip() for k in tareas)
                        for campo, claves, tareas in (("experiencias", ("herramientas", "responsabilidades", "logros"), ("responsabilidades", "logros")),
                            ("proyectos", ("herramientas", "descripcion", "contribucion"), ("contribucion",))) for e in perfil.get(campo, []))
                    if not aplicada:
                        preguntas.append(("skill:" + identidad(skill), f"¿Cómo has utilizado {skill}? Describe una tarea o proyecto, su contexto y qué hiciste tú."))
            elif c.nombre == "capacidades":
                cita = "; ".join(c.evidencias_oferta) or c.evidencia_oferta
                textos = [e.get(k, "") for campo, claves in (
                    ("experiencias", ("responsabilidades", "logros", "herramientas")),
                    ("formacion", ("contenidos", "proyectos")),
                    ("proyectos", ("descripcion", "contribucion", "herramientas")))
                    for e in perfil.get(campo, []) for k in claves]
                if not any(cita_documentada(cita, t) for t in textos):
                    clave = "requisito:" + hashlib.sha256(identidad(cita).encode()).hexdigest()[:16]
                    preguntas.append((clave, f"La oferta pide «{cita}». ¿Qué conocimientos o práctica puedes describir sobre ese requisito?"))
            if c.nombre == "idiomas":
                preguntas.append(("idiomas", "¿Qué idiomas conoces y qué nivel declaras para cada uno?"))
            for clave, pregunta in preguntas:
                dato = candidatas.setdefault(clave, {"pregunta": pregunta, "relevancia": 0})
                dato["relevancia"] += 1
    respondidas = perfil.get("respuestas_confirmadas", {})
    omitidas = perfil.get("preguntas_omitidas", [])
    return [(k, v["pregunta"]) for k, v in sorted(candidatas.items(), key=lambda par: -par[1]["relevancia"])
            if k not in respondidas and k not in omitidas][:3]


def guardar_cambio(clave, pregunta, respuesta=None, omitir=False):
    perfil = migrar_perfil(st.session_state.perfil)
    if omitir:
        perfil.setdefault("preguntas_omitidas", []).append(clave)
    elif respuesta is None:
        perfil.setdefault("respuestas_confirmadas", {}).pop(clave, None)
    else:
        perfil.setdefault("respuestas_confirmadas", {})[clave] = {"pregunta": pregunta, "respuesta": respuesta.strip()}
    guardar_json(ARCHIVO_PERFIL, perfil)
    st.session_state.perfil = perfil
    if not omitir:
        st.session_state.perfil_enriquecido = True
    st.rerun()


def mostrar_mejoras(ofertas, perfil):
    preguntas = preguntas_usuario(ofertas, perfil)
    respuestas = perfil.get("respuestas_confirmadas", {})
    if not preguntas and not respuestas and not perfil.get("preguntas_omitidas"):
        return
    st.subheader("Mejorar mi perfil")
    st.caption("Puedes responder u omitir. Solo se guardará una respuesta después de tu confirmación.")
    for clave, pregunta in preguntas:
        st.write(pregunta)
        respuesta = st.text_area("Tu respuesta", key="respuesta_" + clave)
        if st.button("Proponer información", key="proponer_" + clave, disabled=not respuesta.strip()):
            st.session_state["propuesta_" + clave] = respuesta.strip()
        propuesta = st.session_state.get("propuesta_" + clave)
        if propuesta:
            st.write("Se añadirá a tu perfil como declaración literal:")
            st.text(propuesta)
            if st.button("Confirmar y guardar", key="confirmar_" + clave):
                guardar_cambio(clave, pregunta, propuesta)
        if st.button("Omitir", key="omitir_" + clave):
            guardar_cambio(clave, pregunta, omitir=True)
    for clave, dato in respuestas.items():
        with st.expander(dato["pregunta"]):
            st.text(dato["respuesta"])
            nueva = st.text_area("Editar respuesta", value=dato["respuesta"], key="editar_respuesta_" + clave)
            if st.button("Proponer cambio", key="cambio_" + clave, disabled=not nueva.strip()):
                st.session_state["cambio_propuesto_" + clave] = nueva.strip()
            cambio = st.session_state.get("cambio_propuesto_" + clave)
            if cambio:
                st.text("Se guardará: " + cambio)
                if st.button("Confirmar cambio", key="guardar_cambio_" + clave):
                    guardar_cambio(clave, dato["pregunta"], cambio)
            if st.button("Borrar respuesta", key="borrar_" + clave):
                guardar_cambio(clave, dato["pregunta"])
    if perfil.get("preguntas_omitidas") and st.button("Volver a mostrar preguntas omitidas"):
        nuevo = copy.deepcopy(st.session_state.perfil)
        nuevo["preguntas_omitidas"] = []
        guardar_json(ARCHIVO_PERFIL, nuevo)
        st.session_state.perfil = nuevo
        st.rerun()
