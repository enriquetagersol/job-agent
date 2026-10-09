import copy
import json
import unittest
from unittest.mock import patch

import test_interfaz as fixtures
from test_trayectoria import entrada
from perfil import migrar_perfil
from skills import Propuesta, filtrar_propuestas, fuentes_skills
from skills_datos import eliminar_skill, registrar_rechazo, posible_equivalencia, agregar_fuente


class SkillsDatos(unittest.TestCase):
    def setUp(self):
        self.perfil = migrar_perfil({})
        self.perfil["formacion"] = [{"id": "f", "contenidos": "Ejercicios de SQL y Python"}]
        self.propuesta = Propuesta(skill="SQL", campo="formacion", entrada_id="f", cita="SQL")

    def test_duplicados_y_rechazo_misma_fuente(self):
        duplicada = self.propuesta.model_copy(update={"skill": " sql  "})
        fuentes = fuentes_skills(self.perfil)
        self.assertEqual(len(filtrar_propuestas([self.propuesta, duplicada], fuentes, [])), 1)
        registrar_rechazo(self.perfil, "SQL", self.propuesta.model_dump())
        nueva_cita = self.propuesta.model_copy(update={"cita": "Ejercicios de SQL"})
        self.assertEqual(filtrar_propuestas([nueva_cita], fuentes, [], self.perfil["skills_rechazadas"]), [])
        self.perfil["formacion"][0]["contenidos"] += "; creé un informe nuevo"
        nueva = self.propuesta.model_copy(update={"cita": "informe nuevo"})
        self.assertEqual(len(filtrar_propuestas([nueva], fuentes_skills(self.perfil), [], self.perfil["skills_rechazadas"])), 1)

    def test_eliminar_manual_tambien_bloquea_evidencia_existente(self):
        self.perfil["skills"] = ["SQL"]
        self.perfil["origen_skills"]["SQL"] = {"tipo": "Manual"}
        eliminar_skill(self.perfil, "SQL")
        self.assertEqual(self.perfil["skills"], [])
        self.assertIn("SQL", self.perfil["archivo_fuentes_skills"])
        self.assertEqual(filtrar_propuestas([self.propuesta], fuentes_skills(self.perfil), [], self.perfil["skills_rechazadas"]), [])

    def test_equivalencias_solo_propuestas_y_fuentes_unicas(self):
        self.assertEqual(posible_equivalencia("Project Management", ["Gestión de proyectos"]), "Gestión de proyectos")
        self.assertIsNone(posible_equivalencia("Python", ["Java"]))
        fuente = {"campo": "formacion", "entrada_id": "f", "cita": "SQL", "tipo": "Formación"}
        agregar_fuente(self.perfil, "SQL", fuente)
        agregar_fuente(self.perfil, "SQL", fuente)
        self.assertEqual(len(self.perfil["origen_skills"]["SQL"]["fuentes"]), 1)


