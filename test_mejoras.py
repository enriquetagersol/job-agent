import json
import unittest
from unittest.mock import MagicMock, patch

from mejoras import preguntas_usuario
from perfil import migrar_perfil, perfil_para_modelo
from presentacion import explicar_oferta
import test_interfaz as fixtures
from test_interfaz import oferta_ficticia
from agente import reevaluar_ofertas
from evaluacion import Resultado


class Preguntas(unittest.TestCase):
    def test_deduplicacion_limite_y_respondidas(self):
        oferta = oferta_ficticia()
        c = oferta.criterios[1]
        c.skills_declaradas = ["Python", "LLM", "IA", "SQL"]
        c.puntos = 1
        perfil = migrar_perfil({})
        preguntas = preguntas_usuario([oferta, oferta], perfil)
        self.assertEqual(len(preguntas), 3)
        self.assertEqual(len(set(k for k, _ in preguntas)), 3)
        perfil["respuestas_confirmadas"] = {"skill:python": {"respuesta": "Curso introductorio"}}
        perfil["preguntas_omitidas"] = ["skill:llm"]
        restantes = preguntas_usuario([oferta], perfil)
        self.assertNotIn("skill:python", dict(restantes))
        self.assertNotIn("skill:llm", dict(restantes))
        self.assertEqual(perfil_para_modelo(perfil)["confirmado"]["aclaraciones"]["skill:python"]["respuesta"], "Curso introductorio")
        self.assertEqual(perfil["experiencia"], "Sin especificar")

    def test_preguntas_usuario_fuera_de_tarjetas(self):
        oferta = oferta_ficticia()
        oferta.criterios[1].skills_declaradas = ["Python"]
        oferta.criterios[1].puntos = 1
        oferta.criterios[2].puntos = "Sin datos"
        resultado = explicar_oferta(oferta, separar_usuario=True)
        self.assertFalse(any("proyectos" in p for p in resultado["pendientes"]))
        self.assertTrue(any("salario" in p for p in resultado["pendientes"]))

    def test_reevaluacion_sin_tavily(self):
        oferta = oferta_ficticia()
        cliente = MagicMock()
        cliente.responses.parse.return_value.status = "completed"
        cliente.responses.parse.return_value.output_parsed = Resultado(ofertas=[], descartadas=[])
        with patch("agente.OpenAI") as openai, patch("agente.httpx.Client") as tavily, patch("agente.load_dotenv"):
            openai.return_value.__enter__.return_value = cliente
            resultado = reevaluar_ofertas({"perfil": perfil_para_modelo(migrar_perfil({"puesto": "Analista"}))},
                {"evaluaciones": [oferta.model_dump()], "fecha": "2026-10-09T12:00:00Z"})
        tavily.assert_not_called()
        self.assertEqual(cliente.responses.parse.call_count, 1)
        self.assertTrue(resultado["fuentes"][0]["solo_fragmentos"])


class RespuestasInterfaz(unittest.TestCase):
    setUp = fixtures.PruebasInterfaz.setUp
    tearDown = fixtures.PruebasInterfaz.tearDown
    app = fixtures.PruebasInterfaz.app
    boton = fixtures.PruebasInterfaz.boton

    def test_omitir_persistente_sin_llamadas(self):
        oferta = oferta_ficticia()
        oferta.criterios[1].skills_declaradas = ["Python"]
        oferta.criterios[1].puntos = 1
        self.buscar.return_value["evaluaciones"] = [oferta.model_dump()]
        app = self.app()
        self.boton(app, "Buscar ofertas").click().run()
        app.button(key="omitir_skill:python").click().run()
        app = self.app()
        self.assertFalse(any(t.key == "respuesta_skill:python" for t in app.text_area))
        self.assertEqual(self.buscar.call_count, 1)
    def test_confirmar_persistir_editar_borrar_y_actualizar(self):
        oferta = oferta_ficticia()
        oferta.criterios[1].skills_declaradas = ["Python"]
        oferta.criterios[1].puntos = 1
        self.buscar.return_value["evaluaciones"] = [oferta.model_dump()]
        app = self.app()
        self.boton(app, "Buscar ofertas").click().run()
        antes = self.archivo.read_bytes()
        app.text_area(key="respuesta_skill:python").set_value("Hice un ejercicio personal con Python").run()
        app.button(key="proponer_skill:python").click().run()
        self.assertEqual(self.archivo.read_bytes(), antes)
        app.button(key="confirmar_skill:python").click().run()
        self.assertFalse(app.exception)
        datos = json.loads(self.archivo.read_text())
        self.assertEqual(datos["respuestas_confirmadas"]["skill:python"]["respuesta"], "Hice un ejercicio personal con Python")
        app = self.app()
        self.assertFalse(any(t.key == "respuesta_skill:python" for t in app.text_area))
        app.text_area(key="editar_respuesta_skill:python").set_value("Solo un curso introductorio").run()
        app.button(key="cambio_skill:python").click().run()
        self.assertEqual(json.loads(self.archivo.read_text())["respuestas_confirmadas"], datos["respuestas_confirmadas"])
        app.button(key="guardar_cambio_skill:python").click().run()
        with patch("agente.reevaluar_ofertas", return_value=self.buscar.return_value) as reevaluar:
            self.boton(app, "Actualizar recomendaciones").click().run()
            reevaluar.assert_called_once()
        self.assertEqual(self.buscar.call_count, 1)
        app.button(key="borrar_skill:python").click().run()
        self.assertFalse(json.loads(self.archivo.read_text())["respuestas_confirmadas"])


if __name__ == "__main__":
    unittest.main()
