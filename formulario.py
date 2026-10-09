"""Formulario con borrador en sesión; guardar es la única escritura de perfil."""

import copy
import hashlib

import streamlit as st

from datos_locales import ARCHIVO_PERFIL, guardar_json, leer_json
from perfil import (EXPERIENCIAS, MODALIDADES, MONEDAS, NIVELES, PREFERENCIAS,
                    anadir_opcion, identidad, migrar_perfil, validar_perfil)
from trayectoria import mostrar_entradas, empresa_para_excluir, titulo_entrada, DATOS_PERSONALES, iniciar_entrada, validar_entrada
from skills_datos import eliminar_skill, posible_equivalencia, fuentes_de_skill, agregar_fuente
from validaciones import entrada_completa


def indice_opcional(opciones, valor):
    return opciones.index(valor) if valor in opciones else None


def iniciar_edicion(bloque=None, entrada=None):
    for clave in list(st.session_state):
        if clave.startswith("editor_"):
            del st.session_state[clave]
    st.session_state.borrador = migrar_perfil(st.session_state.perfil)
    st.session_state.editando = True
    st.session_state.error_formulario = ""
    st.session_state.entrada_activa = None
    st.session_state.bloque_edicion = bloque
    st.session_state.entrada_edicion_id = None
    if bloque in ("experiencias", "formacion", "proyectos"):
        iniciar_entrada(bloque, entrada)
        st.session_state.entrada_edicion_id = st.session_state.entrada_activa["dato"]["id"]


def clave_opcion(campo, texto):
    return "editor_" + campo + "_" + hashlib.sha256(identidad(texto).encode()).hexdigest()[:16]


def opciones_texto(campo, etiqueta, limite, propiedad=None, preferencia=False, niveles=False):
    borrador = st.session_state.borrador
    opciones = [o[propiedad] for o in borrador[campo]] if propiedad else list(borrador[campo])
    st.markdown(f"**{etiqueta} · {len(opciones)}/{limite}**" if limite else f"**{etiqueta} · {len(opciones)}**")
    entrada = "editor_nuevo_" + campo
    izquierda, derecha = st.columns([4, 1])
    izquierda.text_input("Añadir " + etiqueta.lower(), key=entrada, label_visibility="collapsed", placeholder=etiqueta)

    def anadir():
        try:
            existentes = [o[propiedad] for o in borrador[campo]] if propiedad else borrador[campo]
            nueva = anadir_opcion(existentes, st.session_state.get(entrada, ""), limite)[-1]
            if propiedad:
                valor = {propiedad: nueva, "preferencia": None} if preferencia else {propiedad: nueva, "nivel": None}
            else:
                valor = nueva
            borrador[campo].append(valor)
            if campo == "skills":
                borrador["origen_skills"][nueva] = {"tipo": "Declaración del usuario"}
            st.session_state[entrada] = ""
            st.session_state.error_formulario = ""
        except ValueError as error:
            st.session_state.error_formulario = str(error)
    derecha.button("Añadir", key="editor_anadir_" + campo, on_click=anadir,
                   disabled=bool(limite and len(opciones) >= limite))

    for opcion in list(borrador[campo]):
        texto = opcion[propiedad] if propiedad else opcion
        etiqueta_col, valor_col, eliminar_col = st.columns([3, 2, 1])
        etiqueta_col.text(texto)
        if preferencia:
            opcion["preferencia"] = valor_col.selectbox("Preferencia de " + texto, PREFERENCIAS,
                index=indice_opcional(PREFERENCIAS, opcion["preferencia"]), key=clave_opcion(campo + "_preferencia", texto))
        if niveles:
            opcion["nivel"] = valor_col.selectbox("Nivel de " + texto, NIVELES,
                index=indice_opcional(NIVELES, opcion["nivel"]), key=clave_opcion(campo + "_nivel", texto))
        if campo in ("skills", "idiomas"):
            def editar(texto=texto):
                st.session_state["editor_modificando_" + campo] = texto
                st.session_state["editor_nombre_" + campo] = texto
            etiqueta_col.button("Editar", key=clave_opcion(campo + "_editar", texto), on_click=editar)
            if campo == "skills" and borrador["origen_skills"].get(texto):
                etiqueta_col.caption("Origen: " + borrador["origen_skills"][texto].get("tipo", "Declaración del usuario"))
        def eliminar(texto=texto):
            if campo == "skills":
                eliminar_skill(borrador, texto)
            else:
                borrador[campo] = [o for o in borrador[campo] if identidad(o[propiedad] if propiedad else o) != identidad(texto)]
            for sufijo in ("_preferencia", "_nivel"):
                st.session_state.pop(clave_opcion(campo + sufijo, texto), None)
            st.session_state.error_formulario = ""
        eliminar_col.button("Eliminar", key=clave_opcion(campo + "_eliminar", texto),
                            on_click=eliminar, help="Eliminar " + texto)
    anterior = st.session_state.get("editor_modificando_" + campo)
    if anterior and anterior in opciones:
        nuevo = st.text_input("Editar " + etiqueta.lower(), key="editor_nombre_" + campo)
        if st.button("Aplicar cambio", key="editor_aplicar_" + campo):
            try:
                otros = [o for o in opciones if o != anterior]
                nombre = anadir_opcion(otros, nuevo, limite)[-1]
                if propiedad:
                    for o in borrador[campo]:
                        if o[propiedad] == anterior:
                            o[propiedad] = nombre
                else:
                    borrador[campo] = [nombre if o == anterior else o for o in borrador[campo]]
                    origen = borrador["origen_skills"].pop(anterior, {"tipo": "Declaración del usuario"})
                    borrador["origen_skills"][nombre] = {**origen, "editada_por_usuario": True}
                st.session_state.pop("editor_modificando_" + campo, None)
                st.rerun()
            except ValueError as error:
                st.error(str(error))


