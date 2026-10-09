"""Perfil compatible con versiones anteriores y evaluaciones privadas locales."""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).parent
ARCHIVO_PERFIL = BASE / "perfil.json"
ARCHIVO_EVALUACIONES = BASE / ".datos" / "evaluaciones.json"
VERSION = 3


def leer_json(archivo, defecto=None):
    if not archivo.exists():
        return defecto
    return json.loads(archivo.read_text(encoding="utf-8"))


def guardar_json(archivo, contenido):
    archivo = Path(archivo)
    if archivo.resolve() == ARCHIVO_PERFIL.resolve() and isinstance(contenido, dict):
        from trayectoria import validar_entrada
        anterior = leer_json(archivo, {})
        for campo in ("experiencias", "formacion", "proyectos"):
            for entrada in contenido.get(campo, []):
                antigua = next((e for e in anterior.get(campo, []) if e.get("id") == entrada.get("id")), None)
                if entrada != antigua:
                    validar_entrada(campo, entrada)
    if archivo.resolve() == ARCHIVO_PERFIL.resolve() and isinstance(contenido, dict) and contenido.get("version_perfil") == 3:
        from perfil import validar_perfil
        validar_perfil(contenido, anterior=leer_json(archivo, {}))
    archivo.parent.mkdir(parents=True, exist_ok=True)
    temporal = archivo.with_suffix(".tmp")
    temporal.write_text(json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporal.chmod(0o600)
    temporal.replace(archivo)


def cargar_perfil():
    perfil = leer_json(ARCHIVO_PERFIL, {})
    if not isinstance(perfil, dict):
        raise ValueError("Perfil inválido")
    return perfil


def contexto_busqueda(perfil):
    from perfil import migrar_perfil, perfil_para_modelo
    actual = migrar_perfil(perfil)
    from trayectoria import empresa_para_excluir
    return {"perfil": perfil_para_modelo(actual),
            "empresa_excluida": empresa_para_excluir(actual).strip() if actual["excluir_empresa_actual"] else ""}


def huella_contexto(contexto):
    contenido = json.dumps({"version": VERSION, **contexto}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(contenido.encode()).hexdigest()


def cargar_evaluaciones():
    datos = leer_json(ARCHIVO_EVALUACIONES, None)
    if datos is not None and (not isinstance(datos, dict) or datos.get("version") != VERSION):
        return None
    return datos


def guardar_evaluaciones(contexto, resultado):
    datos = {"version": VERSION, "huella": huella_contexto(contexto),
             "contexto": contexto, **resultado}
    guardar_json(ARCHIVO_EVALUACIONES, datos)
    return datos
