import unittest
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from busqueda import (Criterio, HerramientasTavily, Recomendacion, Resultado,
                      validar_recomendaciones)


class PruebasBusqueda(unittest.TestCase):
    def test_distingue_error_tecnico_y_pagina_inaccesible(self):
        import httpx
        eventos = []
        cliente = Mock()
        herramientas = HerramientasTavily(cliente, lambda *e: eventos.append(e))
        cliente.post.side_effect = httpx.ConnectError("Error ficticio")
        herramientas.ejecutar("buscar", {"consulta": "ofertas ficticias"})
        self.assertTrue(any(e[0] == "error_tecnico" for e in eventos))
        cliente.post.side_effect = None
        url = "https://example.com/oferta"
        herramientas.descubiertos[url] = {}
        cliente.post.return_value.json.return_value = {"results": [], "failed_results": [{"url": url}]}
        herramientas.ejecutar("extraer", {"enlaces": [url]})
        self.assertTrue(any(e[0] == "inaccesible" and e[2] == url for e in eventos))

    def test_agente_encadena_modelo_busqueda_extraccion_y_evaluacion(self):
        from agente import buscar_ofertas
        from test_interfaz import oferta_ficticia
        oferta = oferta_ficticia()
        texto = "Empresa ficticia Analista Madrid Analizar datos Python"
        llamada_buscar = SimpleNamespace(type="function_call", name="buscar", call_id="1",
            arguments=json.dumps({"consulta": "Analista Madrid"}))
        llamada_extraer = SimpleNamespace(type="function_call", name="extraer", call_id="2",
            arguments=json.dumps({"enlaces": [oferta.enlace]}))
        with patch("agente.load_dotenv"), patch("agente.guardar_diagnostico"), patch.dict("os.environ", {
            "OPENAI_API_KEY": "clave-ficticia", "TAVILY_API_KEY": "clave-ficticia"}), \
            patch("agente.OpenAI") as openai, patch("agente.httpx.Client") as http:
            modelo = openai.return_value.__enter__.return_value
            modelo.responses.create.side_effect = [
                SimpleNamespace(status="completed", output=[llamada_buscar]),
                SimpleNamespace(status="completed", output=[llamada_extraer]),
                SimpleNamespace(status="completed", output=[])]
            modelo.responses.parse.return_value = SimpleNamespace(status="completed",
                output_parsed=Resultado(ofertas=[oferta], descartadas=[]))
            cliente = http.return_value.__enter__.return_value
            respuestas = [Mock(), Mock()]
            respuestas[0].json.return_value = {"results": [{"url": oferta.enlace, "title": "Analista"}]}
            respuestas[1].json.return_value = {"results": [{"url": oferta.enlace, "raw_content": texto}]}
            cliente.post.side_effect = respuestas
            resultado = buscar_ofertas({"perfil": {"confirmado": {"skills": ["Python"]}, "preferencias": {"puestos_objetivo": ["Analista"]}}})
            self.assertFalse(resultado["error"])
            self.assertEqual(resultado["llamadas"], 2)
            self.assertEqual(len(resultado["evaluaciones"]), 1)
            self.assertEqual([c.args[0] for c in cliente.post.call_args_list], ["/search", "/extract"])
            self.assertFalse(modelo.responses.parse.call_args.kwargs["store"])
            contexto = {"perfil": {"confirmado": {"skills": ["Python"]},
                                   "preferencias": {"puestos_objetivo": ["Analista"]}},
                        "empresa_excluida": "Empresa ficticia Ltd"}
            modelo.responses.create.side_effect = [
                SimpleNamespace(status="completed", output=[llamada_buscar]),
                SimpleNamespace(status="completed", output=[llamada_extraer]),
                SimpleNamespace(status="completed", output=[])]
            cliente.post.side_effect = respuestas
            excluido = buscar_ofertas(contexto)
            self.assertEqual(excluido["evaluaciones"], [])
            self.assertEqual(excluido["metricas"]["validas_antes_exclusion"], 1)

    def test_diagnostico_no_guarda_texto_libre_ni_enlaces(self):
        from diagnostico import evento_seguro
        evento = evento_seguro("descartada", "Texto con perfil, salario, clave y experiencia privados")
        self.assertEqual(evento, {"categoria": "descartada", "codigo": "descartada"})
        from perfil import empresa_excluida
        self.assertTrue(empresa_excluida("ACME, Inc.", "Acme"))
        self.assertFalse(empresa_excluida("Acme Technology", "Acme"))

    def test_citas_toleran_formato_pero_no_parafrasis(self):
        from evaluacion import cita_documentada
        self.assertTrue(cita_documentada("Build AI-based solutions.", "• Build AI–based\n solutions"))
        self.assertFalse(cita_documentada("Build AI solutions", "Build AI based solutions"))
        self.assertFalse(cita_documentada("Requires Python", "Does not require Python"))
        self.assertFalse(cita_documentada("SQL", "PostgreSQL"))

    def test_lotes_pequenos_conservan_resultados_si_un_lote_falla(self):
        import httpx
        from openai import APIConnectionError
        from agente import buscar_ofertas
        from test_interfaz import oferta_ficticia
        ofertas = [oferta_ficticia(puesto=f"Analista {n}", enlace=f"https://example.com/{n}") for n in range(4)]
        buscar = SimpleNamespace(type="function_call", name="buscar", call_id="1", arguments=json.dumps({"consulta": "Analista"}))
        extraer = SimpleNamespace(type="function_call", name="extraer", call_id="2", arguments=json.dumps({"enlaces": [o.enlace for o in ofertas]}))
        with patch("agente.load_dotenv"), patch("agente.guardar_diagnostico"), patch.dict("os.environ", {
            "OPENAI_API_KEY": "ficticia", "TAVILY_API_KEY": "ficticia"}), \
            patch("agente.OpenAI") as openai, patch("agente.httpx.Client") as http:
            modelo = openai.return_value.__enter__.return_value
            modelo.responses.create.side_effect = [SimpleNamespace(status="completed", output=[buscar]),
                SimpleNamespace(status="completed", output=[extraer]), SimpleNamespace(status="completed", output=[])]
            modelo.responses.parse.side_effect = [APIConnectionError(request=httpx.Request("POST", "https://example.com")),
                SimpleNamespace(status="completed", output_parsed=Resultado(ofertas=[ofertas[-1]], descartadas=[]))]
            cliente = http.return_value.__enter__.return_value
            r1, r2 = Mock(), Mock()
            r1.json.return_value = {"results": [{"url": o.enlace, "title": o.puesto} for o in ofertas]}
            r2.json.return_value = {"results": [{"url": o.enlace, "raw_content": f"Empresa ficticia {o.puesto} Madrid Analizar datos Python"} for o in ofertas]}
            cliente.post.side_effect = [r1, r2]
            resultado = buscar_ofertas({"perfil": {"confirmado": {"skills": ["Python"]}, "preferencias": {"puestos_objetivo": ["Analista"]}}})
            self.assertFalse(resultado["error"])
            self.assertEqual(len(resultado["evaluaciones"]), 1)
            self.assertEqual(resultado["metricas"]["lotes_fallidos"], 1)
            self.assertEqual(resultado["metricas"]["lotes_evaluados"], 1)
            for llamada in modelo.responses.parse.call_args_list:
                self.assertLessEqual(len(json.loads(llamada.kwargs["input"])["ofertas"]), 3)

    def test_limite_incluye_fallos_y_bloquea_undecima_llamada(self):
        cliente = Mock()
        cliente.post.return_value.json.return_value = {"results": []}
        herramientas = HerramientasTavily(cliente)
        with patch("builtins.print"):
            for _ in range(12):
                herramientas.ejecutar("buscar", {"consulta": "ofertas ficticias"})
        self.assertEqual(herramientas.llamadas, 10)
        self.assertEqual(cliente.post.call_count, 10)

    def test_extraccion_rechaza_url_inventada_y_descripcion_vacia(self):
        cliente = Mock()
        herramientas = HerramientasTavily(cliente)
        url = "https://example.com/empleo"
        with patch("builtins.print"):
            herramientas.ejecutar("extraer", {"enlaces": [url]})
            cliente.post.assert_not_called()
            herramientas.descubiertos[url] = {}
            cliente.post.return_value.json.return_value = {
                "results": [{"url": url, "raw_content": " "}]}
            herramientas.ejecutar("extraer", {"enlaces": [url]})
        self.assertEqual(herramientas.recuperadas, {})

    def test_evidencia_y_duplicados(self):
        from test_interfaz import oferta_ficticia
        oferta = oferta_ficticia()
        otra = oferta.model_copy(update={"enlace": "https://example.com/2"})
        texto = "Empresa ficticia Analista Madrid Analizar datos Python"
        perfil = {"confirmado": {"skills": ["Python"]}, "preferencias": {"puestos_objetivo": ["Analista"]}}
        recuperadas = {url: {"descripcion_recuperada": texto} for url in (oferta.enlace, otra.enlace)}
        resultado = Resultado(ofertas=[oferta, otra], descartadas=[])
        validas = validar_recomendaciones(resultado, recuperadas, perfil)
        self.assertEqual(len(validas), 1)
        oferta.criterios[1].evidencia_perfil = "Capacidad inventada"
        resultado = Resultado(ofertas=[oferta], descartadas=[])
        validas = validar_recomendaciones(resultado, recuperadas, perfil)
        # La cita inventada se rechaza; Python reconoce por separado la skill
        # realmente declarada y requerida, sin atribuir dominio profesional.
        self.assertEqual(validas[0].criterios[1].puntos, 1)
        self.assertEqual(validas[0].criterios[1].skills_declaradas, ["Python"])
        self.assertNotIn("Capacidad inventada", validas[0].criterios[1].evidencias_perfil)
        self.assertEqual(validar_recomendaciones(resultado, {}, perfil), [])


if __name__ == "__main__":
    unittest.main()
