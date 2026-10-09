import copy
import json
import unittest
from unittest.mock import patch

import test_interface as fixtures
from test_career_history import entry
from user_profile import migrate_profile
from skills import SkillSuggestion, filter_suggestions, skill_sources
from skill_store import remove_skill, record_rejection, possible_equivalence, add_source


class SkillStoreTests(unittest.TestCase):
    def setUp(self):
        self.profile = migrate_profile({})
        self.profile["formacion"] = [{"id": "f", "contenidos": "Ejercicios de SQL y Python"}]
        self.suggestion = SkillSuggestion(skill="SQL", field="formacion", entry_id="f", quote="SQL")

    def test_duplicates_and_rejection_same_source(self):
        duplicate = self.suggestion.model_copy(update={'skill': " sql  "})
        sources = skill_sources(self.profile)
        self.assertEqual(len(filter_suggestions([self.suggestion, duplicate], sources, [])), 1)
        record_rejection(self.profile, "SQL", self.suggestion.model_dump())
        new_quote = self.suggestion.model_copy(update={'quote': "Ejercicios de SQL"})
        self.assertEqual(filter_suggestions([new_quote], sources, [], self.profile["skills_rechazadas"]), [])
        self.profile["formacion"][0]["contenidos"] += "; creé un informe nuevo"
        new_value = self.suggestion.model_copy(update={'quote': "informe nuevo"})
        self.assertEqual(len(filter_suggestions([new_value], skill_sources(self.profile), [], self.profile["skills_rechazadas"])), 1)

    def test_remove_manual_also_blocks_evidence_existing(self):
        self.profile["skills"] = ["SQL"]
        self.profile["origen_skills"]["SQL"] = {"tipo": "Manual"}
        remove_skill(self.profile, "SQL")
        self.assertEqual(self.profile["skills"], [])
        self.assertIn("SQL", self.profile["archivo_fuentes_skills"])
        self.assertEqual(filter_suggestions([self.suggestion], skill_sources(self.profile), [], self.profile["skills_rechazadas"]), [])

    def test_equivalences_only_suggestions_and_sources_unique(self):
        self.assertEqual(possible_equivalence("Project Management", ["Gestión de proyectos"]), "Gestión de proyectos")
        self.assertIsNone(possible_equivalence("Python", ["Java"]))
        source = {"campo": "formacion", "entrada_id": "f", "cita": "SQL", "tipo": "Formación"}
        add_source(self.profile, "SQL", source)
        add_source(self.profile, "SQL", source)
        self.assertEqual(len(self.profile["origen_skills"]["SQL"]["fuentes"]), 1)