def mostrar_formulario():
    if st.session_state.get("bloque_edicion"):
        mostrar_editor_individual()
        return
    borrador = st.session_state.borrador
    borrador.setdefault("empresa_actual", "")
    borrador.setdefault("excluir_empresa_actual", False)
    st.subheader("Editar perfil" if st.session_state.perfil else "Crear perfil")
    st.caption("Puedes guardar un perfil incompleto. Solo Guardar perfil guarda tus cambios; nada se envía mientras editas.")
    if st.session_state.get("error_formulario"):
        st.error(st.session_state.error_formulario)
    personales, trayectoria, preferencias = st.tabs(["Datos personales", "Trayectoria profesional", "Preferencias de búsqueda"])
    with personales:
        for clave, etiqueta in DATOS_PERSONALES:
            borrador["datos_cv"][clave] = st.text_input(etiqueta, value=borrador["datos_cv"][clave], key="editor_cv_" + clave)
    with trayectoria:
        for campo in ("experiencias", "formacion", "proyectos"):
            mostrar_entradas(campo, borrador)
        with st.expander("Experiencia general registrada"):
            borrador["experiencia"] = st.selectbox("Experiencia", EXPERIENCIAS[1:],
                index=indice_opcional(EXPERIENCIAS[1:], borrador["experiencia"]), key="editor_experiencia") or "Sin especificar"
            st.caption("Este rango se conserva; no se convierte en empleos ni fechas.")
        opciones_texto("skills", "Capacidades/skills", 10)
        opciones_texto("idiomas", "Idiomas", None, "idioma", niveles=True)
    with preferencias:
        actuales = [e for e in borrador["experiencias"] if e.get("actual") and e.get("empresa")]
        if not borrador["experiencias"]:
            borrador["empresa_actual"] = st.text_input("Empresa actual", value=borrador["empresa_actual"], key="editor_empresa_actual")
        elif len(actuales) > 1:
            ids = [e["id"] for e in actuales]
            borrador["experiencia_excluida_id"] = st.selectbox("Empresa actual que quieres excluir", ids,
                format_func=lambda clave: next(titulo_entrada("experiencias", e) for e in actuales if e["id"] == clave),
                index=indice_opcional(ids, borrador["experiencia_excluida_id"]), key="editor_empresa_elegida")
        st.caption("Empresa para excluir: " + (empresa_para_excluir(borrador) or "Sin seleccionar"))
        borrador["excluir_empresa_actual"] = st.checkbox("Excluir ofertas de esta empresa", value=borrador["excluir_empresa_actual"], key="editor_excluir_empresa")
        opciones_texto("puestos_objetivo", "Puestos objetivo/de interés", 5)
        opciones_texto("ubicaciones", "Ubicaciones", 5, "nombre", preferencia=True)
        borrador["importancia_ubicacion"] = st.selectbox("Importancia global de la ubicación", PREFERENCIAS,
            index=indice_opcional(PREFERENCIAS, borrador["importancia_ubicacion"]), key="editor_importancia_ubicacion")
        st.markdown("**Modalidad**")
        for modalidad in MODALIDADES:
            izquierda, derecha = st.columns(2)
            seleccionada = izquierda.checkbox(modalidad, value=modalidad in borrador["modalidades"], key="editor_modalidad_" + modalidad)
            preferencia = derecha.selectbox("Preferencia de " + modalidad, PREFERENCIAS,
                index=indice_opcional(PREFERENCIAS, borrador["modalidades"].get(modalidad)),
                disabled=not seleccionada, key="editor_preferencia_modalidad_" + modalidad)
            if seleccionada:
                borrador["modalidades"][modalidad] = preferencia
            else:
                borrador["modalidades"].pop(modalidad, None)
        borrador["importancia_modalidad"] = st.selectbox("Importancia global de la modalidad", PREFERENCIAS,
            index=indice_opcional(PREFERENCIAS, borrador["importancia_modalidad"]), key="editor_importancia_modalidad")
        especificar = st.checkbox("Especificar salario mínimo bruto anual", value=borrador["salario_minimo"] is not None, key="editor_especificar_salario")
        importe, moneda = st.columns(2)
        minimo = importe.number_input("Salario mínimo bruto anual", min_value=0.0,
            value=float(borrador["salario_minimo"]) if borrador["salario_minimo"] is not None else None, step=1000.0,
            disabled=not especificar, key="editor_salario")
        borrador["moneda"] = moneda.selectbox("Moneda", MONEDAS,
            index=indice_opcional(MONEDAS, borrador["moneda"]), disabled=not especificar, key="editor_moneda")
        borrador["salario_minimo"] = minimo if especificar else None
        borrador["importancia_salario"] = st.selectbox("Importancia del salario", PREFERENCIAS,
            index=indice_opcional(PREFERENCIAS, borrador["importancia_salario"]), key="editor_importancia_salario")
        borrador["que_buscas"] = st.text_area("¿Qué buscas?", value=borrador["que_buscas"],
            max_chars=400, key="editor_que_buscas", help="Tus aspiraciones orientan los puestos; no acreditan experiencia ni capacidades.")
        st.caption(f"{len(borrador['que_buscas'])}/400 caracteres")
    guardar, cancelar = st.columns(2)
    if guardar.button("Guardar perfil", type="primary", key="editor_guardar"):
        try:
            # Texto sin pulsar Añadir no se pierde ni se añade implícitamente.
            if any(st.session_state.get("editor_nuevo_" + c, "").strip() for c in ("puestos_objetivo", "ubicaciones", "skills", "idiomas")):
                raise ValueError("Pulsa Añadir para guardar las opciones pendientes o borra su texto.")
            if st.session_state.get("entrada_activa"):
                raise ValueError("Guarda o cancela la entrada abierta antes de guardar el perfil.")
            validar_perfil(borrador, anterior=leer_json(ARCHIVO_PERFIL, {}))
            guardar_json(ARCHIVO_PERFIL, borrador)
            st.session_state.perfil = copy.deepcopy(borrador)
            st.session_state.editando = False
            st.session_state.perfil_guardado = True
            st.session_state.borrador = None
            st.rerun()
        except (OSError, ValueError) as error:
            st.error(str(error) if isinstance(error, ValueError) else "No se pudo guardar el perfil.")
    if cancelar.button("Cancelar", key="editor_cancelar"):
        st.session_state.editando = False
        st.session_state.borrador = None
        st.rerun()


