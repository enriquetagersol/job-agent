"""Herramientas Tavily reutilizadas por la interfaz y la línea de comandos."""

from urllib.parse import urlsplit
import httpx
from ofertas import filtrar_ofertas
from evaluacion import Criterio, Recomendacion, Resultado, validar_recomendaciones

MAX_HERRAMIENTAS = 10

def herramienta(nombre, descripcion, propiedades):
    return {"type": "function", "name": nombre, "description": descripcion,
            "strict": True, "parameters": {"type": "object",
            "properties": propiedades, "required": list(propiedades),
            "additionalProperties": False}}


HERRAMIENTAS = [
    herramienta("buscar", "Descubre ofertas y busca sus publicaciones originales. "
                "Usa consultas profesionales sin datos de contacto del usuario.",
                {"consulta": {"type": "string"}}),
    herramienta("extraer", "Recupera la descripción de hasta cinco enlaces "
                "descubiertos mediante buscar. Prefiere empresas o su ATS oficial.",
                {"enlaces": {"type": "array", "items": {"type": "string"},
                             "maxItems": 5, "minItems": 1}}),
]


class HerramientasTavily:
    def __init__(self, cliente, avisar=None):
        self.cliente = cliente
        self.avisar = avisar or (lambda categoria, mensaje, enlace="": None)
        self.llamadas = 0
        self.descubiertos = {}
        self.recuperadas = {}
        self.metricas = {"busquedas": 0, "extracciones": 0, "resultados_busqueda": 0,
                         "paginas_solicitadas": 0, "paginas_fallidas": 0,
                         "paginas_descartadas_por_url": 0}

    def ejecutar(self, nombre, argumentos):
        if self.llamadas >= MAX_HERRAMIENTAS:
            return {"error": "Límite de diez llamadas alcanzado"}
        # También cuentan los intentos fallidos. No hay reintentos automáticos.
        self.llamadas += 1
        self.avisar("progreso", f"Herramienta {self.llamadas}/{MAX_HERRAMIENTAS}: {nombre}")
        try:
            if nombre == "buscar":
                self.metricas["busquedas"] += 1
                consulta = argumentos.get("consulta")
                if not isinstance(consulta, str) or not consulta.strip():
                    return {"error": "Consulta vacía"}
                respuesta = self.cliente.post("/search", json={
                    "query": consulta[:500], "max_results": 8,
                    "search_depth": "advanced", "include_answer": False,
                    "include_raw_content": False,
                })
                respuesta.raise_for_status()
                resultados = []
                for item in respuesta.json().get("results", []):
                    enlace = item.get("url", "")
                    if urlsplit(enlace).scheme not in ("http", "https"):
                        continue
                    self.descubiertos[enlace] = item
                    resultados.append({"enlace": enlace, "titulo": item.get("title", ""),
                                       "resumen": item.get("content", "")[:1500]})
                self.metricas["resultados_busqueda"] += len(resultados)
                return {"resultados": resultados,
                        "aviso": "Los resúmenes no son descripciones recuperadas"}
            if nombre == "extraer":
                self.metricas["extracciones"] += 1
                enlaces = argumentos.get("enlaces")
                if not isinstance(enlaces, list) or not 1 <= len(enlaces) <= 5:
                    return {"error": "Se requieren entre uno y cinco enlaces"}
                if any(not isinstance(url, str) or url not in self.descubiertos for url in enlaces):
                    return {"error": "Solo se admiten enlaces descubiertos en esta ejecución"}
                respuesta = self.cliente.post("/extract", json={
                    "urls": enlaces, "extract_depth": "advanced", "format": "text",
                })
                respuesta.raise_for_status()
                contenido = respuesta.json()
                self.metricas["paginas_solicitadas"] += len(enlaces)
                self.metricas["paginas_fallidas"] += len(contenido.get("failed_results", []))
                ofertas = []
                for item in contenido.get("results", []):
                    url = item.get("url")
                    if url not in enlaces:
                        self.metricas["paginas_descartadas_por_url"] += 1
                        continue
                    ofertas.append({"enlace": url, "fuente": urlsplit(url).netloc,
                                    "descripcion_recuperada": item.get("raw_content", "")})
                for item in contenido.get("failed_results", []):
                    self.avisar("inaccesible", "No se pudo recuperar la página", item.get("url", ""))
                recibidas = {item.get("url") for item in contenido.get("results", [])}
                fallidas = {item.get("url") for item in contenido.get("failed_results", [])}
                for url in enlaces:
                    if url not in recibidas and url not in fallidas:
                        self.avisar("inaccesible", "Tavily no devolvió contenido para esta página", url)
                for oferta in ofertas:
                    if not str(oferta.get("descripcion_recuperada", "")).strip():
                        self.avisar("inaccesible", "Descripción vacía", oferta["enlace"])
                ofertas = filtrar_ofertas(ofertas)
                for oferta in ofertas:
                    # Texto recuperado de Tavily, nunca generado por el modelo.
                    self.recuperadas[oferta["enlace"]] = oferta
                return {"ofertas": ofertas,
                        "fallidas": len(contenido.get("failed_results", []))}
            return {"error": "Herramienta desconocida"}
        except (httpx.HTTPError, ValueError, TypeError):
            self.avisar("error_tecnico", "Tavily no pudo completar la llamada; sin reintentos")
            return {"error": "Tavily no pudo completar esta llamada; no se reintentó"}



def ejecutar_busqueda():
    from agente import buscar_ofertas
    from datos_locales import cargar_perfil, contexto_busqueda
    from evaluacion import normalizar_pesos, ordenar_evaluaciones
    try:
        resultado = buscar_ofertas(contexto_busqueda(cargar_perfil()),
            lambda categoria, mensaje, enlace="": print(f"{categoria}: {mensaje} {enlace}"))
        if resultado["error"]:
            return 1
        for item in ordenar_evaluaciones(resultado["evaluaciones"], normalizar_pesos(contexto_busqueda(cargar_perfil())["perfil"]["preferencias"]))[:5]:
            oferta = item["oferta"]
            print(f"{oferta.puesto} | {oferta.empresa} | {oferta.enlace}")
            print(item["total"])
        print("El fit es orientativo, no una probabilidad de contratación.")
        return 0
    except (OSError, ValueError):
        print("No se pudo leer el perfil local.")
        return 1


if __name__ == "__main__":
    raise SystemExit(ejecutar_busqueda())
