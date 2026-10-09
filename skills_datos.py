"""Lista única, fuentes y decisiones persistentes sobre propuestas."""

import hashlib
import json

def normalizar(texto):
    return " ".join(texto.split()).casefold()


def huella_evidencia(campo, entrada_id, cita):
    return hashlib.sha256(json.dumps([campo, entrada_id, normalizar(cita)], ensure_ascii=False).encode()).hexdigest()


def registrar_rechazo(perfil, skill, fuente):
    campo = fuente.get("campo", "")
    identificador = fuente.get("entrada_id", "")
    if not campo and identificador:
        campo = next((c for c in ("experiencias", "formacion", "proyectos") if any(e["id"] == identificador for e in perfil.get(c, []))), "")
    entrada = next((e for e in perfil.get(campo, []) if e["id"] == identificador), {})
    claves = {"experiencias": ("responsabilidades", "logros", "herramientas"), "formacion": ("contenidos", "proyectos"),
              "proyectos": ("descripcion", "contribucion", "herramientas")}.get(campo, ())
    texto = "\n".join(entrada.get(k, "").strip() for k in claves if entrada.get(k, "").strip())
    decision = {"skill": normalizar(skill), "evidencia": huella_evidencia(
        campo, identificador, fuente.get("cita", "")), "contexto": huella_evidencia(campo, identificador, texto)}
    lista = perfil.setdefault("skills_rechazadas", [])
    if decision not in lista:
        lista.append(decision)


def fuentes_de_skill(perfil, skill):
    origen = perfil.get("origen_skills", {}).get(skill, {})
    return origen.get("fuentes", [origen] if origen else [])


def eliminar_skill(perfil, skill):
    fuentes = fuentes_de_skill(perfil, skill)
    for fuente in fuentes:
        registrar_rechazo(perfil, skill, fuente)
        if fuente.get("skill_original"):
            registrar_rechazo(perfil, fuente["skill_original"], fuente)
    if not any(f.get("entrada_id") for f in fuentes):
        for campo in ("experiencias", "formacion", "proyectos"):
            for entrada in perfil.get(campo, []):
                registrar_rechazo(perfil, skill, {"campo": campo, "entrada_id": entrada["id"]})
    archivo = perfil.setdefault("archivo_fuentes_skills", {}).setdefault(skill, [])
    for fuente in fuentes:
        if fuente not in archivo:
            archivo.append(fuente)
    perfil["skills"] = [s for s in perfil["skills"] if normalizar(s) != normalizar(skill)]
    perfil["origen_skills"].pop(skill, None)


def posible_equivalencia(skill, existentes):
    grupos = ({"project management", "gestion de proyectos", "gestión de proyectos"},
              {"communication", "comunicación", "comunicacion"},
              {"artificial intelligence", "inteligencia artificial", "ia", "ai"},
              {"machine learning", "aprendizaje automático", "aprendizaje automatico"})
    for grupo in grupos:
        if normalizar(skill) in grupo:
            return next((s for s in existentes if normalizar(s) in grupo), None)
    return None


def agregar_fuente(perfil, skill, fuente):
    fuentes = fuentes_de_skill(perfil, skill)
    if fuente not in fuentes:
        fuentes.append(fuente)
    perfil["origen_skills"][skill] = {"tipo": fuentes[0].get("tipo", "Declaración confirmada") if len(fuentes) == 1 else "Fuentes múltiples", "fuentes": fuentes}
