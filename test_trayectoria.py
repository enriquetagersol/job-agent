import copy
import json
import unittest
from unittest.mock import patch

import test_interfaz as fixtures
from cv import borrador_cv, generar_pdf
from datos_locales import contexto_busqueda
from evaluacion import validar_criterios
from perfil import migrar_perfil, perfil_para_modelo, validar_perfil
from presentacion import explicar_oferta
from trayectoria import empresa_para_excluir, validar_entrada
from skills import fuentes_skills, filtrar_propuestas, Propuesta
from mejoras import preguntas_usuario


def entrada(campo, **datos):
    base = {"id": campo, "inicio": {"mes": 1, "ano": 2020}, "fin": {"mes": 6, "ano": 2020}, "actual": False,
            "empresa": "Empresa de prueba", "puesto": "Puesto de prueba", "responsabilidades": "Tareas de prueba",
            "institucion": "Institución de prueba", "estudios": "Curso de prueba", "nombre": "Proyecto de prueba",
            "descripcion": "Descripción de prueba", "contribucion": "Contribución de prueba"}
    base.update(datos)
    return base


class Trayectoria(unittest.TestCase):
    def test_migracion_y_separacion_de_datos(self):
        anterior = {"puesto": "Analista", "experiencia_profesional": "3 años", "empresa_actual": "Anterior"}
        perfil = migrar_perfil(anterior)
        self.assertEqual(perfil["experiencia"], "1–3 años")
        self.assertEqual(perfil["experiencias"], [])
        self.assertEqual(perfil["datos_anteriores"], anterior)
        perfil["datos_cv"]["email"] = "persona@example.test"
        perfil["formacion"] = [entrada("formacion", estudios="Curso", contenidos="Introducción a bases de datos")]
        modelo = perfil_para_modelo(perfil)
        self.assertEqual(modelo["confirmado"]["formacion"], perfil["formacion"])
        self.assertNotIn("datos_cv", modelo["confirmado"])
        self.assertNotIn("persona@example.test", json.dumps(modelo))

    def test_fechas_opcionales_y_orden(self):
        with self.assertRaises(ValueError):
            validar_entrada("experiencias", {"id": "vacia"})
        dato = entrada("experiencias", inicio={"ano": 2025, "mes": 5}, fin={"ano": 2025, "mes": 4})
        with self.assertRaises(ValueError):
            validar_entrada("experiencias", dato)
        dato["actual"] = True
        validar_entrada("experiencias", dato)
        dato["actual"] = False
        dato["fin"] = {"ano": 2024, "mes": None}
        with self.assertRaises(ValueError):
            validar_entrada("experiencias", dato)

    def test_empresa_actual_y_eleccion(self):
        perfil = migrar_perfil({"empresa_actual": "Anterior"})
        self.assertEqual(empresa_para_excluir(perfil), "Anterior")
        perfil["experiencias"] = [entrada("a", empresa="A", actual=True), entrada("b", empresa="B", actual=True)]
        perfil["experiencia_excluida_id"] = "b"
        perfil["excluir_empresa_actual"] = True
        self.assertEqual(contexto_busqueda(perfil)["empresa_excluida"], "B")
        perfil["experiencias"].pop()
        self.assertEqual(empresa_para_excluir(perfil), "A")
        perfil["experiencias"][0]["actual"] = False
        self.assertEqual(empresa_para_excluir(perfil), "")

    def test_curso_no_equivale_a_dominio_ni_trabajo(self):
        perfil = migrar_perfil({})
        contenido = "Realicé ejercicios introductorios con Python y bases de datos"
        perfil["formacion"] = [entrada("curso", estudios="Python avanzado", contenidos=contenido)]
        oferta = fixtures.oferta_ficticia()
        capacidades = oferta.criterios[1]
        capacidades.puntos = 2
        capacidades.evidencias_perfil = [contenido]
        capacidades.evidencias_oferta = ["Python"]
        oferta.criterios[2].evidencias_perfil = [contenido]
        validar_criterios(oferta, perfil_para_modelo(perfil), "Analista Empresa ficticia Madrid Analizar datos Python")
        self.assertEqual(capacidades.puntos, 1)
        self.assertEqual(oferta.criterios[2].puntos, "Sin datos")
        capacidades.puntos = 2
        capacidades.evidencias_perfil = ["Python avanzado"]
        capacidades.evidencia_perfil = "Python avanzado"
        validar_criterios(oferta, perfil_para_modelo(perfil), "Python")
        self.assertEqual(capacidades.puntos, "Sin datos")

    def test_interes_no_depende_de_compatibilidad_secundaria(self):
        oferta = fixtures.oferta_ficticia()
        criterio = oferta.criterios[0]
        criterio.compatibilidad = "Sin datos"
        criterio.motivo = "Las funciones de análisis coinciden con tus puestos objetivo."
        resultado = explicar_oferta(oferta)
        self.assertIn(criterio.motivo, resultado["interes"])
        self.assertNotIn(criterio.motivo, resultado["cumplidos"])

    def test_propuestas_fuente_validada_sin_titulos(self):
        perfil = migrar_perfil({})
        perfil["formacion"] = [entrada("f", estudios="Experto en Python", contenidos="Práctica introductoria de SQL")]
        fuentes = fuentes_skills(perfil)
        self.assertNotIn("Python", json.dumps(fuentes))
        propuestas = [Propuesta(skill="SQL", campo="formacion", entrada_id="f", cita="Práctica introductoria de SQL"),
                      Propuesta(skill="Python", campo="formacion", entrada_id="f", cita="Experto en Python")]
        self.assertEqual([p["skill"] for p in filtrar_propuestas(propuestas, fuentes, [])], ["SQL"])

    def test_cv_literal_sin_preferencias_ni_campos_vacios(self):
        perfil = migrar_perfil({})
        perfil["datos_cv"]["nombre"] = "Persona de prueba"
        perfil["datos_cv"]["apellidos"] = "Apellido de prueba"
        perfil["datos_cv"]["email"] = "prueba@example.test"
        perfil["salario_minimo"] = 98765
        perfil["que_buscas"] = "Una aspiración que no es experiencia"
        perfil["puestos_objetivo"] = ["Puesto deseado"]
        perfil["formacion"] = [entrada("f", institucion="Institución", estudios="Curso", contenidos="Introducción a SQL")]
        perfil["proyectos"] = [entrada("p", nombre="Proyecto", contribucion="Mi contribución exacta", herramientas="SQL")]
        antes = copy.deepcopy(perfil)
        texto = borrador_cv(perfil)
        for omitido in ("98765", "aspiración", "Puesto deseado", "No especificado", "Entrada sin completar"):
            self.assertNotIn(omitido, texto)
        self.assertIn("Mi contribución exacta", texto)
        self.assertIn("FORMACIÓN", texto)
        self.assertIn("PROYECTOS", texto)
        self.assertEqual(texto.count("Proyecto\n"), 1)
        self.assertEqual(perfil, antes)
        self.assertTrue(generar_pdf(perfil).startswith(b"%PDF"))
        self.assertEqual(perfil, antes)
        self.assertEqual(borrador_cv(migrar_perfil({})), "")

    def test_no_preguntar_aplicacion_ya_documentada(self):
        perfil = migrar_perfil({})
        perfil["proyectos"] = [entrada("p", nombre="Ejercicio", herramientas="Python", contribucion="Escribí el script de limpieza de datos")]
        oferta = fixtures.oferta_ficticia()
        oferta.criterios[1].skills_declaradas = ["Python"]
        preguntas = dict(preguntas_usuario([oferta], perfil))
        self.assertNotIn("skill:python", preguntas)