def cerrar_editor():
    st.session_state.editando = False
    st.session_state.borrador = None
    st.session_state.bloque_edicion = None
    st.session_state.entrada_activa = None
    st.rerun()


def mostrar_editor_individual():
    campo = st.session_state.bloque_edicion
    borrador = st.session_state.borrador
    etiquetas = {"puestos_objetivo": "Puestos objetivo", "ubicaciones": "Ubicaciones", "modalidades": "Modalidad",
                 "salario": "Salario", "skills": "Skills", "idiomas": "Idiomas", "que_buscas": "¿Qué buscas?"}
    st.subheader("Editar " + etiquetas.get(campo, campo.replace("cv:", "")))
    claves = [campo]
    if campo.startswith("cv:"):
        clave = campo[3:]
        etiqueta = dict(DATOS_PERSONALES)[clave]
        borrador["datos_cv"][clave] = st.text_input(etiqueta, value=borrador["datos_cv"][clave], key="editor_cv_" + clave)
    elif campo in ("experiencias", "formacion", "proyectos"):
        mostrar_entradas(campo, borrador, solo_editor=True)
    elif campo in ("skills", "puestos_objetivo", "idiomas", "ubicaciones"):
        opciones_texto(campo, etiquetas[campo], {"skills": 10, "puestos_objetivo": 5, "ubicaciones": 5}.get(campo),
                      {"idiomas": "idioma", "ubicaciones": "nombre"}.get(campo),
                      preferencia=campo == "ubicaciones", niveles=campo == "idiomas")
        if campo == "skills":
            claves += ["origen_skills", "skills_rechazadas", "archivo_fuentes_skills"]
        if campo == "ubicaciones":
            claves += ["importancia_ubicacion"]
            borrador["importancia_ubicacion"] = st.selectbox("Importancia global de la ubicación", PREFERENCIAS,
                index=indice_opcional(PREFERENCIAS, borrador["importancia_ubicacion"]), key="editor_importancia_ubicacion")
    elif campo == "modalidades":
        claves += ["importancia_modalidad"]
        for modalidad in MODALIDADES:
            seleccionada = st.checkbox(modalidad, value=modalidad in borrador["modalidades"], key="editor_modalidad_" + modalidad)
            preferencia = st.selectbox("Preferencia de " + modalidad, PREFERENCIAS,
                index=indice_opcional(PREFERENCIAS, borrador["modalidades"].get(modalidad)),
                disabled=not seleccionada, key="editor_preferencia_modalidad_" + modalidad)
            if seleccionada:
                borrador["modalidades"][modalidad] = preferencia
            else:
                borrador["modalidades"].pop(modalidad, None)
        borrador["importancia_modalidad"] = st.selectbox("Importancia global de la modalidad", PREFERENCIAS,
            index=indice_opcional(PREFERENCIAS, borrador["importancia_modalidad"]), key="editor_importancia_modalidad")
    elif campo == "salario":
        claves = ["salario_minimo", "moneda", "importancia_salario"]
        especificar = st.checkbox("Especificar salario mínimo bruto anual", value=borrador["salario_minimo"] is not None, key="editor_especificar_salario")
        minimo = st.number_input("Salario mínimo bruto anual", min_value=0.0,
            value=float(borrador["salario_minimo"]) if borrador["salario_minimo"] is not None else None,
            step=1000.0, disabled=not especificar, key="editor_salario")
        borrador["salario_minimo"] = minimo if especificar else None
        borrador["moneda"] = st.selectbox("Moneda", MONEDAS,
            index=indice_opcional(MONEDAS, borrador["moneda"]), disabled=not especificar, key="editor_moneda")
        borrador["importancia_salario"] = st.selectbox("Importancia del salario", PREFERENCIAS,
            index=indice_opcional(PREFERENCIAS, borrador["importancia_salario"]), key="editor_importancia_salario")
    elif campo == "que_buscas":
        borrador[campo] = st.text_area("¿Qué buscas?", value=borrador[campo], max_chars=400, key="editor_que_buscas")
        st.caption(f"{len(borrador[campo])}/400 caracteres")
    if st.session_state.get("error_formulario"):
        st.error(st.session_state.error_formulario)
    guardar, cancelar = st.columns(2)
    if guardar.button("Guardar", key="editor_guardar_individual", type="primary"):
        try:
            if st.session_state.get("editor_nuevo_" + campo, "").strip():
                raise ValueError("Pulsa Añadir o borra el texto pendiente antes de guardar.")
            nuevo = migrar_perfil(leer_json(ARCHIVO_PERFIL, st.session_state.perfil))
            if campo.startswith("cv:"):
                nuevo["datos_cv"][campo[3:]] = borrador["datos_cv"][campo[3:]]
            elif campo in ("experiencias", "formacion", "proyectos"):
                activa = st.session_state.get("entrada_activa")
                identificador = st.session_state.entrada_edicion_id
                entrada = copy.deepcopy(activa["dato"]) if activa else next(e for e in borrador[campo] if e["id"] == identificador)
                validar_entrada(campo, entrada)
                nuevo[campo] = [entrada if e["id"] == identificador else e for e in nuevo[campo]]
                if not any(e["id"] == identificador for e in nuevo[campo]):
                    nuevo[campo].append(entrada)
            else:
                for clave in claves:
                    nuevo[clave] = copy.deepcopy(borrador.get(clave, {} if clave != "skills_rechazadas" else []))
            validar_perfil(nuevo, anterior=leer_json(ARCHIVO_PERFIL, {}))
            guardar_json(ARCHIVO_PERFIL, nuevo)
            st.session_state.perfil = nuevo
            cerrar_editor()
        except (ValueError, OSError) as error:
            st.error(str(error) if isinstance(error, ValueError) else "No se pudo guardar el cambio.")
    if cancelar.button("Cancelar", key="editor_cancelar_individual"):
        cerrar_editor()


