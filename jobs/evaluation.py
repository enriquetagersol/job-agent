"""Define structured offer evaluations and verify profile/description evidence. Calculate internal weighted fit and information coverage, then prioritize cached recommendations in Python."""

from shared.wire_models import WireModel

import json
import re
import unicodedata
from typing import List, Literal, Optional, Union

from pydantic import Field

CRITERIA = {"puesto": "Relevancia del puesto", "capacidades": "Skills",
             "experiencia": "Experiencia", "idiomas": "Idiomas",
             "ubicacion": "Ubicación", "modalidad": "Modalidad", "salario": "Salario"}
BASE_WEIGHTS = {"puesto": 25, "capacidades": 25, "experiencia": 15, "idiomas": 10,
              "ubicacion": 10, "modalidad": 10, "salario": 5}
IMPORTANCE_WEIGHTS = {"Baja": 1, "Media": 2, "Alta": 3}
PROFESSIONAL_CRITERIA = ("puesto", "capacidades", "experiencia", "idiomas")
PREFERENCES = ("ubicacion", "modalidad", "salario")
CriterionPoints = Union[Literal[0, 1, 2], Literal["Sin datos"]]


class Criterion(WireModel):
    name: Literal["puesto", "capacidades", "experiencia", "idiomas", "ubicacion", "modalidad", "salario"]
    points: CriterionPoints
    reason: str
    listing_evidence: str
    profile_evidence: str
    compatible_option: str
    compatibility: Literal["Compatible", "Parcial", "Incompatible", "Sin datos"]
    profile_evidence_quotes: List[str] = Field(default_factory=list)
    listing_evidence_quotes: List[str] = Field(default_factory=list)
    declared_skills: List[str] = Field(default_factory=list)
    original_evaluation_json: str = ""


class SalaryData(WireModel):
    minimum: Optional[float]
    maximum: Optional[float]
    currency: Optional[str]
    period: Literal["Anual", "Mensual", "Por hora", "No documentado"]
    kind: Literal["Bruto", "Neto", "No documentado"]
    evidence: str


class Recommendation(WireModel):
    url: str
    role: str
    company: str
    location: str
    documented_responsibility: str
    documented_requirement: str
    criteria: List[Criterion]
    documented_salary: SalaryData
    gaps: List[str]


class DiscardedListing(WireModel):
    url: str
    reason: str


class EvaluationResult(WireModel):
    job_listings: List[Recommendation] = Field(max_length=20)
    discarded: List[DiscardedListing]


def normalize_weights(profile):
    weights = {n: base * (IMPORTANCE_WEIGHTS[profile.get("importancia_" + n) or "Media"]
             if n in PREFERENCES else 1) for n, base in BASE_WEIGHTS.items()}
    total = sum(weights.values())
    return {n: weight / total for n, weight in weights.items()}


def calculate_fit(criteria, weights, names=None):
    names = tuple(names or CRITERIA)
    evaluated = {c.name: c.points for c in criteria
                 if c.name in names and c.points != "Sin datos"}
    total = sum(weights[n] for n in names)
    known = sum(weights[n] for n in evaluated)
    coverage = round(100 * known / total, 1) if total else 0
    if not known:
        return {"fit": None, "cobertura": coverage}
    average = sum(weights[n] * points / 2 for n, points in evaluated.items()) / known
    return {"fit": round(1 + 9 * average, 1), "cobertura": coverage}


def rank_evaluations(evaluations, weights):
    results = []
    for data in evaluations:
        listing = Recommendation.model_validate(data)
        results.append({"oferta": listing, "total": calculate_fit(listing.criteria, weights),
                           "profesional": calculate_fit(listing.criteria, weights, PROFESSIONAL_CRITERIA),
                           "preferencias": calculate_fit(listing.criteria, weights, PREFERENCES)})
    return sorted(results, key=lambda r: (
        -(r["total"]["fit"] if r["total"]["fit"] is not None else 0),
        -r["total"]["cobertura"], r["oferta"].url))


def mark_unknown(criterion, reason):
    criterion.points = "Sin datos"
    criterion.compatibility = "Sin datos"
    criterion.reason = reason


def quote_is_documented(quote, text):
    """Match continuous words, allowing only formatting and punctuation differences."""
    def words(value):
        return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", value).casefold()))
    fragment = words(quote)
    return bool(fragment) and " " + fragment + " " in " " + words(text) + " "


