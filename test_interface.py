import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import local_storage
from local_storage import save_json, context_fingerprint, search_context
from evaluation import (CRITERIA, Criterion, SalaryData, Recommendation, EvaluationResult,
                        calculate_fit, normalize_weights, rank_evaluations,
                        validate_recommendations)
from profile_ui import option_key
from user_profile import add_option, remove_option, migrate_profile, profile_for_model, validate_profile


def sample_listing(role="Analista", url="https://example.com/1", points=None):
    points = points or [2, 2, 1, "Sin datos", "Sin datos", "Sin datos", "Sin datos"]
    return Recommendation(url=url, role=role, company="Empresa ficticia", location="Madrid",
        documented_responsibility="Analizar datos", documented_requirement="Python",
        criteria=[Criterion(name=n, points=p, reason="Motivo ficticio", listing_evidence="Python",
                   profile_evidence="Python", compatible_option="", compatibility="Compatible")
                   for n, p in zip(CRITERIA, points)],
        documented_salary=SalaryData(minimum=None, maximum=None, currency=None,
            period="No documentado", kind="No documentado", evidence="No documentado"),
        gaps=["Salario no documentado"])


class ProfileTests(unittest.TestCase):
    def test_limits_empty_duplicates_and_slots(self):
        for limit in (5, 10):
            options = []
            for n in range(limit):
                options = add_option(options, f"Opción {n}", limit)
            with self.assertRaises(ValueError):
                add_option(options, "Una más", limit)
            options = remove_option(options, "Opción 0")
            options = add_option(options, "Nueva", limit)
            self.assertEqual(len(options), limit)
        for text in ("", "  ", "python", " PYTHON "):
            with self.assertRaises(ValueError):
                add_option(["Python"], text, 10)
        languages = []
        for n in range(25):
            languages = add_option(languages, f"Idioma {n}")
        self.assertEqual(len(languages), 25)

    def test_migration_not_fabricates_and_preserves_data(self):
        legacy = {"puesto": "Analista", "ubicacion": "Madrid", "capacidades": "Python",
                   "experiencia_profesional": "3 años", "preferencias_laborales": "Híbrido",
                   "salario": "3000 EUR mensuales", "dato_extra": "conservar"}
        profile = migrate_profile(legacy)
        self.assertEqual(profile["puestos_objetivo"], ["Analista"])
        self.assertEqual(profile["experiencia"], "1–3 años")
        self.assertIsNone(profile["salario_minimo"])
        self.assertEqual(profile["idiomas"], [])
        self.assertEqual(profile["datos_anteriores"], legacy)
        self.assertEqual(migrate_profile(profile), profile)
        profile["que_buscas"] = "Quiero aprender Rust"
        sent = profile_for_model(profile)
        self.assertNotIn("Rust", str(sent["confirmado"]))
        self.assertIn("Rust", sent["preferencias"]["que_buscas"])
        self.assertNotIn("filtros", search_context(profile))
        self.assertNotIn("imprescindibles", search_context(profile))

    def test_salary_and_limit_aspirations(self):
        profile = migrate_profile({})
        profile["salario_minimo"] = -1
        with self.assertRaises(ValueError):
            validate_profile(profile)
        profile["salario_minimo"] = None
        profile["que_buscas"] = "x" * 401
        with self.assertRaises(ValueError):
            validate_profile(profile)
        profile["que_buscas"] = "x" * 400
        self.assertEqual(validate_profile(profile), profile)