def eliminar_confirmada(skill):
    nuevo = migrar_perfil(leer_json(ARCHIVO_PERFIL, st.session_state.perfil))
    eliminar_skill(nuevo, skill)
    guardar_json(ARCHIVO_PERFIL, nuevo)
    st.session_state.perfil = nuevo


def eliminar_entrada_guardada(campo, identificador):
    nuevo = migrar_perfil(leer_json(ARCHIVO_PERFIL, st.session_state.perfil))
    nuevo[campo] = [e for e in nuevo[campo] if e["id"] != identificador]
    guardar_json(ARCHIVO_PERFIL, nuevo)
    st.session_state.perfil = nuevo


def boton_editar(campo, disabled=False):
    st.button("Editar", key="resumen_editar_" + campo, on_click=iniciar_edicion, args=(campo,), disabled=disabled)


def resumen_editable(campo, texto, disabled=False):
    valor, editar = st.columns([5, 1])
    valor.write(texto)
    with editar:
        boton_editar(campo, disabled)


def fusionar_confirmadas(conservar, fusionar):
    nuevo = migrar_perfil(leer_json(ARCHIVO_PERFIL, st.session_state.perfil))
    fuentes = copy.deepcopy(fuentes_de_skill(nuevo, fusionar))
    eliminar_skill(nuevo, fusionar)
    for fuente in fuentes:
        agregar_fuente(nuevo, conservar, fuente)
    guardar_json(ARCHIVO_PERFIL, nuevo)
    st.session_state.perfil = nuevo


