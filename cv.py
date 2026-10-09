"""Base CV from saved data, with local preview and download."""

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

from user_profile import migrate_profile
from career_history import ENTRY_FIELDS, format_date, entry_title
from validation import missing_cv_fields, require_cv_information, entry_is_complete


def professional_description(profile):
    """Select aspiration excerpts; never turn them into qualifications."""
    text = profile.get("que_buscas", "").strip()
    conditions = r"salari|sueldo|remot|híbrido|hibrido|presencial|modalidad|ubicaci|jornada|horario|vacacion|contrato|retribuci|\b(?:eur|usd|gbp|chf|euros)\b|[€$£]"
    locations = [u["nombre"].strip() for u in profile.get("ubicaciones", []) if u["nombre"].strip()]
    parts = re.split(r"[\n.;,]+|\s+(?:con\s+(?:un\s+)?(?:salario|sueldo)|en\s+modalidad)\b", text, flags=re.I)
    relevant = []
    for part in parts:
        part = part.strip()
        if not part or re.search(conditions, part, re.I):
            continue
        if any(re.search(r"\b" + re.escape(u) + r"\b", part, re.I) for u in locations):
            continue
        if re.search(r"busc|interés|interes|gustar|desarroll|aprender|especial|contrib|proyect|trabaj|consult|anal|implement|gesti[oó]n|sector|investig|diseñ|ingenier|program|datos|tecnolog", part, re.I):
            relevant.append(part)
    return ". ".join(relevant)


def compose_cv_text(profile):
    profile = migrate_profile(profile)
    lines = []
    data = profile["datos_cv"]
    name = " ".join(data.get(c, "").strip() for c in ("nombre", "apellidos") if data.get(c, "").strip())
    if name:
        lines.append(name)
    for field in ("email", "telefono", "linkedin", "enlaces"):
        if data.get(field, "").strip():
            lines.append(data[field].strip())
    description = professional_description(profile)
    if description:
        lines.extend(["", "DESCRIPCIÓN", "Intereses profesionales: «" + description + "»"])
    for field, title in (("experiencias", "EXPERIENCIA LABORAL"), ("formacion", "FORMACIÓN"), ("proyectos", "PROYECTOS")):
        entries = []
        for entry in profile[field]:
            if not entry_is_complete(field, entry):
                continue
            entry_name = entry_title(field, entry)
            text = [entry_name] if entry_name != "Entrada sin completar" else []
            if field != "proyectos":
                dates = [format_date(entry.get("inicio", {})),
                          "Actualidad" if entry.get("actual") else format_date(entry.get("fin", {}))]
                if any(dates):
                    text.append(" - ".join(f for f in dates if f))
            for key_name in ENTRY_FIELDS[field]:
                if key_name in ("empresa", "puesto", "institucion", "estudios", "nombre"):
                    continue
                if entry.get(key_name, "").strip():
                    text.append(entry[key_name].strip())
            if text:
                entries.append("\n".join(text))
        if entries:
            lines.extend(["", title, "\n\n".join(entries)])
    if profile["skills"]:
        lines.extend(["", "SKILLS DECLARADAS", ", ".join(profile["skills"])])
    if profile["idiomas"]:
        lines.extend(["", "IDIOMAS", "\n".join(i["idioma"] + (" - " + i["nivel"] if i.get("nivel") else "") for i in profile["idiomas"])])
    additional = []
    if profile["experiencia"] != "Sin especificar":
        additional.append("Experiencia general declarada: " + profile["experiencia"])
    legacy = profile.get("datos_anteriores", {}).get("experiencia_profesional", "")
    if legacy and profile["experiencia"] == "Sin especificar":
        additional.append(legacy)
    for key_name, record in profile.get("respuestas_confirmadas", {}).items():
        if key_name == "experiencia_tareas" or key_name == "idiomas" or key_name.startswith(("skill:", "requisito:")):
            if record.get("respuesta", "").strip():
                additional.append(record["respuesta"].strip())
    if additional:
        lines.extend(["", "INFORMACIÓN ADICIONAL DECLARADA", "\n".join(additional)])
    return "\n".join(lines).strip()


def generate_pdf(profile):
    profile = migrate_profile(profile)
    require_cv_information(profile)
    return _render_pdf(compose_cv_text(profile))


def _render_pdf(text):
    if not text.strip():
        raise ValueError("Añade información confirmada antes de generar el CV.")
    if "CVVera" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("CVVera", str(Path(reportlab.__file__).parent / "fonts" / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("CVVeraBold", str(Path(reportlab.__file__).parent / "fonts" / "VeraBd.ttf")))
    normalized = ParagraphStyle("CV", fontName="CVVera", fontSize=10, leading=15,
                            spaceAfter=5, textColor=colors.HexColor("#263445"), splitLongWords=True)
    heading = ParagraphStyle("Seccion", parent=normalized, fontName="CVVeraBold", fontSize=12, leading=17,
                               spaceBefore=12, spaceAfter=8, keepWithNext=True)
    flow = []
    for line in text.splitlines():
        if not line.strip():
            flow.append(Spacer(1, 5))
            continue
        style = heading if line.strip().isupper() and len(line) < 55 else normalized
        flow.append(Paragraph(escape(line), style))
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=48, rightMargin=48,
                                 topMargin=42, bottomMargin=42, title="CV base", author="")
    document.build(flow)
    return buffer.getvalue()


def render_cv(profile, disabled=False):
    missing_fields = missing_cv_fields(profile)
    fingerprint = hashlib.sha256(json.dumps(profile, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if st.session_state.get('cv_huella') != fingerprint:
        st.session_state.pop('cv_pdf', None)
    if missing_fields:
        st.caption("Completa los campos obligatorios para generar tu CV")
        for missing in missing_fields:
            st.caption("• " + missing)
    if st.button("Generar CV base", disabled=disabled or bool(missing_fields)):
        try:
            st.session_state.cv_pdf = generate_pdf(profile)
            st.session_state.cv_huella = fingerprint
        except ValueError as error:
            st.error(str(error))
            return
        st.session_state.pop('cv_borrador', None)
        st.session_state.pop('cv_texto', None)
        st.session_state.cv_preview = True
    if 'cv_pdf' in st.session_state:
        pdf = st.session_state.cv_pdf
        if pdf:
            preview, download = st.columns(2)
            if preview.button("Ver vista previa" if not st.session_state.get('cv_preview') else "Ocultar vista previa", disabled=disabled):
                st.session_state.cv_preview = not st.session_state.get('cv_preview', False)
                st.rerun()
            download.download_button("Descargar CV base en PDF", data=pdf,
                file_name="cv_base.pdf", mime="application/pdf", disabled=disabled)
            if st.session_state.get('cv_preview'):
                content = base64.b64encode(pdf).decode("ascii")
                st.markdown(f'<iframe title="Vista previa del CV" src="data:application/pdf;base64,{content}" '
                    'style="width:100%;height:700px;border:0"></iframe>', unsafe_allow_html=True)
        else:
            st.info("Completa tus datos personales o tu trayectoria para crear el CV.")
