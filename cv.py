"""CV base de datos guardados, con vista previa y descarga locales."""

from io import BytesIO
import base64
import hashlib
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
import streamlit as st

from perfil import migrar_perfil
from trayectoria import CAMPOS, texto_fecha, titulo_entrada
from validaciones import faltantes_cv, exigir_cv, entrada_completa


def descripcion_profesional(perfil):
    """Selecciona fragmentos de aspiraciones; nunca los convierte en cualificación."""
    texto = perfil.get("que_buscas", "").strip()
    condiciones = r"salari|sueldo|remot|híbrido|hibrido|presencial|modalidad|ubicaci|jornada|horario|vacacion|contrato|retribuci|\b(?:eur|usd|gbp|chf|euros)\b|[€$£]"
    ubicaciones = [u["nombre"].strip() for u in perfil.get("ubicaciones", []) if u["nombre"].strip()]
    partes = re.split(r"[\n.;,]+|\s+(?:con\s+(?:un\s+)?(?:salario|sueldo)|en\s+modalidad)\b", texto, flags=re.I)
    relevantes = []
    for parte in partes:
        parte = parte.strip()
        if not parte or re.search(condiciones, parte, re.I):
            continue
        if any(re.search(r"\b" + re.escape(u) + r"\b", parte, re.I) for u in ubicaciones):
            continue
        if re.search(r"busc|interés|interes|gustar|desarroll|aprender|especial|contrib|proyect|trabaj|consult|anal|implement|gesti[oó]n|sector|investig|diseñ|ingenier|program|datos|tecnolog", parte, re.I):
            relevantes.append(parte)
    return ". ".join(relevantes)


def borrador_cv(perfil):
    perfil = migrar_perfil(perfil)
    lineas = []
    datos = perfil["datos_cv"]
    nombre = " ".join(datos.get(c, "").strip() for c in ("nombre", "apellidos") if datos.get(c, "").strip())
    if nombre:
        lineas.append(nombre)
    for campo in ("email", "telefono", "linkedin", "enlaces"):
        if datos.get(campo, "").strip():
            lineas.append(datos[campo].strip())
    descripcion = descripcion_profesional(perfil)
    if descripcion:
        lineas.extend(["", "DESCRIPCIÓN", "Intereses profesionales: «" + descripcion + "»"])
    for campo, titulo in (("experiencias", "EXPERIENCIA LABORAL"), ("formacion", "FORMACIÓN"), ("proyectos", "PROYECTOS")):
        entradas = []
        for entrada in perfil[campo]:
            if not entrada_completa(campo, entrada):
                continue
            nombre_entrada = titulo_entrada(campo, entrada)
            texto = [nombre_entrada] if nombre_entrada != "Entrada sin completar" else []
            if campo != "proyectos":
                fechas = [texto_fecha(entrada.get("inicio", {})),
                          "Actualidad" if entrada.get("actual") else texto_fecha(entrada.get("fin", {}))]
                if any(fechas):
                    texto.append(" - ".join(f for f in fechas if f))
            for clave in CAMPOS[campo]:
                if clave in ("empresa", "puesto", "institucion", "estudios", "nombre"):
                    continue
                if entrada.get(clave, "").strip():
                    texto.append(entrada[clave].strip())
            if texto:
                entradas.append("\n".join(texto))
        if entradas:
            lineas.extend(["", titulo, "\n\n".join(entradas)])
    if perfil["skills"]:
        lineas.extend(["", "SKILLS DECLARADAS", ", ".join(perfil["skills"])])
    if perfil["idiomas"]:
        lineas.extend(["", "IDIOMAS", "\n".join(i["idioma"] + (" - " + i["nivel"] if i.get("nivel") else "") for i in perfil["idiomas"])])
    adicionales = []
    if perfil["experiencia"] != "Sin especificar":
        adicionales.append("Experiencia general declarada: " + perfil["experiencia"])
    antiguo = perfil.get("datos_anteriores", {}).get("experiencia_profesional", "")
    if antiguo and perfil["experiencia"] == "Sin especificar":
        adicionales.append(antiguo)
    for clave, dato in perfil.get("respuestas_confirmadas", {}).items():
        if clave == "experiencia_tareas" or clave == "idiomas" or clave.startswith(("skill:", "requisito:")):
            if dato.get("respuesta", "").strip():
                adicionales.append(dato["respuesta"].strip())
    if adicionales:
        lineas.extend(["", "INFORMACIÓN ADICIONAL DECLARADA", "\n".join(adicionales)])
    return "\n".join(lineas).strip()


def generar_pdf(perfil):
    perfil = migrar_perfil(perfil)
    exigir_cv(perfil)
    return _renderizar_pdf(borrador_cv(perfil))


def _renderizar_pdf(texto):
    if not texto.strip():
        raise ValueError("Añade información confirmada antes de generar el CV.")
    if "CVVera" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("CVVera", str(Path(reportlab.__file__).parent / "fonts" / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("CVVeraBold", str(Path(reportlab.__file__).parent / "fonts" / "VeraBd.ttf")))
    normal = ParagraphStyle("CV", fontName="CVVera", fontSize=10, leading=15,
                            spaceAfter=5, textColor=colors.HexColor("#263445"), splitLongWords=True)
    encabezado = ParagraphStyle("Seccion", parent=normal, fontName="CVVeraBold", fontSize=12, leading=17,
                               spaceBefore=12, spaceAfter=8, keepWithNext=True)
    flujo = []
    for linea in texto.splitlines():
        if not linea.strip():
            flujo.append(Spacer(1, 5))
            continue
        estilo = encabezado if linea.strip().isupper() and len(linea) < 55 else normal
        flujo.append(Paragraph(escape(linea), estilo))
    buffer = BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=48, rightMargin=48,
                                 topMargin=42, bottomMargin=42, title="CV base", author="")
    documento.build(flujo)
    return buffer.getvalue()


def mostrar_cv(perfil, disabled=False):
    faltan = faltantes_cv(perfil)
    huella = hashlib.sha256(json.dumps(perfil, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if st.session_state.get("cv_huella") != huella:
        st.session_state.pop("cv_pdf", None)
    if faltan:
        st.caption("Completa los campos obligatorios para generar tu CV")
        for falta in faltan:
            st.caption("• " + falta)
    if st.button("Generar CV base", disabled=disabled or bool(faltan)):
        try:
            st.session_state.cv_pdf = generar_pdf(perfil)
            st.session_state.cv_huella = huella
        except ValueError as error:
            st.error(str(error))
            return
        st.session_state.pop("cv_borrador", None)
        st.session_state.pop("cv_texto", None)
        st.session_state.cv_preview = True
    if "cv_pdf" in st.session_state:
        pdf = st.session_state.cv_pdf
        if pdf:
            previa, descarga = st.columns(2)
            if previa.button("Ver vista previa" if not st.session_state.get("cv_preview") else "Ocultar vista previa", disabled=disabled):
                st.session_state.cv_preview = not st.session_state.get("cv_preview", False)
                st.rerun()
            descarga.download_button("Descargar CV base en PDF", data=pdf,
                file_name="cv_base.pdf", mime="application/pdf", disabled=disabled)
            if st.session_state.get("cv_preview"):
                contenido = base64.b64encode(pdf).decode("ascii")
                st.markdown(f'<iframe title="Vista previa del CV" src="data:application/pdf;base64,{contenido}" '
                    'style="width:100%;height:700px;border:0"></iframe>', unsafe_allow_html=True)
        else:
            st.info("Completa tus datos personales o tu trayectoria para crear el CV.")