class RankingTests(unittest.TestCase):
    def test_happyrobot_evidence_listed_not_confirm_proficiency(self):
        from evaluation import validate_criteria
        from presentation import explain_listing
        import json
        listing = sample_listing(role="Deployment Strategist")
        profile = {"confirmado": {"skills": ["Python", "LLM"], "experiencia": "Sin especificar"},
                  "preferencias": {"puestos_objetivo": ["Deployment Strategist"], "modalidades": {"Híbrido": "Alta"}}}
        text = "Deployment Strategist. Comfortable coding Python using LLMs. Hybrid."
        listing.documented_requirement = "Comfortable coding Python using LLMs."
        listing.criteria[0].profile_evidence = "Preferencia: «Deployment Strategist»"
        listing.criteria[0].listing_evidence = "Deployment Strategist"
        skill = listing.criteria[1]
        skill.profile_evidence = "Skills confirmadas: «Python», «LLM»"
        skill.listing_evidence = listing.documented_requirement
        skill.points = 2
        mode = listing.criteria[5]
        mode.profile_evidence = "Preferencia: «Híbrido» (Alta)"
        mode.listing_evidence = "Hybrid"
        mode.compatible_option = "Hybrid"
        mode.points = "Sin datos"
        validate_criteria(listing, profile, text)
        self.assertEqual(skill.points, 1)
        self.assertEqual(skill.declared_skills, ["Python", "LLM"])
        self.assertEqual(json.loads(skill.original_evaluation_json)["puntos"], 2)
        self.assertEqual(mode.points, 2)
        self.assertEqual(listing.criteria[2].points, "Sin datos")
        sections = explain_listing(listing)
        self.assertTrue(sections["interes"])
        self.assertTrue(sections["parciales"])
        self.assertFalse(sections["gaps"])

    def test_weights_approved_and_without_data(self):
        profile = migrate_profile({})
        profile.update(importancia_ubicacion="Baja", importancia_modalidad="Baja", importancia_salario="Baja")
        weights = normalize_weights(profile)
        self.assertEqual(weights["puesto"], .25)
        self.assertEqual(weights["capacidades"], .25)
        criteria = sample_listing(points=[2] + ["Sin datos"] * 6).criteria
        self.assertEqual(calculate_fit(criteria, weights), {"fit": 10, "cobertura": 25})
        criteria[0].points = 0
        self.assertEqual(calculate_fit(criteria, weights)["fit"], 1)
        criteria[0].points = "Sin datos"
        self.assertEqual(calculate_fit(criteria, weights), {"fit": None, "cobertura": 0})

    def test_preferences_change_order_without_exclude(self):
        a = sample_listing(points=[0, 0, 0, 0, 2, 0, 0])
        b = sample_listing(role="Otra", url="https://example.com/2", points=[0, 0, 0, 0, 0, 2, 0])
        data = [a.model_dump(), b.model_dump()]
        weights = normalize_weights({"importancia_ubicacion": "Alta", "importancia_modalidad": "Baja"})
        self.assertEqual(rank_evaluations(data, weights)[0]["oferta"].url, a.url)
        weights = normalize_weights({"importancia_ubicacion": "Baja", "importancia_modalidad": "Alta"})
        self.assertEqual(rank_evaluations(data, weights)[0]["oferta"].url, b.url)
        self.assertEqual(len(rank_evaluations(data, weights)), 2)

    def test_salary_not_comparable_and_evidence_confirmed(self):
        listing = sample_listing()
        profile = migrate_profile({"puesto": "Analista", "capacidades": "Python", "ubicacion": "Madrid"})
        profile.update(salario_minimo=40000, moneda="EUR")
        text = "Empresa ficticia Analista Madrid Analizar datos Python. Salario bruto anual: 50000–60000 EUR."
        retrieved = {listing.url: {"descripcion_recuperada": text}}
        listing.documented_salary = SalaryData(minimum=50000, maximum=60000, currency="EUR",
            period="Anual", kind="Bruto", evidence="Salario bruto anual: 50000–60000 EUR.")
        def validate():
            return validate_recommendations(EvaluationResult(job_listings=[listing], discarded=[]), retrieved,
                                           profile_for_model(profile))[0]
        self.assertEqual(validate().criteria[-1].points, 2)
        profile["moneda"] = "GBP"
        self.assertEqual(validate().criteria[-1].points, "Sin datos")
        profile["moneda"] = "EUR"
        listing.documented_salary.period = "Mensual"
        self.assertEqual(validate().criteria[-1].points, "Sin datos")
        listing.documented_salary.period = "Anual"
        listing.documented_salary.minimum = 70000
        self.assertEqual(validate().criteria[-1].points, "Sin datos")

    def test_aspiration_not_proves_skill(self):
        listing = sample_listing()
        profile = migrate_profile({"puesto": "Analista", "capacidades": "SQL"})
        profile["que_buscas"] = "Python"
        retrieved = {listing.url: {"descripcion_recuperada": "Empresa ficticia Analista Madrid Analizar datos Python"}}
        validated = validate_recommendations(EvaluationResult(job_listings=[listing], discarded=[]), retrieved,
                                          profile_for_model(profile))[0]
        self.assertEqual(validated.criteria[1].points, "Sin datos")


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.file_path = Path(self.temporary.name) / 'user_profile.json'
        self.evaluations = Path(self.temporary.name) / '.local_data' / 'evaluations.json'
        self.profile = {"puesto": "Analista", "ubicacion": "Madrid", "experiencia_profesional": "3 años",
                       "capacidades": "Python", "preferencias_laborales": "Híbrido", "dato_extra": "conservar"}
        save_json(self.file_path, self.profile)
        self.patches = [patch.object(local_storage, "PROFILE_FILE", self.file_path),
                        patch('profile_ui.PROFILE_FILE', self.file_path),
                        patch('profile_improvement.PROFILE_FILE', self.file_path),
                        patch("skills.PROFILE_FILE", self.file_path),
                        patch.object(local_storage, "EVALUATIONS_FILE", self.evaluations),
                        patch('agent.search_listings')]
        for p in self.patches:
            last = p.start()
        self.search = last
        self.search.return_value = {"evaluaciones": [sample_listing().model_dump()], "eventos": [],
                                    "fecha": "2026-10-09T12:00:00Z", "llamadas": 2, "error": False}

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temporary.cleanup()

    def app(self):
        return AppTest.from_file(str(Path(__file__).parent / "app.py"), default_timeout=15).run()

    def button(self, app, label):
        return next(b for b in app.button if b.label == label)

    def test_edit_cancel_save_and_only_trigger(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertFalse(any(b.label == "Guardar perfil" for b in app.button))
        self.search.assert_not_called()
        original = self.file_path.read_bytes()
        self.button(app, "Editar perfil").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="editor_experiencia").value, "1–3 años")
        self.assertTrue(app.selectbox(key="editor_preferencia_modalidad_Remoto").disabled)
        app.text_area(key="editor_que_buscas").set_value("Aprender Rust").run()
        self.button(app, "Cancelar").click().run()
        self.assertEqual(self.file_path.read_bytes(), original)
        self.button(app, "Editar perfil").click().run()
        self.assertEqual(app.text_area(key="editor_que_buscas").value, "")
        app.text_area(key="editor_que_buscas").set_value("Mejorar en análisis").run()
        self.button(app, "Guardar perfil").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(any(b.label == "Guardar perfil" for b in app.button))
        self.search.assert_not_called()
        saved = local_storage.load_profile()
        self.assertEqual(saved["datos_anteriores"]["dato_extra"], "conservar")
        self.button(app, "Editar perfil").click().run()
        self.assertEqual(app.text_area(key="editor_que_buscas").value, "Mejorar en análisis")
        self.button(app, "Cancelar").click().run()
        self.button(app, "Buscar ofertas").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.search.call_count, 1)
        self.assertTrue(self.evaluations.exists())
        self.button(app, "Editar perfil").click().run()
        app.selectbox(key="editor_importancia_ubicacion").select("Alta").run()
        self.button(app, "Guardar perfil").click().run()
        self.assertFalse(any("El perfil ha cambiado" in w.value for w in app.warning))
        self.assertTrue(any(h.value == "Resultado de Busqueda" for h in app.subheader))
        self.assertTrue(any(b.label == "Buscar ofertas" for b in app.button))
        self.assertFalse(any("OpenAI" in c.value or "Tavily" in c.value or "Git" in c.value for c in app.caption))
        self.assertEqual(self.search.call_count, 1)
        self.button(app, "Buscar ofertas").click().run()
        self.assertEqual(self.search.call_count, 2)
        app.session_state.searching = True
        app.run()
        self.assertTrue(self.button(app, "Buscar ofertas").disabled)
        self.assertEqual(self.search.call_count, 2)

    def test_add_limit_remove_duplicates_and_level(self):
        app = self.app()
        self.button(app, "Editar perfil").click().run()
        app.button(key="editor_anadir_puestos_objetivo").click().run()
        self.assertTrue(any("vacía" in e.value for e in app.error))
        app.text_input(key="editor_nuevo_puestos_objetivo").set_value(" ANALISTA ")
        app.button(key="editor_anadir_puestos_objetivo").click().run()
        self.assertTrue(any("ya está" in e.value for e in app.error))
        for n in range(4):
            app.text_input(key="editor_nuevo_puestos_objetivo").set_value(f"Puesto {n}")
            app.button(key="editor_anadir_puestos_objetivo").click().run()
        self.assertTrue(app.button(key="editor_anadir_puestos_objetivo").disabled)
        app.button(key=option_key("puestos_objetivo_eliminar", "Puesto 0")).click().run()
        self.assertFalse(app.button(key="editor_anadir_puestos_objetivo").disabled)
        app.text_input(key="editor_nuevo_idiomas").set_value("Inglés")
        app.button(key="editor_anadir_idiomas").click().run()
        app.selectbox(key=option_key("idiomas_nivel", "Inglés")).select("Alto").run()
        app.checkbox(key="editor_modalidad_Remoto").check().run()
        self.assertFalse(app.selectbox(key="editor_preferencia_modalidad_Remoto").disabled)
        self.search.assert_not_called()
        self.assertFalse(app.exception)

    def test_without_file_profile_ui_empty_and_profile_incomplete_persistent(self):
        self.file_path.unlink()
        app = self.app()
        self.assertFalse(app.exception)
        self.assertFalse(self.file_path.exists())
        for field in ("puestos_objetivo", "ubicaciones", "skills", "idiomas"):
            self.assertEqual(app.text_input(key="editor_nuevo_" + field).value, "")
        self.assertEqual(app.text_area(key="editor_que_buscas").value, "")
        self.assertIsNone(app.selectbox(key="editor_experiencia").value)
        self.assertIsNone(app.selectbox(key="editor_moneda").value)
        self.assertIsNone(app.number_input(key="editor_salario").value)
        for mode in ("Presencial", "Híbrido", "Remoto"):
            self.assertFalse(app.checkbox(key="editor_modalidad_" + mode).value)
        self.button(app, "Guardar perfil").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(self.button(app, "Buscar ofertas").disabled)
        self.assertFalse(any(b.label == "Guardar perfil" for b in app.button))
        saved = local_storage.load_profile()
        self.assertEqual(saved["puestos_objetivo"], [])
        self.assertEqual(saved["skills"], [])
        self.assertIsNone(saved["salario_minimo"])
        self.assertIsNone(saved["importancia_ubicacion"])
        # Reopening loads the incomplete profile and displays its summary.
        app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(self.button(app, "Buscar ofertas").disabled)
        self.button(app, "Editar perfil").click().run()
        app.text_input(key="editor_nuevo_puestos_objetivo").set_value("Analista")
        app.button(key="editor_anadir_puestos_objetivo").click().run()
        self.button(app, "Guardar perfil").click().run()
        app = self.app()
        self.assertFalse(self.button(app, "Buscar ofertas").disabled)
        self.button(app, "Editar perfil").click().run()
        self.assertEqual(app.session_state.draft["puestos_objetivo"], ["Analista"])
        app.button(key=option_key("puestos_objetivo_eliminar", "Analista")).click().run()
        self.button(app, "Cancelar").click().run()
        app = self.app()
        self.assertEqual(app.session_state.profile["puestos_objetivo"], ["Analista"])
        self.search.assert_not_called()

    def test_cancel_creation_not_saves_and_reopens_empty(self):
        self.file_path.unlink()
        app = self.app()
        app.text_input(key="editor_nuevo_skills").set_value("Python")
        app.button(key="editor_anadir_skills").click().run()
        self.button(app, "Cancelar").click().run()
        self.assertFalse(self.file_path.exists())
        self.button(app, "Crear perfil").click().run()
        self.assertEqual(app.session_state.draft["skills"], [])
        self.search.assert_not_called()

    def test_company_current_saves_and_restores(self):
        app = self.app()
        self.button(app, "Editar perfil").click().run()
        app.text_input(key="editor_empresa_actual").set_value("Empresa ficticia")
        app.checkbox(key="editor_excluir_empresa").check().run()
        self.button(app, "Guardar perfil").click().run()
        app = self.app()
        self.button(app, "Editar perfil").click().run()
        self.assertEqual(app.text_input(key="editor_empresa_actual").value, "Empresa ficticia")
        self.assertTrue(app.checkbox(key="editor_excluir_empresa").value)
        self.search.assert_not_called()

    def test_results_explained_without_scores_or_label_overall(self):
        app = self.app()
        self.button(app, "Buscar ofertas").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        text = "\n".join(m.value for m in app.markdown)
        for section in ("Motivos de interés", "Requisitos que cumple", "Gaps"):
            self.assertIn(section, text)
        for label in ("Fit global", "Encaje profesional", "Fit no calculable", "Información pendiente de confirmar", "No hay preguntas pendientes", "¿Sigue abierta esta vacante?"):
            self.assertNotIn(label, text)
        self.assertEqual(self.search.call_count, 1)


if __name__ == "__main__":
    unittest.main()
