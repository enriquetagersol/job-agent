"""Entradas de trayectoria: datos literales, fechas opcionales y edición local."""

import copy
import uuid
import streamlit as st
from validaciones import faltantes_entrada, entrada_completa

MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")
CAMPOS = {
    "experiencias": {"empresa": "Empresa", "puesto": "Puesto", "responsabilidades": "Descripción de responsabilidades",
                     "logros": "Logros (opcional)", "herramientas": "Herramientas utilizadas (opcional)"},
    "formacion": {"institucion": "Institución", "estudios": "Estudios, titulación o curso",
                  "contenidos": "Contenidos aprendidos (opcional)", "proyectos": "Proyectos realizados (opcional)"},
    "proyectos": {"nombre": "Nombre", "descripcion": "Descripción", "contribucion": "Contribución personal",
                  "herramientas": "Tecnologías o herramientas utilizadas", "enlace": "Enlace (opcional)"},
}
BOTONES = {"experiencias": "Añadir experiencia", "formacion": "Añadir estudios", "proyectos": "Añadir proyecto"}
DATOS_PERSONALES = (("nombre", "Nombre"), ("apellidos", "Apellidos"), ("telefono", "Número de teléfono"),
                    ("email", "Email"), ("linkedin", "Enlace a LinkedIn"))


def completar_trayectoria(perfil):
    for campo in CAMPOS:
        perfil.setdefault(campo, [])
    perfil.setdefault("datos_cv", {"nombre": "", "email": "", "telefono": "", "enlaces": ""})
    for campo, _ in DATOS_PERSONALES:
        perfil["datos_cv"].setdefault(campo, "")
    perfil.setdefault("origen_skills", {})
    for skill in perfil.get("skills", []):
        perfil["origen_skills"].setdefault(skill, {"tipo": "Perfil anterior (sin origen detallado)"})
    perfil.setdefault("experiencia_excluida_id", None)
    return perfil


def validar_entrada(campo, entrada, exigir_completa=True):
    if not isinstance(entrada, dict) or not isinstance(entrada.get("id"), str):
        raise ValueError("Entrada de trayectoria inválida.")
    if not isinstance(entrada.get("actual", False), bool):
        raise ValueError("La casilla de actividad actual debe ser verdadera o falsa.")
    for clave in CAMPOS[campo]:
        if not isinstance(entrada.get(clave, ""), str):
            raise ValueError("Los datos de trayectoria deben ser texto.")
    if exigir_completa and campo != "proyectos":
        faltan = faltantes_entrada(campo, entrada)
        if faltan:
            raise ValueError("Completa los campos obligatorios: " + "; ".join(faltan))
    if campo == "proyectos":
        return entrada
    fechas = []
    for clave in ("inicio", "fin"):
        fecha = entrada.get(clave, {})
        mes, ano = fecha.get("mes"), fecha.get("ano")
        if mes is not None and (type(mes) is not int or not 1 <= mes <= 12):
            raise ValueError("Mes inválido.")
        if ano is not None and (type(ano) is not int or not 1 <= ano <= 9999):
            raise ValueError("Año inválido.")
        fechas.append((ano, mes))
    if not entrada.get("actual"):
        (ai, mi), (af, mf) = fechas
        if ai and af and (af < ai or (af == ai and mi and mf and mf < mi)):
            raise ValueError("La fecha de fin no puede ser anterior a la de inicio.")
    return entrada


def empresa_para_excluir(perfil):
    experiencias = perfil.get("experiencias", [])
    actuales = [e for e in experiencias if e.get("actual") and e.get("empresa", "").strip()]
    if not experiencias:
        return perfil.get("empresa_actual", "")
    if len(actuales) == 1:
        return actuales[0]["empresa"]
    return next((e["empresa"] for e in actuales if e["id"] == perfil.get("experiencia_excluida_id")), "")


def texto_fecha(fecha):
    return " ".join(str(v) for v in (MESES[fecha["mes"] - 1] if fecha.get("mes") else "", fecha.get("ano") or "") if v)


def titulo_entrada(campo, entrada):
    claves = {"experiencias": ("puesto", "empresa"), "formacion": ("estudios", "institucion"), "proyectos": ("nombre",)}[campo]
    return " · ".join(entrada.get(k, "") for k in claves if entrada.get(k)) or "Entrada sin completar"


def iniciar_entrada(campo, entrada=None):
    for clave in list(st.session_state):
        if clave.startswith("editor_entrada_"):
            del st.session_state[clave]
    dato = copy.deepcopy(entrada) if entrada else {"id": uuid.uuid4().hex}
    st.session_state.entrada_activa = {"campo": campo, "dato": dato}