class IndependentEditorTests(unittest.TestCase):
    setUp = fixtures.InterfaceTests.setUp
    tearDown = fixtures.InterfaceTests.tearDown
    app = fixtures.InterfaceTests.app
    button = fixtures.InterfaceTests.button

    def test_saving_independent_cancellation_and_data_latest(self):
        profile = migrate_profile(self.profile)
        fixtures.save_json(self.file_path, profile)
        app = self.app()
        app.button(key="resumen_editar_que_buscas").click().run()
        self.assertFalse(any(i.key == "editor_salario" for i in app.number_input))
        app.text_area(key="editor_que_buscas").set_value("Objetivo nuevo").run()
        latest = copy.deepcopy(profile)
        latest["salario_minimo"] = 50000
        fixtures.save_json(self.file_path, latest)
        self.button(app, "Guardar").click().run()
        saved = json.loads(self.file_path.read_text())
        self.assertEqual(saved["salario_minimo"], 50000)
        self.assertEqual(saved["que_buscas"], "Objetivo nuevo")
        app.button(key="resumen_editar_que_buscas").click().run()
        app.text_area(key="editor_que_buscas").set_value("Cambio cancelado").run()
        self.button(app, "Cancelar").click().run()
        self.assertEqual(json.loads(self.file_path.read_text()), saved)
        self.search.assert_not_called()

    def test_remove_and_cancel_list_not_changes_other_field(self):
        app = self.app()
        before = self.file_path.read_bytes()
        app.button(key="resumen_editar_skills").click().run()
        app.button(key=fixtures.option_key("skills_eliminar", "Python")).click().run()
        self.button(app, "Cancelar").click().run()
        self.assertEqual(self.file_path.read_bytes(), before)
        app.button(key=fixtures.option_key("resumen_skill_eliminar", "Python")).click().run()
        saved = json.loads(self.file_path.read_text())
        self.assertEqual(saved["skills"], [])
        self.assertEqual(saved["puestos_objetivo"], ["Analista"])
        app = self.app()
        self.assertFalse(any(b.key == fixtures.option_key("resumen_skill_eliminar", "Python") for b in app.button))
        self.search.assert_not_called()

    def test_discard_persist_and_not_consume_slots(self):
        profile = migrate_profile(self.profile)
        profile["formacion"] = [entry("f", contenidos="Ejercicios SQL")]
        fixtures.save_json(self.file_path, profile)
        suggestion = {"skill": "SQL", "campo": "formacion", "entrada_id": "f", "cita": "SQL"}
        with patch("skills.suggest_skills", return_value=[suggestion]):
            app = self.app()
            self.button(app, "Proponer skills").click().run()
        self.assertEqual(json.loads(self.file_path.read_text())["skills"], ["Python"])
        app = self.app()
        self.assertTrue(any(b.key == "skill_confirmar_formacionfsql" for b in app.button))
        self.button(app, "Descartar").click().run()
        app = self.app()
        self.assertFalse(any(b.key == "skill_confirmar_formacionfsql" for b in app.button))
        saved = json.loads(self.file_path.read_text())
        self.assertEqual(filter_suggestions([SkillSuggestion(**suggestion)], skill_sources(saved), saved["skills"], saved["skills_rechazadas"]), [])

    def test_limit_and_merge_confirmed_without_slot(self):
        profile = migrate_profile(self.profile)
        profile["skills"] = ["Gestión de proyectos"] + [f"Skill {i}" for i in range(9)]
        profile["formacion"] = [entry("f", contenidos="Coordinación de proyectos SQL")]
        profile["skills_propuestas"] = [
            {"skill": "SQL", "campo": "formacion", "entrada_id": "f", "cita": "SQL"},
            {"skill": "Project Management", "campo": "formacion", "entrada_id": "f", "cita": "Coordinación de proyectos"}]
        fixtures.save_json(self.file_path, profile)
        app = self.app()
        self.assertTrue(app.button(key="skill_confirmar_formacionfsql").disabled)
        self.assertEqual(len(json.loads(self.file_path.read_text())["skills"]), 10)
        app.checkbox(key="skill_fusionar_formacionfproject management").check().run()
        self.assertFalse(app.button(key="skill_confirmar_formacionfproject management").disabled)
        app.button(key="skill_confirmar_formacionfproject management").click().run()
        data = json.loads(self.file_path.read_text())
        self.assertEqual(len(data["skills"]), 10)
        self.assertNotIn("Project Management", data["skills"])
        self.assertTrue(data["origen_skills"]["Gestión de proyectos"]["fuentes"])

    def test_edit_entry_saves_only_that_entry(self):
        profile = migrate_profile(self.profile)
        profile["proyectos"] = [{"id": "p", "nombre": "Original", "descripcion": "Descripción"}]
        fixtures.save_json(self.file_path, profile)
        app = self.app()
        app.button(key="resumen_entrada_p").click().run()
        app.text_input(key="editor_entrada_nombre").set_value("Editado").run()
        self.assertFalse(any(b.key == "editor_anadir_formacion" for b in app.button))
        self.button(app, "Guardar").click().run()
        data = json.loads(self.file_path.read_text())
        self.assertEqual(data["proyectos"][0]["nombre"], "Editado")
        self.assertEqual(data["skills"], profile["skills"])
        self.search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
