import json
import unittest
from unittest.mock import MagicMock, patch

from profile_improvement import user_questions
from user_profile import migrate_profile, profile_for_model
from presentation import explain_listing
import test_interface as fixtures
from test_interface import sample_listing
from agent import reevaluate_listings
from evaluation import EvaluationResult


class QuestionTests(unittest.TestCase):
    def test_deduplication_limit_and_answered(self):
        listing = sample_listing()
        c = listing.criteria[1]
        c.declared_skills = ["Python", "LLM", "IA", "SQL"]
        c.points = 1
        profile = migrate_profile({})
        questions = user_questions([listing, listing], profile)
        self.assertEqual(len(questions), 3)
        self.assertEqual(len(set(k for k, _ in questions)), 3)
        profile["respuestas_confirmadas"] = {"skill:python": {"respuesta": "Curso introductorio"}}
        profile["preguntas_omitidas"] = ["skill:llm"]
        remaining = user_questions([listing], profile)
        self.assertNotIn("skill:python", dict(remaining))
        self.assertNotIn("skill:llm", dict(remaining))
        self.assertEqual(profile_for_model(profile)["confirmado"]["aclaraciones"]["skill:python"]["respuesta"], "Curso introductorio")
        self.assertEqual(profile["experiencia"], "Sin especificar")

    def test_questions_user_outside_of_cards(self):
        listing = sample_listing()
        listing.criteria[1].declared_skills = ["Python"]
        listing.criteria[1].points = 1
        listing.criteria[2].points = "Sin datos"
        result = explain_listing(listing, separate_user=True)
        self.assertFalse(any("proyectos" in p for p in result["pendientes"]))
        self.assertTrue(any("salario" in p for p in result["pendientes"]))

    def test_reevaluation_without_tavily(self):
        listing = sample_listing()
        client = MagicMock()
        client.responses.parse.return_value.status = "completed"
        client.responses.parse.return_value.output_parsed = EvaluationResult(job_listings=[], discarded=[])
        with patch('agent.OpenAI') as openai, patch('agent.httpx.Client') as tavily, patch('agent.load_dotenv'):
            openai.return_value.__enter__.return_value = client
            result = reevaluate_listings({"perfil": profile_for_model(migrate_profile({"puesto": "Analista"}))},
                {"evaluaciones": [listing.model_dump()], "fecha": "2026-10-09T12:00:00Z"})
        tavily.assert_not_called()
        self.assertEqual(client.responses.parse.call_count, 1)
        self.assertTrue(result["fuentes"][0]["solo_fragmentos"])


class AnswerInterfaceTests(unittest.TestCase):
    setUp = fixtures.InterfaceTests.setUp
    tearDown = fixtures.InterfaceTests.tearDown
    app = fixtures.InterfaceTests.app
    button = fixtures.InterfaceTests.button

    def test_skip_persistent_without_calls(self):
        listing = sample_listing()
        listing.criteria[1].declared_skills = ["Python"]
        listing.criteria[1].points = 1
        self.search.return_value["evaluaciones"] = [listing.model_dump()]
        app = self.app()
        self.button(app, "Buscar ofertas").click().run()
        app.button(key="omitir_skill:python").click().run()
        app = self.app()
        self.assertFalse(any(t.key == "respuesta_skill:python" for t in app.text_area))
        self.assertEqual(self.search.call_count, 1)
    def test_confirm_persist_edit_delete_and_update(self):
        listing = sample_listing()
        listing.criteria[1].declared_skills = ["Python"]
        listing.criteria[1].points = 1
        self.search.return_value["evaluaciones"] = [listing.model_dump()]
        app = self.app()
        self.button(app, "Buscar ofertas").click().run()
        before = self.file_path.read_bytes()
        app.text_area(key="respuesta_skill:python").set_value("Hice un ejercicio personal con Python").run()
        app.button(key="proponer_skill:python").click().run()
        self.assertEqual(self.file_path.read_bytes(), before)
        app.button(key="confirmar_skill:python").click().run()
        self.assertFalse(app.exception)
        data = json.loads(self.file_path.read_text())
        self.assertEqual(data["respuestas_confirmadas"]["skill:python"]["respuesta"], "Hice un ejercicio personal con Python")
        app = self.app()
        self.assertFalse(any(t.key == "respuesta_skill:python" for t in app.text_area))
        app.text_area(key="editar_respuesta_skill:python").set_value("Solo un curso introductorio").run()
        app.button(key="cambio_skill:python").click().run()
        self.assertEqual(json.loads(self.file_path.read_text())["respuestas_confirmadas"], data["respuestas_confirmadas"])
        app.button(key="guardar_cambio_skill:python").click().run()
        with patch('agent.reevaluate_listings', return_value=self.search.return_value) as reevaluate:
            self.button(app, "Actualizar recomendaciones").click().run()
            reevaluate.assert_called_once()
        self.assertEqual(self.search.call_count, 1)
        app.button(key="borrar_skill:python").click().run()
        self.assertFalse(json.loads(self.file_path.read_text())["respuestas_confirmadas"])


if __name__ == "__main__":
    unittest.main()
