"""Tavily tools shared by the interface and command line."""

from urllib.parse import urlsplit
import httpx
from job_listings import filter_listings
from evaluation import Criterion, Recommendation, EvaluationResult, validate_recommendations

MAX_TOOL_CALLS = 10

def define_tool(name, description, properties):
    return {"type": "function", "name": name, "description": description,
            "strict": True, "parameters": {"type": "object",
            "properties": properties, "required": list(properties),
            "additionalProperties": False}}


TOOLS = [
    define_tool("search", "Descubre ofertas y busca sus publicaciones originales. "
                "Usa consultas profesionales sin datos de contacto del usuario.",
                {"query": {"type": "string"}}),
    define_tool("extract", "Recupera la descripción de hasta cinco enlaces "
                "descubiertos mediante search. Prefiere empresas o su ATS oficial.",
                {"urls": {"type": "array", "items": {"type": "string"},
                             "maxItems": 5, "minItems": 1}}),
]


class TavilyTools:
    def __init__(self, client, notify=None):
        self.client = client
        self.notify = notify or (lambda category, message, url="": None)
        self.calls = 0
        self.discovered = {}
        self.retrieved = {}
        self.metrics = {"busquedas": 0, "extracciones": 0, "resultados_busqueda": 0,
                         "paginas_solicitadas": 0, "paginas_fallidas": 0,
                         "paginas_descartadas_por_url": 0}

    def execute(self, name, arguments):
        if self.calls >= MAX_TOOL_CALLS:
            return {"error": "Límite de diez llamadas alcanzado"}
        # Failed attempts also count. There are no automatic retries.
        self.calls += 1
        self.notify("progreso", f"Herramienta {self.calls}/{MAX_TOOL_CALLS}: {name}")
        try:
            if name in ("search", "buscar"):
                self.metrics["busquedas"] += 1
                query = arguments.get("query", arguments.get("consulta"))
                if not isinstance(query, str) or not query.strip():
                    return {"error": "Consulta vacía"}
                response = self.client.post("/search", json={
                    "query": query[:500], "max_results": 8,
                    "search_depth": "advanced", "include_answer": False,
                    "include_raw_content": False,
                })
                response.raise_for_status()
                results = []
                for item in response.json().get("results", []):
                    url = item.get("url", "")
                    if urlsplit(url).scheme not in ("http", "https"):
                        continue
                    self.discovered[url] = item
                    results.append({"enlace": url, "titulo": item.get("title", ""),
                                       "resumen": item.get("content", "")[:1500]})
                self.metrics["resultados_busqueda"] += len(results)
                return {"resultados": results,
                        "aviso": "Los resúmenes no son descripciones recuperadas"}
            if name in ("extract", "extraer"):
                self.metrics["extracciones"] += 1
                urls = arguments.get("urls", arguments.get("enlaces"))
                if not isinstance(urls, list) or not 1 <= len(urls) <= 5:
                    return {"error": "Se requieren entre uno y cinco enlaces"}
                if any(not isinstance(url, str) or url not in self.discovered for url in urls):
                    return {"error": "Solo se admiten enlaces descubiertos en esta ejecución"}
                response = self.client.post("/extract", json={
                    "urls": urls, "extract_depth": "advanced", "format": "text",
                })
                response.raise_for_status()
                content = response.json()
                self.metrics["paginas_solicitadas"] += len(urls)
                self.metrics["paginas_fallidas"] += len(content.get("failed_results", []))
                job_listings = []
                for item in content.get("results", []):
                    url = item.get("url")
                    if url not in urls:
                        self.metrics["paginas_descartadas_por_url"] += 1
                        continue
                    job_listings.append({"enlace": url, "fuente": urlsplit(url).netloc,
                                    "descripcion_recuperada": item.get("raw_content", "")})
                for item in content.get("failed_results", []):
                    self.notify("inaccesible", "No se pudo recuperar la página", item.get("url", ""))
                received = {item.get("url") for item in content.get("results", [])}
                failed = {item.get("url") for item in content.get("failed_results", [])}
                for url in urls:
                    if url not in received and url not in failed:
                        self.notify("inaccesible", "Tavily no devolvió contenido para esta página", url)
                for listing in job_listings:
                    if not str(listing.get("descripcion_recuperada", "")).strip():
                        self.notify("inaccesible", "Descripción vacía", listing["enlace"])
                job_listings = filter_listings(job_listings)
                for listing in job_listings:
                    # Text retrieved from Tavily, never generated by the model.
                    self.retrieved[listing["enlace"]] = listing
                return {"ofertas": job_listings,
                        "fallidas": len(content.get("failed_results", []))}
            return {"error": "Herramienta desconocida"}
        except (httpx.HTTPError, ValueError, TypeError):
            self.notify("error_tecnico", "Tavily no pudo completar la llamada; sin reintentos")
            return {"error": "Tavily no pudo completar esta llamada; no se reintentó"}



def run_search():
    from agent import search_listings
    from local_storage import load_profile, search_context
    from evaluation import normalize_weights, rank_evaluations
    try:
        result = search_listings(search_context(load_profile()),
            lambda category, message, url="": print(f"{category}: {message} {url}"))
        if result["error"]:
            return 1
        for item in rank_evaluations(result["evaluaciones"], normalize_weights(search_context(load_profile())["perfil"]["preferencias"]))[:5]:
            listing = item["oferta"]
            print(f"{listing.role} | {listing.company} | {listing.url}")
            print(item["total"])
        print("El fit es orientativo, no una probabilidad de contratación.")
        return 0
    except (OSError, ValueError):
        print("No se pudo leer el perfil local.")
        return 1


if __name__ == "__main__":
    raise SystemExit(run_search())