def text_values(data):
    if isinstance(data, str):
        return [data]
    if isinstance(data, dict):
        return [v for record in data.values() for v in text_values(record)]
    if isinstance(data, list):
        return [v for record in data for v in text_values(record)]
    return []


def atomic_evidence(quotes, legacy_text, origin):
    """Validate each value; presentation prefixes are not profile evidence."""
    suggestions = list(quotes) if quotes else [legacy_text]
    if not quotes:
        suggestions += re.findall(r'«([^»]+)»|"([^"]+)"', legacy_text)
        suggestions = [next((s for s in c if s), "") if isinstance(c, tuple) else c for c in suggestions]
        suggestions += [part.strip() for part in legacy_text.split(";")]
    return list(dict.fromkeys(c for c in suggestions if c not in ("No documentado", "Sin datos")
        and any(quote_is_documented(c, text) for text in origin)))


def validate_criteria(listing, profile, text):
    confirmed, preferences = profile.get("confirmado", {}), profile.get("preferencias", {})
    modes = {"remote": "Remoto", "remoto": "Remoto", "hybrid": "Híbrido", "hibrido": "Híbrido",
                   "on site": "Presencial", "onsite": "Presencial", "presencial": "Presencial"}
    for c in listing.criteria:
        if not c.original_evaluation_json:
            c.original_evaluation_json = json.dumps({"puntos": c.points, "motivo": c.reason,
                "compatibilidad": c.compatibility, "evidencia_perfil": c.profile_evidence,
                "evidencia_oferta": c.listing_evidence}, ensure_ascii=False)
        origin = confirmed if c.name in ("capacidades", "experiencia", "idiomas") else preferences
        if c.name == "puesto":
            origin = {"preferences": preferences, "career": {
                field: confirmed.get(field, []) for field in ("experiencias", "formacion", "proyectos")}}
        if c.name == "capacidades":
            # Course and job titles do not establish specific skills.
            origin = {"skills": confirmed.get("skills", []), "aclaraciones": confirmed.get("aclaraciones", {}),
                "tareas": [{k: e.get(k, "") for k in keys} for field, keys in (
                    ("experiencias", ("responsabilidades", "logros", "herramientas")),
                    ("formacion", ("contenidos", "proyectos")),
                    ("proyectos", ("descripcion", "contribucion", "herramientas"))) for e in confirmed.get(field, [])]}
        source_texts = text_values(origin)
        if c.name == "modalidad":
            source_texts += list(preferences.get("modalidades", {}))
        c.profile_evidence_quotes = atomic_evidence(c.profile_evidence_quotes, c.profile_evidence, source_texts)
        c.listing_evidence_quotes = atomic_evidence(c.listing_evidence_quotes, c.listing_evidence, [text])
        if c.name == "puesto":
            match = next((p for p in preferences.get("puestos_objetivo", [])
                if quote_is_documented(p, listing.role) or quote_is_documented(listing.role, p)), None)
            if match and quote_is_documented(listing.role, text):
                task_grounded = any(quote != listing.role and quote_is_documented(quote, listing.documented_responsibility)
                                    for quote in c.listing_evidence_quotes)
                c.points, c.compatibility = 2, "Compatible"
                preserve_reason = task_grounded and bool(c.profile_evidence_quotes) and bool(c.reason.strip())
                c.profile_evidence_quotes = list(dict.fromkeys([match, *c.profile_evidence_quotes]))
                c.listing_evidence_quotes = list(dict.fromkeys([listing.role, *c.listing_evidence_quotes]))
                if not preserve_reason:
                    c.reason = f"Buscas puestos de {match}; el título de esta oferta coincide. Falta concretar cómo sus funciones conectan con lo que quieres hacer."
                continue
        if c.name == "salario":
            score_salary(c, listing.documented_salary, preferences, text)
            continue
        if c.name == "capacidades":
            requirement = "\n".join(c.listing_evidence_quotes + [listing.documented_requirement])
            aliases = {"llm": ("LLM", "LLMs", "large language models"),
                       "ia": ("IA", "AI", "artificial intelligence", "inteligencia artificial")}
            c.declared_skills = [skill for skill in confirmed.get("skills", []) if any(
                quote_is_documented(alias, requirement) for alias in aliases.get(skill.casefold(), (skill,)))]
            clarifications = confirmed.get("aclaraciones", {})
            additional_evidence = any(len(quote.split()) >= 5 and quote_is_documented(quote, response.get("respuesta", ""))
                for response in clarifications.values() for quote in c.profile_evidence_quotes)
            practical_fields = [("experiencias", ("responsabilidades", "logros", "herramientas")),
                               ("proyectos", ("descripcion", "contribucion", "herramientas"))]
            practical_evidence = any(len(quote.split()) >= 5 and quote_is_documented(quote, e.get(k, ""))
                for field, keys in practical_fields for e in confirmed.get(field, [])
                for k in keys for quote in c.profile_evidence_quotes)
            education_evidence = any(quote_is_documented(quote, e.get(k, ""))
                for e in confirmed.get("formacion", []) for k in ("contenidos", "proyectos") for quote in c.profile_evidence_quotes)
            additional_evidence = additional_evidence or practical_evidence or education_evidence
            if c.declared_skills and not additional_evidence:
                c.points, c.compatibility = 1, "Parcial"
                c.profile_evidence_quotes = list(dict.fromkeys(c.profile_evidence_quotes + c.declared_skills))
                c.reason = "La oferta pide conocimientos relacionados con " + ", ".join(c.declared_skills) + ". Los declaras en tu perfil; falta confirmar cómo los has aplicado y con qué autonomía."
                continue
            if additional_evidence:
                c.declared_skills = []
                if education_evidence and not practical_evidence and c.points == 2:
                    c.points, c.compatibility = 1, "Parcial"
                    c.reason = "Los contenidos registrados en tu formación coinciden con conocimientos que pide la oferta. Esto acredita aprendizaje declarado, no dominio avanzado ni experiencia laboral."
        experience_details = confirmed.get("experiencia_detalle_confirmado") or any(
            len(quote.split()) >= 5 and quote_is_documented(quote, r.get("respuesta", ""))
            for r in confirmed.get("aclaraciones", {}).values() for quote in c.profile_evidence_quotes)
        experience_details = experience_details or any(len(quote.split()) >= 5 and quote_is_documented(quote, e.get(k, ""))
            for e in confirmed.get("experiencias", []) for k in ("responsabilidades", "logros") for quote in c.profile_evidence_quotes)
        if c.name == "experiencia" and confirmed.get("experiencia", "Sin especificar") == "Sin especificar" and not experience_details:
            mark_unknown(c, "¿Qué experiencia tienes en las tareas que pide este puesto?")
            continue
        if c.name == "experiencia" and not experience_details and not re.search(r"\d+\s*(?:\+\s*)?(?:years|años)", " ".join(c.listing_evidence_quotes), re.I):
            mark_unknown(c, f"Has indicado {confirmed.get('experiencia', 'experiencia general')}. ¿Qué tareas o proyectos has realizado que acrediten lo que pide {listing.role}?")
            continue
        if not c.profile_evidence_quotes or not c.listing_evidence_quotes:
            mark_unknown(c, "Falta información para confirmar este requisito o preferencia.")
            continue
        if c.name == "modalidad":
            from profiles.user_profile import normalize_identity
            c.compatible_option = modes.get(normalize_identity(c.compatible_option), c.compatible_option)
        if c.name in ("ubicacion", "modalidad"):
            options = ({u['nombre']: u['preferencia'] for u in preferences.get('ubicaciones', [])}
                        if c.name == "ubicacion" else preferences.get("modalidades", {}))
            if c.compatibility == "Incompatible":
                c.points = 0
            elif c.compatible_option not in options or options[c.compatible_option] not in IMPORTANCE_WEIGHTS:
                mark_unknown(c, "Falta concretar esta preferencia para compararla con la oferta.")
            else:
                points = IMPORTANCE_WEIGHTS[options[c.compatible_option]] - 1
                c.points = min(points, 1) if c.compatibility == "Parcial" else points
                c.reason = (f"La oferta está en {c.compatible_option}, uno de los lugares donde quieres trabajar."
                            if c.name == "ubicacion" else f"La oferta ofrece modalidad {c.compatible_option.lower()}, que has seleccionado en tu perfil.")
    return listing


