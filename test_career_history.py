import copy
import json
import unittest
from unittest.mock import patch

import test_interface as fixtures
from cv import compose_cv_text, generate_pdf
from local_storage import search_context
from evaluation import validate_criteria
from user_profile import migrate_profile, profile_for_model, validate_profile
from presentation import explain_listing
from career_history import employer_to_exclude, validate_entry
from skills import skill_sources, filter_suggestions, SkillSuggestion
from profile_improvement import user_questions


def entry(field, **data):
    base = {"id": field, "inicio": {"mes": 1, "ano": 2020}, "fin": {"mes": 6, "ano": 2020}, "actual": False,
            "empresa": "Empresa de prueba", "puesto": "Puesto de prueba", "responsabilidades": "Tareas de prueba",
            "institucion": "Institución de prueba", "estudios": "Curso de prueba", "nombre": "Proyecto de prueba",
            "descripcion": "Descripción de prueba", "contribucion": "Contribución de prueba"}
    aliases = {'name': 'nombre', 'description': 'descripcion', 'role': 'puesto', 'company': 'empresa', 'current': 'actual', 'start_date': 'inicio', 'end_date': 'fin', 'tools': 'herramientas'}
    base.update({aliases.get(key, key): value for key, value in data.items()})
    return base


class CareerHistoryTests(unittest.TestCase):
    def test_migration_and_separation_of_data(self):
        previous = {"puesto": "Analista", "experiencia_profesional": "3 años", "empresa_actual": "Anterior"}
        profile = migrate_profile(previous)
        self.assertEqual(profile["experiencia"], "1–3 años")
        self.assertEqual(profile["experiencias"], [])
        self.assertEqual(profile["datos_anteriores"], previous)
        profile["datos_cv"]["email"] = "persona@example.test"
        profile["formacion"] = [entry("formacion", estudios="Curso", contenidos="Introducción a bases de datos")]
        model = profile_for_model(profile)
        self.assertEqual(model["confirmado"]["formacion"], profile["formacion"])
        self.assertNotIn("datos_cv", model["confirmado"])
        self.assertNotIn("persona@example.test", json.dumps(model))

    def test_dates_optional_and_order(self):
        with self.assertRaises(ValueError):
            validate_entry("experiencias", {"id": "vacia"})
        record = entry("experiencias", start_date={"ano": 2025, "mes": 5}, end_date={"ano": 2025, "mes": 4})
        with self.assertRaises(ValueError):
            validate_entry("experiencias", record)
        record["actual"] = True
        validate_entry("experiencias", record)
        record["actual"] = False
        record["fin"] = {"ano": 2024, "mes": None}
        with self.assertRaises(ValueError):
            validate_entry("experiencias", record)

    def test_company_current_and_selection(self):
        profile = migrate_profile({"empresa_actual": "Anterior"})
        self.assertEqual(employer_to_exclude(profile), "Anterior")
        profile["experiencias"] = [entry("a", company="A", current=True), entry("b", company="B", current=True)]
        profile["experiencia_excluida_id"] = "b"
        profile["excluir_empresa_actual"] = True
        self.assertEqual(search_context(profile)["empresa_excluida"], "B")
        profile["experiencias"].pop()
        self.assertEqual(employer_to_exclude(profile), "A")
        profile["experiencias"][0]["actual"] = False
        self.assertEqual(employer_to_exclude(profile), "")

    def test_course_not_equals_a_proficiency_or_work(self):
        profile = migrate_profile({})
        content = "Realicé ejercicios introductorios con Python y bases de datos"
        profile["formacion"] = [entry("curso", estudios="Python avanzado", contenidos=content)]
        listing = fixtures.sample_listing()
        capabilities = listing.criteria[1]
        capabilities.points = 2
        capabilities.profile_evidence_quotes = [content]
        capabilities.listing_evidence_quotes = ["Python"]
        listing.criteria[2].profile_evidence_quotes = [content]
        validate_criteria(listing, profile_for_model(profile), "Analista Empresa ficticia Madrid Analizar datos Python")
        self.assertEqual(capabilities.points, 1)
        self.assertEqual(listing.criteria[2].points, "Sin datos")
        capabilities.points = 2
        capabilities.profile_evidence_quotes = ["Python avanzado"]
        capabilities.profile_evidence = "Python avanzado"
        validate_criteria(listing, profile_for_model(profile), "Python")
        self.assertEqual(capabilities.points, "Sin datos")

    def test_interest_not_depends_of_compatibility_secondary(self):
        listing = fixtures.sample_listing()
        criterion = listing.criteria[0]
        criterion.compatibility = "Sin datos"
        criterion.reason = "Las funciones de análisis coinciden con tus puestos objetivo."
        result = explain_listing(listing)
        self.assertIn(criterion.reason, result["interes"])
        self.assertNotIn(criterion.reason, result["cumplidos"])

    def test_suggestions_source_validated_without_titles(self):
        profile = migrate_profile({})
        profile["formacion"] = [entry("f", estudios="Experto en Python", contenidos="Práctica introductoria de SQL")]
        sources = skill_sources(profile)
        self.assertNotIn("Python", json.dumps(sources))
        suggestions = [SkillSuggestion(skill="SQL", field="formacion", entry_id="f", quote="Práctica introductoria de SQL"),
                      SkillSuggestion(skill="Python", field="formacion", entry_id="f", quote="Experto en Python")]
        self.assertEqual([p["skill"] for p in filter_suggestions(suggestions, sources, [])], ["SQL"])

    def test_cv_literal_without_preferences_or_fields_empty(self):
        profile = migrate_profile({})
        profile["datos_cv"]["nombre"] = "Persona de prueba"
        profile["datos_cv"]["apellidos"] = "Apellido de prueba"
        profile["datos_cv"]["email"] = "prueba@example.test"
        profile["salario_minimo"] = 98765
        profile["que_buscas"] = "Una aspiración que no es experiencia"
        profile["puestos_objetivo"] = ["Puesto deseado"]
        profile["formacion"] = [entry("f", institucion="Institución", estudios="Curso", contenidos="Introducción a SQL")]
        profile["proyectos"] = [entry("p", name="Proyecto", contribucion="Mi contribución exacta", tools="SQL")]
        before = copy.deepcopy(profile)
        text = compose_cv_text(profile)
        for omitted in ("98765", "aspiración", "Puesto deseado", "No especificado", "Entrada sin completar"):
            self.assertNotIn(omitted, text)
        self.assertIn("Mi contribución exacta", text)
        self.assertIn("FORMACIÓN", text)
        self.assertIn("PROYECTOS", text)
        self.assertEqual(text.count("Proyecto\n"), 1)
        self.assertEqual(profile, before)
        self.assertTrue(generate_pdf(profile).startswith(b"%PDF"))
        self.assertEqual(profile, before)
        self.assertEqual(compose_cv_text(migrate_profile({})), "")

    def test_not_ask_application_already_documented(self):
        profile = migrate_profile({})
        profile["proyectos"] = [entry("p", name="Ejercicio", tools="Python", contribucion="Escribí el script de limpieza de datos")]
        listing = fixtures.sample_listing()
        listing.criteria[1].declared_skills = ["Python"]
        questions = dict(user_questions([listing], profile))
        self.assertNotIn("skill:python", questions)


