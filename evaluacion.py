"""El modelo aporta evidencia; Python aplica la fórmula aprobada."""

import json
import re
import unicodedata
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

CRITERIOS = {"puesto": "Relevancia del puesto", "capacidades": "Skills",
             "experiencia": "Experiencia", "idiomas": "Idiomas",
             "ubicacion": "Ubicación", "modalidad": "Modalidad", "salario": "Salario"}
PESOS_BASE = {"puesto": 25, "capacidades": 25, "experiencia": 15, "idiomas": 10,
              "ubicacion": 10, "modalidad": 10, "salario": 5}
IMPORTANCIAS = {"Baja": 1, "Media": 2, "Alta": 3}
PROFESIONALES = ("puesto", "capacidades", "experiencia", "idiomas")
PREFERENCIAS = ("ubicacion", "modalidad", "salario")
Puntos = Union[Literal[0, 1, 2], Literal["Sin datos"]]


class Criterio(BaseModel):
    nombre: Literal["puesto", "capacidades", "experiencia", "idiomas", "ubicacion", "modalidad", "salario"]
    puntos: Puntos
    motivo: str
    evidencia_oferta: str
    evidencia_perfil: str
    opcion_compatible: str
    compatibilidad: Literal["Compatible", "Parcial", "Incompatible", "Sin datos"]
    evidencias_perfil: List[str] = Field(default_factory=list)
    evidencias_oferta: List[str] = Field(default_factory=list)
    skills_declaradas: List[str] = Field(default_factory=list)
    evaluacion_original_json: str = ""


class DatosSalario(BaseModel):
    minimo: Optional[float]
    maximo: Optional[float]
    moneda: Optional[str]
    periodo: Literal["Anual", "Mensual", "Por hora", "No documentado"]
    tipo: Literal["Bruto", "Neto", "No documentado"]
    evidencia: str


class Recomendacion(BaseModel):
    enlace: str
    puesto: str
    empresa: str
    ubicacion: str
    responsabilidad_documentada: str
    requisito_documentado: str
    criterios: List[Criterio]
    salario_documentado: DatosSalario
    gaps: List[str]


class Descarte(BaseModel):
    enlace: str
    motivo: str


class Resultado(BaseModel):
    ofertas: List[Recomendacion] = Field(max_length=20)
    descartadas: List[Descarte]


def normalizar_pesos(perfil):
    pesos = {n: base * (IMPORTANCIAS[perfil.get("importancia_" + n) or "Media"]
             if n in PREFERENCIAS else 1) for n, base in PESOS_BASE.items()}
    total = sum(pesos.values())
    return {n: peso / total for n, peso in pesos.items()}


def calcular_fit(criterios, pesos, nombres=None):
    nombres = tuple(nombres or CRITERIOS)
    evaluados = {c.nombre: c.puntos for c in criterios
                 if c.nombre in nombres and c.puntos != "Sin datos"}
    total = sum(pesos[n] for n in nombres)
    conocido = sum(pesos[n] for n in evaluados)
    cobertura = round(100 * conocido / total, 1) if total else 0
    if not conocido:
        return {"fit": None, "cobertura": cobertura}
    media = sum(pesos[n] * puntos / 2 for n, puntos in evaluados.items()) / conocido
    return {"fit": round(1 + 9 * media, 1), "cobertura": cobertura}


def ordenar_evaluaciones(evaluaciones, pesos):
    resultados = []
    for datos in evaluaciones:
        oferta = Recomendacion.model_validate(datos)
        resultados.append({"oferta": oferta, "total": calcular_fit(oferta.criterios, pesos),
                           "profesional": calcular_fit(oferta.criterios, pesos, PROFESIONALES),
                           "preferencias": calcular_fit(oferta.criterios, pesos, PREFERENCIAS)})
    return sorted(resultados, key=lambda r: (
        -(r["total"]["fit"] if r["total"]["fit"] is not None else 0),
        -r["total"]["cobertura"], r["oferta"].enlace))


def sin_datos(criterio, motivo):
    criterio.puntos = "Sin datos"
    criterio.compatibilidad = "Sin datos"
    criterio.motivo = motivo


def cita_documentada(cita, texto):
    """Mismas palabras continuas, tolerando solo formato y puntuación."""
    def palabras(valor):
        return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", valor).casefold()))
    fragmento = palabras(cita)
    return bool(fragmento) and " " + fragmento + " " in " " + palabras(texto) + " "