class EditoresIndependientes(unittest.TestCase):
    setUp = fixtures.PruebasInterfaz.setUp
    tearDown = fixtures.PruebasInterfaz.tearDown
    app = fixtures.PruebasInterfaz.app
    boton = fixtures.PruebasInterfaz.boton

    def test_guardado_independiente_cancelacion_y_datos_recientes(self):
        perfil = migrar_perfil(self.perfil)
        fixtures.guardar_json(self.archivo, perfil)
        app = self.app()
        app.button(key="resumen_editar_que_buscas").click().run()
        self.assertFalse(any(i.key == "editor_salario" for i in app.number_input))
        app.text_area(key="editor_que_buscas").set_value("Objetivo nuevo").run()
        reciente = copy.deepcopy(perfil)
        reciente["salario_minimo"] = 50000
        fixtures.guardar_json(self.archivo, reciente)
        self.boton(app, "Guardar").click().run()
        guardado = json.loads(self.archivo.read_text())
        self.assertEqual(guardado["salario_minimo"], 50000)
        self.assertEqual(guardado["que_buscas"], "Objetivo nuevo")
        app.button(key="resumen_editar_que_buscas").click().run()
        app.text_area(key="editor_que_buscas").set_value("Cambio cancelado").run()
        self.boton(app, "Cancelar").click().run()
        self.assertEqual(json.loads(self.archivo.read_text()), guardado)
        self.buscar.assert_not_called()

    def test_eliminar_y_cancelar_lista_no_modifica_otro_campo(self):
        app = self.app()
        antes = self.archivo.read_bytes()
        app.button(key="resumen_editar_skills").click().run()
        app.button(key=fixtures.clave_opcion("skills_eliminar", "Python")).click().run()
        self.boton(app, "Cancelar").click().run()
        self.assertEqual(self.archivo.read_bytes(), antes)
        app.button(key=fixtures.clave_opcion("resumen_skill_eliminar", "Python")).click().run()
        guardado = json.loads(self.archivo.read_text())
        self.assertEqual(guardado["skills"], [])
        self.assertEqual(guardado["puestos_objetivo"], ["Analista"])
        app = self.app()
        self.assertFalse(any(b.key == fixtures.clave_opcion("resumen_skill_eliminar", "Python") for b in app.button))
        self.buscar.assert_not_called()

    def test_descartar_persistir_y_no_consumir_huecos(self):
        perfil = migrar_perfil(self.perfil)
        perfil["formacion"] = [entrada("f", contenidos="Ejercicios SQL")]
        fixtures.guardar_json(self.archivo, perfil)
        propuesta = {"skill": "SQL", "campo": "formacion", "entrada_id": "f", "cita": "SQL"}
        with patch("skills.proponer_skills", return_value=[propuesta]):
            app = self.app()
            self.boton(app, "Proponer skills").click().run()
        self.assertEqual(json.loads(self.archivo.read_text())["skills"], ["Python"])
        app = self.app()
        self.assertTrue(any(b.key == "skill_confirmar_formacionfsql" for b in app.button))
        self.boton(app, "Descartar").click().run()
        app = self.app()
        self.assertFalse(any(b.key == "skill_confirmar_formacionfsql" for b in app.button))
        guardado = json.loads(self.archivo.read_text())
        self.assertEqual(filtrar_propuestas([Propuesta(**propuesta)], fuentes_skills(guardado), guardado["skills"], guardado["skills_rechazadas"]), [])

    def test_limite_y_fusion_confirmada_sin_hueco(self):
        perfil = migrar_perfil(self.perfil)
        perfil["skills"] = ["Gestión de proyectos"] + [f"Skill {i}" for i in range(9)]
        perfil["formacion"] = [entrada("f", contenidos="Coordinación de proyectos SQL")]
        perfil["skills_propuestas"] = [
            {"skill": "SQL", "campo": "formacion", "entrada_id": "f", "cita": "SQL"},
            {"skill": "Project Management", "campo": "formacion", "entrada_id": "f", "cita": "Coordinación de proyectos"}]
        fixtures.guardar_json(self.archivo, perfil)
        app = self.app()
        self.assertTrue(app.button(key="skill_confirmar_formacionfsql").disabled)
        self.assertEqual(len(json.loads(self.archivo.read_text())["skills"]), 10)
        app.checkbox(key="skill_fusionar_formacionfproject management").check().run()
        self.assertFalse(app.button(key="skill_confirmar_formacionfproject management").disabled)
        app.button(key="skill_confirmar_formacionfproject management").click().run()
        datos = json.loads(self.archivo.read_text())
        self.assertEqual(len(datos["skills"]), 10)
        self.assertNotIn("Project Management", datos["skills"])
        self.assertTrue(datos["origen_skills"]["Gestión de proyectos"]["fuentes"])

    def test_editar_entrada_guarda_solo_esa_entrada(self):
        perfil = migrar_perfil(self.perfil)
        perfil["proyectos"] = [{"id": "p", "nombre": "Original", "descripcion": "Descripción"}]
        fixtures.guardar_json(self.archivo, perfil)
        app = self.app()
        app.button(key="resumen_entrada_p").click().run()
        app.text_input(key="editor_entrada_nombre").set_value("Editado").run()
        self.assertFalse(any(b.key == "editor_anadir_formacion" for b in app.button))
        self.boton(app, "Guardar").click().run()
        datos = json.loads(self.archivo.read_text())
        self.assertEqual(datos["proyectos"][0]["nombre"], "Editado")
        self.assertEqual(datos["skills"], perfil["skills"])
        self.buscar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