class EdicionTrayectoria(unittest.TestCase):
    setUp = fixtures.PruebasInterfaz.setUp
    tearDown = fixtures.PruebasInterfaz.tearDown
    app = fixtures.PruebasInterfaz.app
    boton = fixtures.PruebasInterfaz.boton

    def test_fecha_invalida_y_editar_skill_con_origen(self):
        app = self.app()
        self.boton(app, "Editar perfil").click().run()
        self.boton(app, "Añadir estudios").click().run()
        app.text_input(key="editor_entrada_institucion").set_value("Institución de prueba").run()
        app.text_input(key="editor_entrada_estudios").set_value("Curso de prueba").run()
        app.selectbox(key="editor_entrada_inicio_mes").select("Marzo").run()
        app.selectbox(key="editor_entrada_fin_mes").select("Marzo").run()
        app.number_input(key="editor_entrada_inicio_ano").set_value(2025).run()
        app.number_input(key="editor_entrada_fin_ano").set_value(2024).run()
        self.boton(app, "Guardar entrada").click().run()
        self.assertTrue(any("anterior" in e.value for e in app.error))
        self.boton(app, "Cancelar entrada").click().run()
        app.button(key=fixtures.clave_opcion("skills_editar", "Python")).click().run()
        app.text_input(key="editor_nombre_skills").set_value("SQL").run()
        app.button(key="editor_aplicar_skills").click().run()
        self.boton(app, "Guardar perfil").click().run()
        perfil = json.loads(self.archivo.read_text())
        self.assertEqual(perfil["skills"], ["SQL"])
        self.assertTrue(perfil["origen_skills"]["SQL"]["editada_por_usuario"])
        self.buscar.assert_not_called()

    def test_propuesta_solo_botones_y_confirmacion(self):
        perfil = migrar_perfil(self.perfil)
        perfil["formacion"] = [entrada("f", contenidos="Ejercicios introductorios de SQL")]
        fixtures.guardar_json(self.archivo, perfil)
        propuesta = {"skill": "SQL", "campo": "formacion", "entrada_id": "f", "cita": "Ejercicios introductorios de SQL"}
        with patch("skills.proponer_skills", return_value=[propuesta]) as proponer:
            app = self.app()
            proponer.assert_not_called()
            original = self.archivo.read_bytes()
            self.boton(app, "Proponer skills").click().run()
            proponer.assert_called_once()
            self.assertEqual(json.loads(self.archivo.read_text())["skills"], perfil["skills"])
            self.boton(app, "Añadir").click().run()
        nuevo = json.loads(self.archivo.read_text())
        self.assertIn("SQL", nuevo["skills"])
        self.assertEqual(nuevo["origen_skills"]["SQL"]["tipo"], "Formación")
        self.buscar.assert_not_called()

    def test_entradas_guardado_cancelacion_edicion_y_eliminacion(self):
        app = self.app()
        original = self.archivo.read_bytes()
        self.boton(app, "Editar perfil").click().run()
        self.boton(app, "Añadir experiencia").click().run()
        app.text_input(key="editor_entrada_empresa").set_value("Empresa de prueba").run()
        app.text_input(key="editor_entrada_puesto").set_value("Analista").run()
        app.text_area(key="editor_entrada_responsabilidades").set_value("Análisis de datos").run()
        app.number_input(key="editor_entrada_inicio_ano").set_value(2024).run()
        app.selectbox(key="editor_entrada_inicio_mes").select("Marzo").run()
        app.checkbox(key="editor_entrada_actual").check().run()
        self.assertTrue(app.number_input(key="editor_entrada_fin_ano").disabled)
        self.boton(app, "Guardar entrada").click().run()
        self.assertEqual(self.archivo.read_bytes(), original)
        self.boton(app, "Guardar perfil").click().run()
        self.assertFalse(app.exception)
        perfil = json.loads(self.archivo.read_text())
        self.assertEqual(perfil["experiencias"][0]["empresa"], "Empresa de prueba")
        identificador = perfil["experiencias"][0]["id"]
        app = self.app()
        self.boton(app, "Editar perfil").click().run()
        app.button(key="editor_editar_" + identificador).click().run()
        self.assertEqual(app.text_input(key="editor_entrada_empresa").value, "Empresa de prueba")
        app.text_input(key="editor_entrada_empresa").set_value("Cambio cancelado").run()
        self.boton(app, "Cancelar entrada").click().run()
        self.boton(app, "Cancelar").click().run()
        self.assertEqual(json.loads(self.archivo.read_text()), perfil)
        self.boton(app, "Editar perfil").click().run()
        app.button(key="editor_eliminar_" + identificador).click().run()
        self.boton(app, "Guardar perfil").click().run()
        self.assertEqual(json.loads(self.archivo.read_text())["experiencias"], [])
        self.buscar.assert_not_called()

    def test_formacion_proyecto_y_cv_no_modifican_perfil(self):
        app = self.app()
        self.boton(app, "Editar perfil").click().run()
        for boton, clave, valor in (("Añadir estudios", "estudios", "Curso de prueba"), ("Añadir proyecto", "nombre", "Proyecto de prueba")):
            self.boton(app, boton).click().run()
            app.text_input(key="editor_entrada_" + clave).set_value(valor).run()
            if clave == "estudios":
                app.text_input(key="editor_entrada_institucion").set_value("Institución de prueba").run()
                app.selectbox(key="editor_entrada_inicio_mes").select("Marzo").run()
                app.number_input(key="editor_entrada_inicio_ano").set_value(2024).run()
                app.checkbox(key="editor_entrada_actual").check().run()
            else:
                app.text_area(key="editor_entrada_descripcion").set_value("Descripción de prueba").run()
                app.text_area(key="editor_entrada_contribucion").set_value("Contribución de prueba").run()
            self.boton(app, "Guardar entrada").click().run()
        self.boton(app, "Guardar perfil").click().run()
        for campo, valor in (("nombre", "Persona"), ("apellidos", "Prueba"), ("email", "prueba@example.test")):
            app.button(key="resumen_editar_cv:" + campo).click().run()
            app.text_input(key="editor_cv_" + campo).set_value(valor).run()
            self.boton(app, "Guardar").click().run()
        original = self.archivo.read_bytes()
        self.boton(app, "Generar CV base").click().run()
        self.assertFalse(any(t.key == "cv_texto" for t in app.text_area))
        self.assertTrue(app.session_state.cv_pdf.startswith(b"%PDF"))
        self.assertFalse(app.exception)
        self.assertEqual(self.archivo.read_bytes(), original)
        self.buscar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