def valores_texto(datos):
    if isinstance(datos, str):
        return [datos]
    if isinstance(datos, dict):
        return [v for dato in datos.values() for v in valores_texto(dato)]
    if isinstance(datos, list):
        return [v for dato in datos for v in valores_texto(dato)]
    return []


def evidencias_atomicas(citas, legado, origen):
    """Valida cada valor; prefijos de presentación no son evidencia del perfil."""
    propuestas = list(citas) if citas else [legado]
    if not citas:
        propuestas += re.findall(r'«([^»]+)»|"([^"]+)"', legado)
        propuestas = [next((s for s in c if s), "") if isinstance(c, tuple) else c for c in propuestas]
        propuestas += [parte.strip() for parte in legado.split(";")]
    return list(dict.fromkeys(c for c in propuestas if c not in ("No documentado", "Sin datos")
        and any(cita_documentada(c, texto) for texto in origen)))


def validar_criterios(oferta, perfil, texto):
    confirmado, preferencias = perfil.get("confirmado", {}), perfil.get("preferencias", {})
    modalidades = {"remote": "Remoto", "remoto": "Remoto", "hybrid": "Híbrido", "hibrido": "Híbrido",
                   "on site": "Presencial", "onsite": "Presencial", "presencial": "Presencial"}
    for c in oferta.criterios:
        if not c.evaluacion_original_json:
            c.evaluacion_original_json = json.dumps({"puntos": c.puntos, "motivo": c.motivo,
                "compatibilidad": c.compatibilidad, "evidencia_perfil": c.evidencia_perfil,
                "evidencia_oferta": c.evidencia_oferta}, ensure_ascii=False)
        origen = confirmado if c.nombre in ("capacidades", "experiencia", "idiomas") else preferencias
        if c.nombre == "capacidades":
            # Los títulos de cursos/empleos no acreditan skills específicas.
            origen = {"skills": confirmado.get("skills", []), "aclaraciones": confirmado.get("aclaraciones", {}),
                "tareas": [{k: e.get(k, "") for k in claves} for campo, claves in (
                    ("experiencias", ("responsabilidades", "logros", "herramientas")),
                    ("formacion", ("contenidos", "proyectos")),
                    ("proyectos", ("descripcion", "contribucion", "herramientas"))) for e in confirmado.get(campo, [])]}
        textos_origen = valores_texto(origen)
        if c.nombre == "modalidad":
            textos_origen += list(preferencias.get("modalidades", {}))
        c.evidencias_perfil = evidencias_atomicas(c.evidencias_perfil, c.evidencia_perfil, textos_origen)
        c.evidencias_oferta = evidencias_atomicas(c.evidencias_oferta, c.evidencia_oferta, [texto])
        if c.nombre == "puesto":
            coincidencia = next((p for p in preferencias.get("puestos_objetivo", [])
                if cita_documentada(p, oferta.puesto) or cita_documentada(oferta.puesto, p)), None)
            if coincidencia and cita_documentada(oferta.puesto, texto):
                c.puntos, c.compatibilidad = 2, "Compatible"
                c.evidencias_perfil = [coincidencia]
                c.evidencias_oferta = [oferta.puesto]
                c.motivo = f"El puesto de {oferta.puesto} coincide con tu objetivo de {coincidencia}. Esta coincidencia expresa interés; los requisitos se valoran por separado."
                continue
        if c.nombre == "salario":
            puntuar_salario(c, oferta.salario_documentado, preferencias, texto)
            continue
        if c.nombre == "capacidades":
            requisito = "\n".join(c.evidencias_oferta + [oferta.requisito_documentado])
            aliases = {"llm": ("LLM", "LLMs", "large language models"),
                       "ia": ("IA", "AI", "artificial intelligence", "inteligencia artificial")}
            c.skills_declaradas = [skill for skill in confirmado.get("skills", []) if any(
                cita_documentada(alias, requisito) for alias in aliases.get(skill.casefold(), (skill,)))]
            aclaraciones = confirmado.get("aclaraciones", {})
            evidencia_adicional = any(len(cita.split()) >= 5 and cita_documentada(cita, respuesta.get("respuesta", ""))
                for respuesta in aclaraciones.values() for cita in c.evidencias_perfil)
            campos_practicos = [("experiencias", ("responsabilidades", "logros", "herramientas")),
                               ("proyectos", ("descripcion", "contribucion", "herramientas"))]
            evidencia_practica = any(len(cita.split()) >= 5 and cita_documentada(cita, e.get(k, ""))
                for campo, claves in campos_practicos for e in confirmado.get(campo, [])
                for k in claves for cita in c.evidencias_perfil)
            evidencia_formacion = any(cita_documentada(cita, e.get(k, ""))
                for e in confirmado.get("formacion", []) for k in ("contenidos", "proyectos") for cita in c.evidencias_perfil)
            evidencia_adicional = evidencia_adicional or evidencia_practica or evidencia_formacion
            if c.skills_declaradas and not evidencia_adicional:
                c.puntos, c.compatibilidad = 1, "Parcial"
                c.evidencias_perfil = list(dict.fromkeys(c.evidencias_perfil + c.skills_declaradas))
                c.motivo = "La oferta pide conocimientos relacionados con " + ", ".join(c.skills_declaradas) + ". Los declaras en tu perfil; falta confirmar cómo los has aplicado y con qué autonomía."
                continue
            if evidencia_adicional:
                c.skills_declaradas = []
                if evidencia_formacion and not evidencia_practica and c.puntos == 2:
                    c.puntos, c.compatibilidad = 1, "Parcial"
                    c.motivo = "Los contenidos registrados en tu formación coinciden con conocimientos que pide la oferta. Esto acredita aprendizaje declarado, no dominio avanzado ni experiencia laboral."
        detalle_experiencia = confirmado.get("experiencia_detalle_confirmado") or any(
            len(cita.split()) >= 5 and cita_documentada(cita, r.get("respuesta", ""))
            for r in confirmado.get("aclaraciones", {}).values() for cita in c.evidencias_perfil)
        detalle_experiencia = detalle_experiencia or any(len(cita.split()) >= 5 and cita_documentada(cita, e.get(k, ""))
            for e in confirmado.get("experiencias", []) for k in ("responsabilidades", "logros") for cita in c.evidencias_perfil)
        if c.nombre == "experiencia" and confirmado.get("experiencia", "Sin especificar") == "Sin especificar" and not detalle_experiencia:
            sin_datos(c, "¿Qué experiencia tienes en las tareas que pide este puesto?")
            continue
        if c.nombre == "experiencia" and not detalle_experiencia and not re.search(r"\d+\s*(?:\+\s*)?(?:years|años)", " ".join(c.evidencias_oferta), re.I):
            sin_datos(c, f"Has indicado {confirmado.get('experiencia', 'experiencia general')}. ¿Qué tareas o proyectos has realizado que acrediten lo que pide {oferta.puesto}?")
            continue
        if not c.evidencias_perfil or not c.evidencias_oferta:
            sin_datos(c, "Falta información para confirmar este requisito o preferencia.")
            continue
        if c.nombre == "modalidad":
            from perfil import identidad
            c.opcion_compatible = modalidades.get(identidad(c.opcion_compatible), c.opcion_compatible)
        if c.nombre in ("ubicacion", "modalidad"):
            opciones = ({u['nombre']: u['preferencia'] for u in preferencias.get('ubicaciones', [])}
                        if c.nombre == "ubicacion" else preferencias.get("modalidades", {}))
            if c.compatibilidad == "Incompatible":
                c.puntos = 0
            elif c.opcion_compatible not in opciones or opciones[c.opcion_compatible] not in IMPORTANCIAS:
                sin_datos(c, "Falta concretar esta preferencia para compararla con la oferta.")
            else:
                puntos = IMPORTANCIAS[opciones[c.opcion_compatible]] - 1
                c.puntos = min(puntos, 1) if c.compatibilidad == "Parcial" else puntos
                c.motivo = (f"La oferta está en {c.opcion_compatible}, uno de los lugares donde quieres trabajar."
                            if c.nombre == "ubicacion" else f"La oferta ofrece modalidad {c.opcion_compatible.lower()}, que has seleccionado en tu perfil.")
    return oferta


