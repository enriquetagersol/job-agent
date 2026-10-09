import copy
import json
import unittest
from unittest.mock import patch

import test_interface as fixtures
from test_career_history import entry
from local_storage import search_context, save_json
from user_profile import migrate_profile
from career_history import validate_entry
from validation import has_search_information, missing_cv_fields
from cv import generate_pdf
from agent import search_listings, reevaluate_listings


class ValidationTests(unittest.TestCase):
    def test_required_and_whitespace(self):
        record = entry("e", company="   ", responsabilidades=" ")
        with self.assertRaisesRegex(ValueError, "Empresa.*responsabilidades"):
            validate_entry("experiencias", record)
        record = entry("f", institucion=" ", estudios="")
        with self.assertRaisesRegex(ValueError, "Institución.*Estudios"):
            validate_entry("formacion", record)

    def test_dates_current_and_complete(self):
        record = entry("e", end_date={})
        with self.assertRaisesRegex(ValueError, "Fecha de fin"):
            validate_entry("experiencias", record)
        record["actual"] = True
        validate_entry("experiencias", record)
        record["inicio"] = {"ano": 2020}
        with self.assertRaisesRegex(ValueError, "inicio.*mes"):
            validate_entry("experiencias", record)

    def test_job_search_partial_without_role_and_without_contact(self):
        profile = migrate_profile({})
        profile["datos_cv"] = {"nombre": "Persona", "apellidos": "Prueba", "email": "p@example.test"}
        profile["importancia_ubicacion"] = "Media"
        profile["moneda"] = "EUR"
        self.assertFalse(has_search_information(search_context(profile)["perfil"]))
        profile["skills"] = ["Python"]
        self.assertTrue(has_search_information(search_context(profile)["perfil"]))
        profile["skills"] = []
        profile["que_buscas"] = "Quiero trabajar en proyectos de análisis"
        self.assertTrue(has_search_information(search_context(profile)["perfil"]))

    def test_direct_actions_blocked_before_services(self):
        profile = migrate_profile({})
        with patch('agent.OpenAI') as model, patch('agent.load_dotenv') as env:
            with self.assertRaisesRegex(ValueError, "No hay suficiente información"):
                search_listings(search_context(profile))
            with self.assertRaises(ValueError):
                reevaluate_listings(search_context(profile), {})
            model.assert_not_called()
            env.assert_not_called()
        with self.assertRaisesRegex(ValueError, "Nombre.*Apellidos.*Email"):
            generate_pdf(profile)

    def test_cv_complete_by_project_email_and_contact_optional(self):
        profile = migrate_profile({})
        profile["datos_cv"] = {"nombre": "Persona", "apellidos": "Prueba", "email": "p@example.test"}
        profile["proyectos"] = [entry("p", name="Proyecto", description="Descripción", contribucion="Mi tarea")]
        self.assertEqual(missing_cv_fields(profile), [])
        self.assertTrue(generate_pdf(profile).startswith(b"%PDF"))
        profile["datos_cv"]["email"] = "correo incorrecto"
        self.assertIn("Email con formato válido", missing_cv_fields(profile))
        profile["datos_cv"]["email"] = "p@example.test"
        profile["proyectos"][0]["contribucion"] = " "
        self.assertTrue(any("Contribución personal" in f for f in missing_cv_fields(profile)))


class ValidatedInterfaceTests(unittest.TestCase):
    setUp = fixtures.InterfaceTests.setUp
    tearDown = fixtures.InterfaceTests.tearDown
    app = fixtures.InterfaceTests.app
    button = fixtures.InterfaceTests.button

    def test_saving_direct_rejects_new_incomplete(self):
        before = self.file_path.read_bytes()
        profile = migrate_profile(self.profile)
        profile["experiencias"] = [{"id": "e", "empresa": "Empresa"}]
        with self.assertRaisesRegex(ValueError, "Puesto"):
            save_json(self.file_path, profile)
        self.assertEqual(self.file_path.read_bytes(), before)

    def test_legacy_pending_preserves_and_not_can_be_saved_incomplete(self):
        profile = migrate_profile(self.profile)
        profile["experiencias"] = [{"id": "antigua", "empresa": "Empresa anterior"}]
        # Simulate a file created by the previous version.
        self.file_path.write_text(json.dumps(profile))
        app = self.app()
        self.assertTrue(any("Pendiente de completar" in c.value for c in app.caption))
        app.button(key="resumen_editar_que_buscas").click().run()
        app.text_area(key="editor_que_buscas").set_value("Análisis de datos").run()
        self.button(app, "Guardar").click().run()
        saved = json.loads(self.file_path.read_text())
        self.assertEqual(saved["experiencias"], profile["experiencias"])
        app.button(key="resumen_entrada_antigua").click().run()
        app.text_input(key="editor_entrada_empresa").set_value("Nombre cambiado").run()
        self.button(app, "Guardar").click().run()
        self.assertTrue(any("Puesto" in e.value and "Fecha de inicio" in e.value for e in app.error))
        self.assertEqual(app.text_input(key="editor_entrada_empresa").value, "Nombre cambiado")
        self.assertEqual(json.loads(self.file_path.read_text()), saved)
        self.search.assert_not_called()

    def test_job_search_and_cv_are_independent_and_update(self):
        profile = migrate_profile({})
        save_json(self.file_path, profile)
        app = self.app()
        self.assertTrue(self.button(app, "Buscar ofertas").disabled)
        self.assertTrue(self.button(app, "Generar CV base").disabled)
        app.button(key="resumen_editar_skills").click().run()
        app.text_input(key="editor_nuevo_skills").set_value("SQL")
        app.button(key="editor_anadir_skills").click().run()
        self.button(app, "Guardar").click().run()
        self.assertFalse(self.button(app, "Buscar ofertas").disabled)
        self.assertTrue(self.button(app, "Generar CV base").disabled)
        self.button(app, "Buscar ofertas").click().run()
        self.search.assert_called_once()
        app.button(key=fixtures.option_key("resumen_skill_eliminar", "SQL")).click().run()
        self.assertTrue(self.button(app, "Buscar ofertas").disabled)

    def test_remove_only_entry_blocks_cv_and_clears_pdf_previous(self):
        profile = migrate_profile({})
        profile["datos_cv"] = {"nombre": "Persona", "apellidos": "Prueba", "email": "p@example.test"}
        profile["proyectos"] = [entry("p")]
        save_json(self.file_path, profile)
        app = self.app()
        self.assertFalse(self.button(app, "Generar CV base").disabled)
        self.button(app, "Generar CV base").click().run()
        self.assertIn("cv_pdf", app.session_state)
        app.button(key="resumen_eliminar_p").click().run()
        self.assertTrue(self.button(app, "Generar CV base").disabled)
        self.assertNotIn("cv_pdf", app.session_state)
        self.assertTrue(self.button(app, "Buscar ofertas").disabled)


if __name__ == "__main__":
    unittest.main()