class CareerEditingTests(unittest.TestCase):
    setUp = fixtures.InterfaceTests.setUp
    tearDown = fixtures.InterfaceTests.tearDown
    app = fixtures.InterfaceTests.app
    button = fixtures.InterfaceTests.button

    def test_date_invalid_and_edit_skill_with_origin(self):
        app = self.app()
        self.button(app, "Editar perfil").click().run()
        self.button(app, "Añadir estudios").click().run()
        app.text_input(key="editor_entrada_institucion").set_value("Institución de prueba").run()
        app.text_input(key="editor_entrada_estudios").set_value("Curso de prueba").run()
        app.selectbox(key="editor_entrada_inicio_mes").select("Marzo").run()
        app.selectbox(key="editor_entrada_fin_mes").select("Marzo").run()
        app.number_input(key="editor_entrada_inicio_ano").set_value(2025).run()
        app.number_input(key="editor_entrada_fin_ano").set_value(2024).run()
        self.button(app, "Guardar entrada").click().run()
        self.assertTrue(any("anterior" in e.value for e in app.error))
        self.button(app, "Cancelar entrada").click().run()
        app.button(key=fixtures.option_key("skills_editar", "Python")).click().run()
        app.text_input(key="editor_nombre_skills").set_value("SQL").run()
        app.button(key="editor_aplicar_skills").click().run()
        self.button(app, "Guardar perfil").click().run()
        profile = json.loads(self.file_path.read_text())
        self.assertEqual(profile["skills"], ["SQL"])
        self.assertTrue(profile["origen_skills"]["SQL"]["editada_por_usuario"])
        self.search.assert_not_called()

    def test_suggestion_only_buttons_and_confirmation(self):
        profile = migrate_profile(self.profile)
        profile["formacion"] = [entry("f", contenidos="Ejercicios introductorios de SQL")]
        fixtures.save_json(self.file_path, profile)
        suggestion = {"skill": "SQL", "campo": "formacion", "entrada_id": "f", "cita": "Ejercicios introductorios de SQL"}
        with patch("skills.suggest_skills", return_value=[suggestion]) as suggest:
            app = self.app()
            suggest.assert_not_called()
            original = self.file_path.read_bytes()
            self.button(app, "Proponer skills").click().run()
            suggest.assert_called_once()
            self.assertEqual(json.loads(self.file_path.read_text())["skills"], profile["skills"])
            self.button(app, "Añadir").click().run()
        updated = json.loads(self.file_path.read_text())
        self.assertIn("SQL", updated["skills"])
        self.assertEqual(updated["origen_skills"]["SQL"]["tipo"], "Formación")
        self.search.assert_not_called()

    def test_entries_saving_cancellation_editing_and_removal(self):
        app = self.app()
        original = self.file_path.read_bytes()
        self.button(app, "Editar perfil").click().run()
        self.button(app, "Añadir experiencia").click().run()
        app.text_input(key="editor_entrada_empresa").set_value("Empresa de prueba").run()
        app.text_input(key="editor_entrada_puesto").set_value("Analista").run()
        app.text_area(key="editor_entrada_responsabilidades").set_value("Análisis de datos").run()
        app.number_input(key="editor_entrada_inicio_ano").set_value(2024).run()
        app.selectbox(key="editor_entrada_inicio_mes").select("Marzo").run()
        app.checkbox(key="editor_entrada_actual").check().run()
        self.assertTrue(app.number_input(key="editor_entrada_fin_ano").disabled)
        self.button(app, "Guardar entrada").click().run()
        self.assertEqual(self.file_path.read_bytes(), original)
        self.button(app, "Guardar perfil").click().run()
        self.assertFalse(app.exception)
        profile = json.loads(self.file_path.read_text())
        self.assertEqual(profile["experiencias"][0]["empresa"], "Empresa de prueba")
        identifier = profile["experiencias"][0]["id"]
        app = self.app()
        self.button(app, "Editar perfil").click().run()
        app.button(key="editor_editar_" + identifier).click().run()
        self.assertEqual(app.text_input(key="editor_entrada_empresa").value, "Empresa de prueba")
        app.text_input(key="editor_entrada_empresa").set_value("Cambio cancelado").run()
        self.button(app, "Cancelar entrada").click().run()
        self.button(app, "Cancelar").click().run()
        self.assertEqual(json.loads(self.file_path.read_text()), profile)
        self.button(app, "Editar perfil").click().run()
        app.button(key="editor_eliminar_" + identifier).click().run()
        self.button(app, "Guardar perfil").click().run()
        self.assertEqual(json.loads(self.file_path.read_text())["experiencias"], [])
        self.search.assert_not_called()

    def test_education_project_and_cv_not_change_profile(self):
        app = self.app()
        self.button(app, "Editar perfil").click().run()
        for button, key_name, value in (("Añadir estudios", "estudios", "Curso de prueba"), ("Añadir proyecto", "nombre", "Proyecto de prueba")):
            self.button(app, button).click().run()
            app.text_input(key="editor_entrada_" + key_name).set_value(value).run()
            if key_name == "estudios":
                app.text_input(key="editor_entrada_institucion").set_value("Institución de prueba").run()
                app.selectbox(key="editor_entrada_inicio_mes").select("Marzo").run()
                app.number_input(key="editor_entrada_inicio_ano").set_value(2024).run()
                app.checkbox(key="editor_entrada_actual").check().run()
            else:
                app.text_area(key="editor_entrada_descripcion").set_value("Descripción de prueba").run()
                app.text_area(key="editor_entrada_contribucion").set_value("Contribución de prueba").run()
            self.button(app, "Guardar entrada").click().run()
        self.button(app, "Guardar perfil").click().run()
        for field, value in (("nombre", "Persona"), ("apellidos", "Prueba"), ("email", "prueba@example.test")):
            app.button(key="resumen_editar_cv:" + field).click().run()
            app.text_input(key="editor_cv_" + field).set_value(value).run()
            self.button(app, "Guardar").click().run()
        original = self.file_path.read_bytes()
        self.button(app, "Generar CV base").click().run()
        self.assertFalse(any(t.key == "cv_texto" for t in app.text_area))
        self.assertTrue(app.session_state.cv_pdf.startswith(b"%PDF"))
        self.assertFalse(app.exception)
        self.assertEqual(self.file_path.read_bytes(), original)
        self.search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