def number_is_documented(number, text):
    """Recognize explicit amounts without converting periods or currencies."""
    for candidate in re.findall(r"\d[\d., ]*\s*[kK]?", text):
        compact = candidate.strip().replace(" ", "")
        factor = 1000 if compact.lower().endswith("k") else 1
        compact = compact.rstrip("kK").rstrip(".,")
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", compact):
            compact = compact.replace(",", "").replace(".", "")
        else:
            compact = compact.replace(",", ".")
        try:
            if float(compact) * factor == number:
                return True
        except ValueError:
            pass
    return False


def score_salary(criterion, salary, preferences, text):
    target = preferences.get("salario_minimo")
    quote = salary.evidence
    annual = bool(re.search(r"anual|annual|per annum|per year|/year|/yr|por año", quote, re.I))
    gross = bool(re.search(r"brut[oa]|gross|before tax", quote, re.I))
    if target is None:
        mark_unknown(criterion, "Salario mínimo del perfil no especificado.")
        return
    if not quote.strip() or quote not in text or salary.period != "Anual" or salary.kind != "Bruto" or not annual or not gross:
        mark_unknown(criterion, "Salario no comparable: no hay evidencia explícita de importe bruto anual. No se anualiza.")
        return
    if not salary.currency or salary.currency.upper() != preferences["moneda"]:
        mark_unknown(criterion, "Salario no comparable: moneda distinta o no documentada; no se aplica conversión.")
        return
    currencies = {"EUR": ("EUR", "€", "euro"), "GBP": ("GBP", "£", "pound", "libra"),
               "USD": ("USD", "US$", "US dollar")}
    tokens = currencies.get(salary.currency.upper(), (salary.currency.upper(),))
    if not any(token.casefold() in quote.casefold() for token in tokens):
        mark_unknown(criterion, "Moneda sin evidencia suficiente en la descripción.")
        return
    minimum, maximum = salary.minimum, salary.maximum
    if (minimum is None or maximum is None or minimum < 0 or maximum < minimum or
        not number_is_documented(minimum, quote) or not number_is_documented(maximum, quote)):
        mark_unknown(criterion, "Rango salarial no documentado o sin evidencia verificable.")
        return
    criterion.listing_evidence = quote
    criterion.profile_evidence = f"{target} {preferences['moneda']} bruto anual"
    if minimum >= target:
        criterion.points, criterion.compatibility = 2, "Compatible"
        criterion.reason = "Todo el rango bruto anual alcanza el mínimo solicitado."
    elif maximum >= target:
        criterion.points, criterion.compatibility = 1, "Parcial"
        criterion.reason = "Solo una parte del rango bruto anual alcanza el mínimo solicitado."
    else:
        criterion.points, criterion.compatibility = 0, "Incompatible"
        criterion.reason = "El máximo documentado es inferior al mínimo solicitado; no excluye la oferta."


