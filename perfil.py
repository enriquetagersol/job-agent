"""Edición del perfil sin llamadas externas ni inferencias sobre el usuario."""

import copy
import re
import unicodedata
from trayectoria import completar_trayectoria, validar_entrada

PREFERENCIAS = ("Baja", "Media", "Alta")
MODALIDADES = ("Presencial", "Híbrido", "Remoto")
EXPERIENCIAS = ("Sin especificar", "Sin experiencia", "<1 año", "1–3 años", "4–6 años", ">6 años")
NIVELES = ("Básico", "Intermedio", "Alto", "Nativo/bilingüe")
MONEDAS = ("EUR", "GBP", "USD", "CAD", "CHF", "MXN", "ARS", "COP", "CLP", "BRL")


def identidad(texto):
    texto = " ".join(texto.split()).casefold()
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def anadir_opcion(opciones, texto, limite=None):
    texto = " ".join(texto.split())
    if not texto:
        raise ValueError("La opción no puede estar vacía.")
    if identidad(texto) in {identidad(o) for o in opciones}:
        raise ValueError("Esa opción ya está añadida.")
    if limite is not None and len(opciones) >= limite:
        raise ValueError(f"Ya has añadido el máximo de {limite} opciones.")
    return [*opciones, texto]


def eliminar_opcion(opciones, texto):
    return [o for o in opciones if identidad(o) != identidad(texto)]


def migrar_perfil(anterior):
    """Conserva la fuente antigua; solo migra equivalencias explícitas."""
    if anterior.get("version_perfil") == 3:
        perfil = copy.deepcopy(anterior)
        perfil.setdefault("empresa_actual", "")
        perfil.setdefault("excluir_empresa_actual", False)
        return completar_trayectoria(perfil)
    puestos = [anterior["puesto"]] if str(anterior.get("puesto", "")).strip() else []
    ubicaciones = [{"nombre": anterior["ubicacion"], "preferencia": None}] if str(anterior.get("ubicacion", "")).strip() else []
    skills = [anterior["capacidades"]] if str(anterior.get("capacidades", "")).strip() else []
    experiencia = anterior.get("experiencia_profesional", "")
    if experiencia not in EXPERIENCIAS:
        coincidencia = re.fullmatch(r"\s*(\d+)\s*años?\s*", experiencia, re.IGNORECASE)
        if coincidencia:
            anos = int(coincidencia[1])
            experiencia = "Sin experiencia" if anos == 0 else "1–3 años" if anos <= 3 else "4–6 años" if anos <= 6 else ">6 años"
        else:
            experiencia = "Sin especificar"
    modalidad = anterior.get("modalidad", anterior.get("preferencias_laborales", ""))
    modalidades = {m: None for m in MODALIDADES if identidad(m) == identidad(modalidad)}
    return completar_trayectoria({"version_perfil": 3, "puestos_objetivo": puestos, "ubicaciones": ubicaciones,
            "modalidades": modalidades, "skills": skills, "idiomas": [],
            "experiencia": experiencia, "salario_minimo": None, "moneda": None,
            "importancia_ubicacion": None, "importancia_modalidad": None,
            "importancia_salario": None, "que_buscas": "",
            "empresa_actual": anterior.get("empresa_actual", ""),
            "excluir_empresa_actual": anterior.get("excluir_empresa_actual", False),
            "datos_anteriores": copy.deepcopy(anterior)})


def validar_perfil(perfil, anterior=None):
    for campo in ("experiencias", "formacion", "proyectos"):
        ids = set()
        for entrada in perfil.get(campo, []):
            antigua = next((e for e in (anterior or {}).get(campo, []) if e.get("id") == entrada.get("id")), None)
            if entrada != antigua:
                validar_entrada(campo, entrada)
            if entrada["id"] in ids:
                raise ValueError("Entrada de trayectoria duplicada.")
            ids.add(entrada["id"])
    if not isinstance(perfil.get("empresa_actual", ""), str) or not isinstance(perfil.get("excluir_empresa_actual", False), bool):
        raise ValueError("Empresa actual o exclusión inválida.")
    for campo, limite in (("puestos_objetivo", 5), ("skills", 10)):
        opciones = []
        for valor in perfil[campo]:
            opciones = anadir_opcion(opciones, valor, limite)
    opciones = []
    for ubicacion in perfil["ubicaciones"]:
        opciones = anadir_opcion(opciones, ubicacion["nombre"], 5)
        if ubicacion["preferencia"] is not None and ubicacion["preferencia"] not in PREFERENCIAS:
            raise ValueError("Preferencia de ubicación inválida.")
    for modalidad, preferencia in perfil["modalidades"].items():
        if modalidad not in MODALIDADES or (preferencia is not None and preferencia not in PREFERENCIAS):
            raise ValueError("Modalidad o preferencia inválida.")
    opciones = []
    for idioma in perfil["idiomas"]:
        opciones = anadir_opcion(opciones, idioma["idioma"])
        if idioma["nivel"] is not None and idioma["nivel"] not in NIVELES:
            raise ValueError("Nivel de idioma inválido.")
    minimo = perfil["salario_minimo"]
    if minimo is not None and (isinstance(minimo, bool) or not isinstance(minimo, (int, float)) or minimo < 0):
        raise ValueError("El salario mínimo debe ser no negativo o estar sin especificar.")
    if (perfil["moneda"] is not None and perfil["moneda"] not in MONEDAS) or perfil["experiencia"] not in EXPERIENCIAS:
        raise ValueError("Moneda o experiencia inválida.")
    for campo in ("importancia_ubicacion", "importancia_modalidad", "importancia_salario"):
        if perfil[campo] is not None and perfil[campo] not in PREFERENCIAS:
            raise ValueError("Importancia inválida.")
    if len(perfil["que_buscas"]) > 400:
        raise ValueError("¿Qué buscas? admite un máximo de 400 caracteres.")
    return perfil


def perfil_para_modelo(perfil):
    perfil = migrar_perfil(perfil)
    # No enviar campos desconocidos o preferencias antiguas que el usuario haya sustituido.
    confirmado = {campo: copy.deepcopy(perfil[campo]) for campo in
        ("skills", "idiomas", "experiencia")}
    confirmado["aclaraciones"] = copy.deepcopy(perfil.get("respuestas_confirmadas", {}))
    for campo in ("experiencias", "formacion", "proyectos", "origen_skills"):
        confirmado[campo] = copy.deepcopy(perfil[campo])
    anterior = perfil.get("datos_anteriores", {})
    if perfil["experiencia"] == "Sin especificar" and anterior.get("experiencia_profesional"):
        confirmado["experiencia_detalle_confirmado"] = anterior["experiencia_profesional"]
    preferencias = {campo: copy.deepcopy(perfil[campo]) for campo in
        ("puestos_objetivo", "ubicaciones", "modalidades", "salario_minimo", "moneda",
         "importancia_ubicacion", "importancia_modalidad", "importancia_salario", "que_buscas")}
    return {"confirmado": confirmado, "preferencias": preferencias}


def empresa_excluida(empresa, empresa_actual):
    def normalizar(nombre):
        palabras = re.findall(r"\w+", identidad(nombre))
        legales = {"ltd", "limited", "inc", "incorporated", "llc", "plc", "sa", "sl", "corp", "corporation"}
        while palabras and palabras[-1] in legales:
            palabras.pop()
        return " ".join(palabras)
    actual = normalizar(empresa_actual)
    return bool(actual) and normalizar(empresa) == actual