def mostrar_resumen(perfil, deshabilitar_edicion=False):
    perfil = migrar_perfil(perfil)
    st.subheader("Tu perfil")
    personales, trayectoria, preferencias = st.tabs(["Datos personales", "Trayectoria profesional", "Preferencias de búsqueda"])
    with personales:
        for campo, etiqueta in DATOS_PERSONALES:
            resumen_editable("cv:" + campo, etiqueta + ": " + (perfil["datos_cv"][campo] or "Sin especificar"), deshabilitar_edicion)
    with trayectoria:
        for campo, etiqueta in (("experiencias", "Experiencia laboral"), ("formacion", "Formación"), ("proyectos", "Proyectos")):
            st.write("**" + etiqueta + "**")
            for entrada in perfil[campo]:
                with st.container(border=True):
                    st.write(titulo_entrada(campo, entrada))
                    if not entrada_completa(campo, entrada):
                        st.caption("Pendiente de completar")
                    editar, eliminar = st.columns(2)
                    editar.button("Editar", key="resumen_entrada_" + entrada["id"], on_click=iniciar_edicion,
                                  args=(campo, entrada), disabled=deshabilitar_edicion)
                    eliminar.button("Eliminar", key="resumen_eliminar_" + entrada["id"], on_click=eliminar_entrada_guardada,
                                    args=(campo, entrada["id"]), disabled=deshabilitar_edicion)
            if not perfil[campo]:
                st.caption("Todavía sin registrar")
            st.button({"experiencias": "Añadir experiencia", "formacion": "Añadir estudios", "proyectos": "Añadir proyecto"}[campo],
                key="resumen_anadir_" + campo, on_click=iniciar_edicion, args=(campo,), disabled=deshabilitar_edicion)
        st.caption("Experiencia general registrada: " + perfil["experiencia"])
        resumen_editable("skills", f"**Skills confirmadas · {len(perfil['skills'])}/10**", deshabilitar_edicion)
        for skill in perfil["skills"]:
            valor, eliminar = st.columns([5, 1])
            valor.text(skill)
            eliminar.button("Eliminar", key=clave_opcion("resumen_skill_eliminar", skill), on_click=eliminar_confirmada,
                            args=(skill,), disabled=deshabilitar_edicion)
        for i, skill in enumerate(perfil["skills"]):
            equivalente = posible_equivalencia(skill, perfil["skills"][i + 1:])
            if equivalente:
                st.caption(f"«{skill}» y «{equivalente}» podrían ser equivalentes. Si confirmas la fusión, se conservará «{skill}» y sus fuentes.")
                st.button("Confirmar fusión", key=clave_opcion("fusion_confirmadas", skill),
                    on_click=fusionar_confirmadas, args=(skill, equivalente), disabled=deshabilitar_edicion)
        if not deshabilitar_edicion:
            from skills import mostrar_propuestas
            mostrar_propuestas(perfil)
        resumen_editable("idiomas", "**Idiomas:** " + ("; ".join(f"{i['idioma']} ({i['nivel'] or 'Sin especificar'})" for i in perfil["idiomas"]) or "Sin especificar"), deshabilitar_edicion)
    with preferencias:
        st.write("**Empresa para excluir:** " + (empresa_para_excluir(perfil) or "Sin seleccionar"))
        st.caption("Excluir ofertas de esta empresa: " + ("Sí" if perfil["excluir_empresa_actual"] else "No"))
        resumen_editable("puestos_objetivo", "**Puestos objetivo:** " + (", ".join(perfil["puestos_objetivo"]) or "No especificado"), deshabilitar_edicion)
        resumen_editable("ubicaciones", "**Ubicaciones:** " + ("; ".join(f"{u['nombre']} ({u['preferencia'] or 'Sin especificar'})" for u in perfil["ubicaciones"]) or "No especificado"), deshabilitar_edicion)
        st.caption("Importancia global de ubicación: " + (perfil["importancia_ubicacion"] or "Sin especificar"))
        resumen_editable("modalidades", "**Modalidades:** " + ("; ".join(f"{m} ({p or 'Sin especificar'})" for m, p in perfil["modalidades"].items()) or "No especificado"), deshabilitar_edicion)
        st.caption("Importancia global de modalidad: " + (perfil["importancia_modalidad"] or "Sin especificar"))
        salario = "No especificado" if perfil["salario_minimo"] is None else f"{perfil['salario_minimo']:,.2f} {perfil['moneda'] or 'moneda sin especificar'} bruto anual"
        resumen_editable("salario", "**Salario mínimo:** " + salario, deshabilitar_edicion)
        st.caption("Importancia del salario: " + (perfil["importancia_salario"] or "Sin especificar"))
        resumen_editable("que_buscas", "**¿Qué buscas?**", deshabilitar_edicion)
        st.text(perfil["que_buscas"] or "No especificado")
    st.button("Editar perfil", on_click=iniciar_edicion, disabled=deshabilitar_edicion)