def validate_recommendations(result, retrieved, profile, notify=None):
    valid, seen = [], set()
    confirmed = profile.get("confirmado", {})
    preferences = profile.get("preferencias", {})
    def discard(url, reason):
        if notify:
            notify("descartada", reason, url)
    for original in result.job_listings:
        listing = original.model_copy(deep=True)
        source = retrieved.get(listing.url)
        if not source:
            discard(listing.url, "Enlace sin descripción recuperada")
            continue
        text = source["descripcion_recuperada"]
        if any(not quote_is_documented(quote, text) for quote in
               (listing.documented_responsibility, listing.documented_requirement)):
            discard(listing.url, "Responsabilidades o requisitos sin evidencia verificable")
            continue
        if any(v != "No documentado" and not quote_is_documented(v, text)
               for v in (listing.role, listing.company, listing.location)):
            discard(listing.url, "Identificación sin respaldo en la descripción")
            continue
        if len(listing.criteria) != len(CRITERIA) or {c.name for c in listing.criteria} != set(CRITERIA):
            discard(listing.url, "Evaluación incompleta de dimensiones")
            continue
        # Python creates the audit record, not the model.
        for criterion in listing.criteria:
            criterion.original_evaluation_json = ""
        validate_criteria(listing, profile, text)
        normalize_identity = tuple(" ".join(v.lower().split()) for v in (listing.company, listing.role, listing.location))
        if "No documentado" in (listing.company, listing.role):
            normalize_identity = (listing.url,)
        if normalize_identity in seen:
            discard(listing.url, "Oferta duplicada")
            continue
        seen.add(normalize_identity)
        valid.append(listing)
    return valid
