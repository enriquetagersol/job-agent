"""Reglas compartidas para formularios y acciones, sin llamadas externas."""

import re


def texto_util(valor):
    return (isinstance(valor, str) and valor.strip().casefold() not in (
        "sin especificar", "no especificado", "no especificada", "no documentado", "sin datos")
        and bool(re.search(r"\w", valor.strip())))


def faltantes_entrada(campo, entrada):
    requeridos = {"experiencias": (("empresa", "Empresa"), ("puesto", "Puesto"), ("responsabilidades", "Descripción de responsabilidades")),
                  "formacion": (("institucion", "Institución"), ("estudios", "Estudios/titulación")),
                  "proyectos": (("nombre", "Nombre del proyecto"), ("descripcion", "Descripción del proyecto"), ("contribucion", "Contribución personal"))}
    faltan = [etiqueta for clave, etiqueta in requeridos[campo] if not texto_util(entrada.get(clave))]
    if campo != "proyectos":
        for clave, etiqueta in (("inicio", "Fecha de inicio"), ("fin", "Fecha de fin")):
            if clave == "fin" and entrada.get("actual") is True:
                continue
            fecha = entrada.get(clave) or {}
            if not isinstance(fecha, dict):
                fecha = {}
            if type(fecha.get("mes")) is not int or not 1 <= fecha["mes"] <= 12:
                faltan.append(etiqueta + " · mes")
            if type(fecha.get("ano")) is not int or not 1 <= fecha["ano"] <= 9999:
                faltan.append(etiqueta + " · año")
    return faltan


def entrada_completa(campo, entrada):
    if faltantes_entrada(campo, entrada):
        return False
    if campo != "proyectos" and not entrada.get("actual"):
        inicio, fin = entrada["inicio"], entrada["fin"]
        return (fin["ano"], fin["mes"]) >= (inicio["ano"], inicio["mes"])
    return True


def informacion_busqueda(perfil):
    if "confirmado" in perfil:
        confirmado, preferencias = perfil["confirmado"], perfil.get("preferencias", {})
    else:
        confirmado = preferencias = perfil
    for campo, claves in (("experiencias", ("empresa", "puesto", "responsabilidades", "logros", "herramientas")),
                         ("formacion", ("institucion", "estudios", "contenidos", "proyectos")),
                         ("proyectos", ("nombre", "descripcion", "contribucion", "herramientas"))):
        if any(texto_util(e.get(k)) for e in confirmado.get(campo, []) for k in claves):
            return True
    if any(texto_util(s) for s in confirmado.get("skills", [])) or any(texto_util(i.get("idioma")) for i in confirmado.get("idiomas", [])):
        return True
    if confirmado.get("experiencia") in ("Sin experiencia", "<1 año", "1–3 años", "4–6 años", ">6 años"):
        return True
    if texto_util(confirmado.get("experiencia_detalle_confirmado")):
        return True
    if any(texto_util(r.get("respuesta")) for r in confirmado.get("aclaraciones", confirmado.get("respuestas_confirmadas", {})).values()):
        return True
    return (any(texto_util(p) for p in preferencias.get("puestos_objetivo", [])) or
            any(texto_util(u.get("nombre")) for u in preferencias.get("ubicaciones", [])) or
            any(m in ("Presencial", "Híbrido", "Remoto") and p in (None, "Baja", "Media", "Alta")
                for m, p in preferencias.get("modalidades", {}).items()) or
            (type(preferencias.get("salario_minimo")) in (int, float) and preferencias["salario_minimo"] > 0) or
            texto_util(preferencias.get("que_buscas")))


def exigir_busqueda(perfil):
    if not informacion_busqueda(perfil):
        raise ValueError("No hay suficiente información para buscar. Añade información sobre tu trayectoria o lo que buscas")


def faltantes_cv(perfil):
    datos = perfil.get("datos_cv", {})
    faltan = []
    if not texto_util(datos.get("nombre")):
        faltan.append("Nombre")
    if not texto_util(datos.get("apellidos")):
        faltan.append("Apellidos")
    email = datos.get("email", "")
    if not isinstance(email, str) or not re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", email.strip()):
        faltan.append("Email con formato válido")
    if not any(entrada_completa(campo, e) for campo in ("experiencias", "formacion", "proyectos") for e in perfil.get(campo, [])):
        faltan.append("Al menos una experiencia, formación o proyecto completo")
        for campo, etiqueta in (("experiencias", "Experiencia"), ("formacion", "Formación"), ("proyectos", "Proyecto")):
            for i, entrada in enumerate(perfil.get(campo, []), 1):
                faltan.extend(f"{etiqueta} {i}: {f}" for f in faltantes_entrada(campo, entrada))
                if not faltantes_entrada(campo, entrada) and not entrada_completa(campo, entrada):
                    faltan.append(f"{etiqueta} {i}: fecha de fin anterior al inicio")
    return faltan


def exigir_cv(perfil):
    faltan = faltantes_cv(perfil)
    if faltan:
        raise ValueError("Completa los campos obligatorios para generar tu CV: " + "; ".join(faltan))