def numero_documentado(numero, texto):
    """Reconoce cantidades explícitas, sin convertir periodos ni monedas."""
    for candidato in re.findall(r"\d[\d., ]*\s*[kK]?", texto):
        compacto = candidato.strip().replace(" ", "")
        factor = 1000 if compacto.lower().endswith("k") else 1
        compacto = compacto.rstrip("kK").rstrip(".,")
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", compacto):
            compacto = compacto.replace(",", "").replace(".", "")
        else:
            compacto = compacto.replace(",", ".")
        try:
            if float(compacto) * factor == numero:
                return True
        except ValueError:
            pass
    return False


def puntuar_salario(criterio, salario, preferencias, texto):
    objetivo = preferencias.get("salario_minimo")
    cita = salario.evidencia
    anual = bool(re.search(r"anual|annual|per annum|per year|/year|/yr|por año", cita, re.I))
    bruto = bool(re.search(r"brut[oa]|gross|before tax", cita, re.I))
    if objetivo is None:
        sin_datos(criterio, "Salario mínimo del perfil no especificado.")
        return
    if not cita.strip() or cita not in texto or salario.periodo != "Anual" or salario.tipo != "Bruto" or not anual or not bruto:
        sin_datos(criterio, "Salario no comparable: no hay evidencia explícita de importe bruto anual. No se anualiza.")
        return
    if not salario.moneda or salario.moneda.upper() != preferencias["moneda"]:
        sin_datos(criterio, "Salario no comparable: moneda distinta o no documentada; no se aplica conversión.")
        return
    monedas = {"EUR": ("EUR", "€", "euro"), "GBP": ("GBP", "£", "pound", "libra"),
               "USD": ("USD", "US$", "US dollar")}
    tokens = monedas.get(salario.moneda.upper(), (salario.moneda.upper(),))
    if not any(token.casefold() in cita.casefold() for token in tokens):
        sin_datos(criterio, "Moneda sin evidencia suficiente en la descripción.")
        return
    minimo, maximo = salario.minimo, salario.maximo
    if (minimo is None or maximo is None or minimo < 0 or maximo < minimo or
        not numero_documentado(minimo, cita) or not numero_documentado(maximo, cita)):
        sin_datos(criterio, "Rango salarial no documentado o sin evidencia verificable.")
        return
    criterio.evidencia_oferta = cita
    criterio.evidencia_perfil = f"{objetivo} {preferencias['moneda']} bruto anual"
    if minimo >= objetivo:
        criterio.puntos, criterio.compatibilidad = 2, "Compatible"
        criterio.motivo = "Todo el rango bruto anual alcanza el mínimo solicitado."
    elif maximo >= objetivo:
        criterio.puntos, criterio.compatibilidad = 1, "Parcial"
        criterio.motivo = "Solo una parte del rango bruto anual alcanza el mínimo solicitado."
    else:
        criterio.puntos, criterio.compatibilidad = 0, "Incompatible"
        criterio.motivo = "El máximo documentado es inferior al mínimo solicitado; no excluye la oferta."


