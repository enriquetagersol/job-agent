"""Propuestas explícitas con fuente; nunca incorporadas sin confirmación."""

import os
import json
from pathlib import Path
from typing import List

import streamlit as st
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

from datos_locales import ARCHIVO_PERFIL, guardar_json, leer_json
from evaluacion import cita_documentada
from perfil import anadir_opcion, identidad, migrar_perfil
from trayectoria import titulo_entrada
from skills_datos import (registrar_rechazo, huella_evidencia, normalizar, agregar_fuente,
                         posible_equivalencia)


class Propuesta(BaseModel):
    skill: str
    campo: str
    entrada_id: str
    cita: str


class Propuestas(BaseModel):
    propuestas: List[Propuesta]


def fuentes_skills(perfil):
    fuentes = []
    for campo, claves in (("experiencias", ("responsabilidades", "logros", "herramientas")),
                         ("formacion", ("contenidos", "proyectos")),
                         ("proyectos", ("descripcion", "contribucion", "herramientas"))):
        for entrada in perfil.get(campo, []):
            texto = "\n".join(entrada.get(c, "").strip() for c in claves if entrada.get(c, "").strip())
            if texto:
                fuentes.append({"campo": campo, "entrada_id": entrada["id"], "texto": texto})
    return fuentes


def filtrar_propuestas(propuestas, fuentes, existentes, rechazadas=None):
    origenes = {(f["campo"], f["entrada_id"]): f["texto"] for f in fuentes}
    vistas = {identidad(s) for s in existentes}
    validas = []
    for propuesta in propuestas:
        texto = origenes.get((propuesta.campo, propuesta.entrada_id), "")
        huella = huella_evidencia(propuesta.campo, propuesta.entrada_id, propuesta.cita)
        contexto = huella_evidencia(propuesta.campo, propuesta.entrada_id, texto)
        if any((d["evidencia"] == huella or d.get("contexto") == contexto) and (d["skill"] == normalizar(propuesta.skill) or
               posible_equivalencia(propuesta.skill, [d["skill"]])) for d in (rechazadas or [])):
            continue
        if not propuesta.skill.strip() or identidad(propuesta.skill) in vistas or not cita_documentada(propuesta.cita, texto):
            continue
        vistas.add(identidad(propuesta.skill))
        validas.append(propuesta.model_dump())
    return validas[:10]


def proponer_skills(perfil):
    fuentes = fuentes_skills(perfil)
    if not fuentes:
        return []
    load_dotenv(Path(__file__).parent / ".env")
    with OpenAI(max_retries=0, timeout=60.0) as modelo:
        respuesta = modelo.responses.parse(model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
            instructions="Propón hasta diez skills a partir SOLO de los contenidos o tareas descritos. "
                "No uses títulos, aspiraciones ni preferencias. No asignes dominio ni experiencia. "
                "Aporta una cita literal continua y el campo/entrada_id exactos. La persona debe confirmarlas.",
            input=json.dumps({"fuentes": fuentes, "skills_existentes": perfil["skills"]}, ensure_ascii=False),
            text_format=Propuestas, reasoning={"effort": "none"}, max_output_tokens=1800, store=False)
        if respuesta.status != "completed" or respuesta.output_parsed is None:
            raise ValueError("Propuesta incompleta")
    return filtrar_propuestas(respuesta.output_parsed.propuestas, fuentes, perfil["skills"], perfil.get("skills_rechazadas", []))


def mostrar_propuestas(perfil):
    with st.container():
        st.caption("Te sugerimos habilidades basadas en tu trayectoria. Revisa y añade las que te representan")
        if len(perfil["skills"]) >= 10:
            st.caption("Has alcanzado el límite de 10 skills confirmadas. Elimina una para añadir otra; las propuestas pendientes no ocupan huecos.")
        fuentes = fuentes_skills(perfil)
        if not fuentes:
            st.caption("Describe y guarda las tareas, conocimientos o herramientas de alguna experiencia, estudio o proyecto para proponer skills.")
        if st.button("Proponer skills", disabled=not fuentes):
            try:
                with st.spinner("Preparando propuestas…"):
                    propuestas = proponer_skills(perfil)
                nuevo = migrar_perfil(leer_json(ARCHIVO_PERFIL, st.session_state.perfil))
                nuevo["skills_propuestas"] = propuestas
                guardar_json(ARCHIVO_PERFIL, nuevo)
                st.session_state.perfil = nuevo
                st.rerun()
            except Exception:
                st.error("No se pudieron preparar propuestas. El perfil no ha cambiado.")
        pendientes = filtrar_propuestas([Propuesta(**p) for p in perfil.get("skills_propuestas", [])],
                                       fuentes_skills(perfil), perfil["skills"], perfil.get("skills_rechazadas", []))
        for p in pendientes:
            clave = p["campo"] + p["entrada_id"] + identidad(p["skill"])
            entrada = next(e for e in perfil[p["campo"]] if e["id"] == p["entrada_id"])
            st.write(p["skill"])
            st.caption("Se propone a partir de " + titulo_entrada(p["campo"], entrada) + ": «" + p["cita"] + "»")
            skill = st.text_input("Skill que confirmarás", value=p["skill"], key="skill_propuesta_" + clave)
            equivalente = posible_equivalencia(skill, perfil["skills"])
            fusionar = False
            if equivalente:
                st.caption(f"Podría equivaler a «{equivalente}». Puedes fusionarlas o mantenerlas distintas.")
                fusionar = st.checkbox("Fusionar con " + equivalente, key="skill_fusionar_" + clave)
            if st.button("Confirmar fusión" if fusionar else "Añadir", key="skill_confirmar_" + clave,
                         disabled=len(perfil["skills"]) >= 10 and not fusionar):
                try:
                    nuevo = migrar_perfil(leer_json(ARCHIVO_PERFIL, st.session_state.perfil))
                    nueva = equivalente if fusionar else anadir_opcion(nuevo["skills"], skill, 10)[-1]
                    if not fusionar:
                        nuevo["skills"].append(nueva)
                    fuente = {"tipo": {"experiencias": "Experiencia laboral", "formacion": "Formación", "proyectos": "Proyecto"}[p["campo"]], "campo": p["campo"],
                        "entrada_id": p["entrada_id"], "cita": p["cita"], "confirmada_por_usuario": True,
                        "skill_original": p["skill"], "editada_por_usuario": skill.strip() != p["skill"]}
                    agregar_fuente(nuevo, nueva, fuente)
                    registrar_rechazo(nuevo, p["skill"], fuente)
                    nuevo["skills_propuestas"] = [v for v in nuevo.get("skills_propuestas", []) if v != p]
                    guardar_json(ARCHIVO_PERFIL, nuevo)
                    st.session_state.perfil = nuevo
                    st.session_state.perfil_enriquecido = True
                    st.rerun()
                except (ValueError, OSError) as error:
                    st.error(str(error) if isinstance(error, ValueError) else "No se pudo guardar la skill.")
            if st.button("Descartar", key="skill_descartar_" + clave):
                nuevo = migrar_perfil(leer_json(ARCHIVO_PERFIL, st.session_state.perfil))
                registrar_rechazo(nuevo, p["skill"], p)
                nuevo["skills_propuestas"] = [v for v in nuevo.get("skills_propuestas", []) if v != p]
                guardar_json(ARCHIVO_PERFIL, nuevo)
                st.session_state.perfil = nuevo
                st.rerun()
