import copy
import json
import unittest
from unittest.mock import patch

import test_interfaz as fixtures
from test_trayectoria import entrada
from datos_locales import contexto_busqueda, guardar_json
from perfil import migrar_perfil
from trayectoria import validar_entrada
from validaciones import informacion_busqueda, faltantes_cv
from cv import generar_pdf
from agente import buscar_ofertas, reevaluar_ofertas


class Reglas(unittest.TestCase):
    def test_obligatorios_y_espacios(self):
        dato = entrada("e", empresa="   ", responsabilidades=" ")
        with self.assertRaisesRegex(ValueError, "Empresa.*responsabilidades"):
            validar_entrada("experiencias", dato)
        dato = entrada("f", institucion=" ", estudios="")
        with self.assertRaisesRegex(ValueError, "Institución.*Estudios"):
            validar_entrada("formacion", dato)

    def test_fechas_actual_y_completas(self):
        dato = entrada("e", fin={})
        with self.assertRaisesRegex(ValueError, "Fecha de fin"):
            validar_entrada("experiencias", dato)
        dato["actual"] = True
        validar_entrada("experiencias", dato)
        dato["inicio"] = {"ano": 2020}
        with self.assertRaisesRegex(ValueError, "inicio.*mes"):
            validar_entrada("experiencias", dato)

    def test_busqueda_parcial_sin_puesto_y_sin_contactos(self):
        perfil = migrar_perfil({})
        perfil["datos_cv"] = {"nombre": "Persona", "apellidos": "Prueba", "email": "p@example.test"}
        perfil["importancia_ubicacion"] = "Media"
        perfil["moneda"] = "EUR"
        self.assertFalse(informacion_busqueda(contexto_busqueda(perfil)["perfil"]))
        perfil["skills"] = ["Python"]
        self.assertTrue(informacion_busqueda(contexto_busqueda(perfil)["perfil"]))
        perfil["skills"] = []
        perfil["que_buscas"] = "Quiero trabajar en proyectos de análisis"
        self.assertTrue(informacion_busqueda(contexto_busqueda(perfil)["perfil"]))

    def test_acciones_directas_bloqueadas_antes_de_servicios(self):
        perfil = migrar_perfil({})
        with patch("agente.OpenAI") as modelo, patch("agente.load_dotenv") as env:
            with self.assertRaisesRegex(ValueError, "No hay suficiente información"):
                buscar_ofertas(contexto_busqueda(perfil))
            with self.assertRaises(ValueError):
                reevaluar_ofertas(contexto_busqueda(perfil), {})
            modelo.assert_not_called()
            env.assert_not_called()
        with self.assertRaisesRegex(ValueError, "Nombre.*Apellidos.*Email"):
            generar_pdf(perfil)

    def test_cv_completo_por_proyecto_email_y_contactos_opcionales(self):
        perfil = migrar_perfil({})
        perfil["datos_cv"] = {"nombre": "Persona", "apellidos": "Prueba", "email": "p@example.test"}
        perfil["proyectos"] = [entrada("p", nombre="Proyecto", descripcion="Descripción", contribucion="Mi tarea")]
        self.assertEqual(faltantes_cv(perfil), [])
        self.assertTrue(generar_pdf(perfil).startswith(b"%PDF"))
        perfil["datos_cv"]["email"] = "correo incorrecto"
        self.assertIn("Email con formato válido", faltantes_cv(perfil))
        perfil["datos_cv"]["email"] = "p@example.test"
        perfil["proyectos"][0]["contribucion"] = " "
        self.assertTrue(any("Contribución personal" in f for f in faltantes_cv(perfil)))


class InterfazValidada(unittest.TestCase):
    setUp = fixtures.PruebasInterfaz.setUp
    tearDown = fixtures.PruebasInterfaz.tearDown
    app = fixtures.PruebasInterfaz.app
    boton = fixtures.PruebasInterfaz.boton

    def test_guardado_directo_rechaza_nuevas_incompletas(self):
        antes = self.archivo.read_bytes()
        perfil = migrar_perfil(self.perfil)
        perfil["experiencias"] = [{"id": "e", "empresa": "Empresa"}]
        with self.assertRaisesRegex(ValueError, "Puesto"):
            guardar_json(self.archivo, perfil)
        self.assertEqual(self.archivo.read_bytes(), antes)

    def test_antigua_pendiente_se_conserva_y_no_puede_guardarse_incompleta(self):
        perfil = migrar_perfil(self.perfil)
        perfil["experiencias"] = [{"id": "antigua", "empresa": "Empresa anterior"}]
        # Simula un archivo creado con la versión anterior.
        self.archivo.write_text(json.dumps(perfil))
        app = self.app()
        self.assertTrue(any("Pendiente de completar" in c.value for c in app.caption))
        app.button(key="resumen_editar_que_buscas").click().run()
        app.text_area(key="editor_que_buscas").set_value("Análisis de datos").run()
        self.boton(app, "Guardar").click().run()
        guardado = json.loads(self.archivo.read_text())
        self.assertEqual(guardado["experiencias"], perfil["experiencias"])
        app.button(key="resumen_entrada_antigua").click().run()
        app.text_input(key="editor_entrada_empresa").set_value("Nombre cambiado").run()
        self.boton(app, "Guardar").click().run()
        self.assertTrue(any("Puesto" in e.value and "Fecha de inicio" in e.value for e in app.error))
        self.assertEqual(app.text_input(key="editor_entrada_empresa").value, "Nombre cambiado")
        self.assertEqual(json.loads(self.archivo.read_text()), guardado)
        self.buscar.assert_not_called()

    def test_busqueda_y_cv_son_independientes_y_se_actualizan(self):
        perfil = migrar_perfil({})
        guardar_json(self.archivo, perfil)
        app = self.app()
        self.assertTrue(self.boton(app, "Buscar ofertas").disabled)
        self.assertTrue(self.boton(app, "Generar CV base").disabled)
        app.button(key="resumen_editar_skills").click().run()
        app.text_input(key="editor_nuevo_skills").set_value("SQL")
        app.button(key="editor_anadir_skills").click().run()
        self.boton(app, "Guardar").click().run()
        self.assertFalse(self.boton(app, "Buscar ofertas").disabled)
        self.assertTrue(self.boton(app, "Generar CV base").disabled)
        self.boton(app, "Buscar ofertas").click().run()
        self.buscar.assert_called_once()
        app.button(key=fixtures.clave_opcion("resumen_skill_eliminar", "SQL")).click().run()
        self.assertTrue(self.boton(app, "Buscar ofertas").disabled)

    def test_eliminar_unica_entrada_bloquea_cv_y_quita_pdf_anterior(self):
        perfil = migrar_perfil({})
        perfil["datos_cv"] = {"nombre": "Persona", "apellidos": "Prueba", "email": "p@example.test"}
        perfil["proyectos"] = [entrada("p")]
        guardar_json(self.archivo, perfil)
        app = self.app()
        self.assertFalse(self.boton(app, "Generar CV base").disabled)
        self.boton(app, "Generar CV base").click().run()
        self.assertIn("cv_pdf", app.session_state)
        app.button(key="resumen_eliminar_p").click().run()
        self.assertTrue(self.boton(app, "Generar CV base").disabled)
        self.assertNotIn("cv_pdf", app.session_state)
        self.assertTrue(self.boton(app, "Buscar ofertas").disabled)


if __name__ == "__main__":
    unittest.main()