def validar_recomendaciones(resultado, recuperadas, perfil, avisar=None):
    validas, vistas = [], set()
    confirmado = perfil.get("confirmado", {})
    preferencias = perfil.get("preferencias", {})
    def descartar(enlace, motivo):
        if avisar:
            avisar("descartada", motivo, enlace)
    for original in resultado.ofertas:
        oferta = original.model_copy(deep=True)
        fuente = recuperadas.get(oferta.enlace)
        if not fuente:
            descartar(oferta.enlace, "Enlace sin descripción recuperada")
            continue
        texto = fuente["descripcion_recuperada"]
        if any(not cita_documentada(cita, texto) for cita in
               (oferta.responsabilidad_documentada, oferta.requisito_documentado)):
            descartar(oferta.enlace, "Responsabilidades o requisitos sin evidencia verificable")
            continue
        if any(v != "No documentado" and not cita_documentada(v, texto)
               for v in (oferta.puesto, oferta.empresa, oferta.ubicacion)):
            descartar(oferta.enlace, "Identificación sin respaldo en la descripción")
            continue
        if len(oferta.criterios) != len(CRITERIOS) or {c.nombre for c in oferta.criterios} != set(CRITERIOS):
            descartar(oferta.enlace, "Evaluación incompleta de dimensiones")
            continue
        # El registro de auditoría lo crea Python, no el modelo.
        for criterio in oferta.criterios:
            criterio.evaluacion_original_json = ""
        validar_criterios(oferta, perfil, texto)
        identidad = tuple(" ".join(v.lower().split()) for v in (oferta.empresa, oferta.puesto, oferta.ubicacion))
        if "No documentado" in (oferta.empresa, oferta.puesto):
            identidad = (oferta.enlace,)
        if identidad in vistas:
            descartar(oferta.enlace, "Oferta duplicada")
            continue
        vistas.add(identidad)
        validas.append(oferta)
    return validas