def fecha_editor(etiqueta, fecha, clave, disabled=False):
    mes, ano = st.columns(2)
    elegido = mes.selectbox("Mes de " + etiqueta, MESES,
        index=fecha["mes"] - 1 if fecha.get("mes") else None, disabled=disabled, key=clave + "_mes")
    valor = ano.number_input("Año de " + etiqueta, min_value=1, max_value=9999,
        value=fecha.get("ano"), step=1, disabled=disabled, key=clave + "_ano")
    return {"mes": MESES.index(elegido) + 1 if elegido else None, "ano": valor}


def mostrar_entradas(campo, perfil, solo_editor=False):
    st.markdown("**" + {"experiencias": "Experiencia laboral", "formacion": "Formación", "proyectos": "Proyectos"}[campo] + "**")
    for entrada in ([] if solo_editor else list(perfil[campo])):
        with st.container(border=True):
            st.write(titulo_entrada(campo, entrada))
            if not entrada_completa(campo, entrada):
                st.caption("Pendiente de completar")
            if campo != "proyectos":
                fechas = [texto_fecha(entrada.get("inicio", {})), "Actualidad" if entrada.get("actual") else texto_fecha(entrada.get("fin", {}))]
                st.caption(" - ".join(f for f in fechas if f))
            descripcion = entrada.get("responsabilidades") or entrada.get("contenidos") or entrada.get("descripcion")
            if descripcion:
                st.text(descripcion[:180] + ("…" if len(descripcion) > 180 else ""))
            editar, eliminar = st.columns(2)
            editar.button("Editar", key="editor_editar_" + entrada["id"], on_click=iniciar_entrada,
                          args=(campo, entrada), disabled=bool(st.session_state.get("entrada_activa")))
            def quitar(identificador=entrada["id"]):
                perfil[campo] = [e for e in perfil[campo] if e["id"] != identificador]
                if (st.session_state.get("entrada_activa") or {}).get("dato", {}).get("id") == identificador:
                    st.session_state.entrada_activa = None
            eliminar.button("Eliminar", key="editor_eliminar_" + entrada["id"], on_click=quitar)
    if not solo_editor:
        st.button(BOTONES[campo], key="editor_anadir_" + campo, on_click=iniciar_entrada, args=(campo,),
                  disabled=bool(st.session_state.get("entrada_activa")))
    activa = st.session_state.get("entrada_activa")
    if not activa or activa["campo"] != campo:
        return
    dato = activa["dato"]
    with st.container(border=True):
        st.caption("Esta entrada se incorpora al borrador. Guardar perfil confirma todos los cambios.")
        for clave, etiqueta in CAMPOS[campo].items():
            if clave in ({"experiencias": ("empresa", "puesto", "responsabilidades"), "formacion": ("institucion", "estudios")}.get(campo, ())):
                etiqueta += " *"
            funcion = st.text_area if clave in ("responsabilidades", "logros", "contenidos", "proyectos", "descripcion", "contribucion", "herramientas") else st.text_input
            dato[clave] = funcion(etiqueta, value=dato.get(clave, ""), key="editor_entrada_" + clave)
        if campo != "proyectos":
            dato["actual"] = st.checkbox("Trabajo aquí actualmente" if campo == "experiencias" else "En curso",
                value=dato.get("actual", False), key="editor_entrada_actual")
            dato["inicio"] = fecha_editor("inicio *", dato.get("inicio", {}), "editor_entrada_inicio")
            fin = fecha_editor("fin" if dato["actual"] else "fin *", dato.get("fin", {}), "editor_entrada_fin", disabled=dato["actual"])
            if not dato["actual"]:
                dato["fin"] = fin
        agregar, cancelar = st.columns(2)
        if agregar.button("Guardar entrada", key="editor_entrada_guardar"):
            try:
                validar_entrada(campo, dato)
                perfil[campo] = [copy.deepcopy(dato) if e["id"] == dato["id"] else e for e in perfil[campo]] if any(e["id"] == dato["id"] for e in perfil[campo]) else [*perfil[campo], copy.deepcopy(dato)]
                st.session_state.entrada_activa = None
                st.rerun()
            except ValueError as error:
                st.error(str(error))
        if cancelar.button("Cancelar entrada", key="editor_entrada_cancelar"):
            st.session_state.entrada_activa = None
            st.rerun()
