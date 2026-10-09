import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import datos_locales
from datos_locales import guardar_json, huella_contexto, contexto_busqueda
from evaluacion import (CRITERIOS, Criterio, DatosSalario, Recomendacion, Resultado,
                        calcular_fit, normalizar_pesos, ordenar_evaluaciones,
                        validar_recomendaciones)
from formulario import clave_opcion
from perfil import anadir_opcion, eliminar_opcion, migrar_perfil, perfil_para_modelo, validar_perfil


def oferta_ficticia(puesto="Analista", enlace="https://example.com/1", puntos=None):
    puntos = puntos or [2, 2, 1, "Sin datos", "Sin datos", "Sin datos", "Sin datos"]
    return Recomendacion(enlace=enlace, puesto=puesto, empresa="Empresa ficticia", ubicacion="Madrid",
        responsabilidad_documentada="Analizar datos", requisito_documentado="Python",
        criterios=[Criterio(nombre=n, puntos=p, motivo="Motivo ficticio", evidencia_oferta="Python",
                   evidencia_perfil="Python", opcion_compatible="", compatibilidad="Compatible")
                   for n, p in zip(CRITERIOS, puntos)],
        salario_documentado=DatosSalario(minimo=None, maximo=None, moneda=None,
            periodo="No documentado", tipo="No documentado", evidencia="No documentado"),
        gaps=["Salario no documentado"])


class PruebasPerfil(unittest.TestCase):
    def test_limites_vacios_duplicados_y_huecos(self):
        for limite in (5, 10):
            opciones = []
            for n in range(limite):
                opciones = anadir_opcion(opciones, f"Opción {n}", limite)
            with self.assertRaises(ValueError):
                anadir_opcion(opciones, "Una más", limite)
            opciones = eliminar_opcion(opciones, "Opción 0")
            opciones = anadir_opcion(opciones, "Nueva", limite)
            self.assertEqual(len(opciones), limite)
        for texto in ("", "  ", "python", " PYTHON "):
            with self.assertRaises(ValueError):
                anadir_opcion(["Python"], texto, 10)
        idiomas = []
        for n in range(25):
            idiomas = anadir_opcion(idiomas, f"Idioma {n}")
        self.assertEqual(len(idiomas), 25)

    def test_migracion_no_inventa_y_conserva_datos(self):
        antiguo = {"puesto": "Analista", "ubicacion": "Madrid", "capacidades": "Python",
                   "experiencia_profesional": "3 años", "preferencias_laborales": "Híbrido",
                   "salario": "3000 EUR mensuales", "dato_extra": "conservar"}
        perfil = migrar_perfil(antiguo)
        self.assertEqual(perfil["puestos_objetivo"], ["Analista"])
        self.assertEqual(perfil["experiencia"], "1–3 años")
        self.assertIsNone(perfil["salario_minimo"])
        self.assertEqual(perfil["idiomas"], [])
        self.assertEqual(perfil["datos_anteriores"], antiguo)
        self.assertEqual(migrar_perfil(perfil), perfil)
        perfil["que_buscas"] = "Quiero aprender Rust"
        enviado = perfil_para_modelo(perfil)
        self.assertNotIn("Rust", str(enviado["confirmado"]))
        self.assertIn("Rust", enviado["preferencias"]["que_buscas"])
        self.assertNotIn("filtros", contexto_busqueda(perfil))
        self.assertNotIn("imprescindibles", contexto_busqueda(perfil))

    def test_salario_y_limite_aspiraciones(self):
        perfil = migrar_perfil({})
        perfil["salario_minimo"] = -1
        with self.assertRaises(ValueError):
            validar_perfil(perfil)
        perfil["salario_minimo"] = None
        perfil["que_buscas"] = "x" * 401
        with self.assertRaises(ValueError):
            validar_perfil(perfil)
        perfil["que_buscas"] = "x" * 400
        self.assertEqual(validar_perfil(perfil), perfil)


class PruebasFit(unittest.TestCase):
    def test_happyrobot_evidencias_listadas_no_confirman_dominio(self):
        from evaluacion import validar_criterios
        from presentacion import explicar_oferta
        import json
        oferta = oferta_ficticia(puesto="Deployment Strategist")
        perfil = {"confirmado": {"skills": ["Python", "LLM"], "experiencia": "Sin especificar"},
                  "preferencias": {"puestos_objetivo": ["Deployment Strategist"], "modalidades": {"Híbrido": "Alta"}}}
        texto = "Deployment Strategist. Comfortable coding Python using LLMs. Hybrid."
        oferta.requisito_documentado = "Comfortable coding Python using LLMs."
        oferta.criterios[0].evidencia_perfil = "Preferencia: «Deployment Strategist»"
        oferta.criterios[0].evidencia_oferta = "Deployment Strategist"
        skill = oferta.criterios[1]
        skill.evidencia_perfil = "Skills confirmadas: «Python», «LLM»"
        skill.evidencia_oferta = oferta.requisito_documentado
        skill.puntos = 2
        modalidad = oferta.criterios[5]
        modalidad.evidencia_perfil = "Preferencia: «Híbrido» (Alta)"
        modalidad.evidencia_oferta = "Hybrid"
        modalidad.opcion_compatible = "Hybrid"
        modalidad.puntos = "Sin datos"
        validar_criterios(oferta, perfil, texto)
        self.assertEqual(skill.puntos, 1)
        self.assertEqual(skill.skills_declaradas, ["Python", "LLM"])
        self.assertEqual(json.loads(skill.evaluacion_original_json)["puntos"], 2)
        self.assertEqual(modalidad.puntos, 2)
        self.assertEqual(oferta.criterios[2].puntos, "Sin datos")
        secciones = explicar_oferta(oferta)
        self.assertTrue(secciones["interes"])
        self.assertTrue(secciones["parciales"])
        self.assertFalse(secciones["gaps"])

    def test_pesos_aprobados_y_sin_datos(self):
        perfil = migrar_perfil({})
        perfil.update(importancia_ubicacion="Baja", importancia_modalidad="Baja", importancia_salario="Baja")
        pesos = normalizar_pesos(perfil)
        self.assertEqual(pesos["puesto"], .25)
        self.assertEqual(pesos["capacidades"], .25)
        criterios = oferta_ficticia(puntos=[2] + ["Sin datos"] * 6).criterios
        self.assertEqual(calcular_fit(criterios, pesos), {"fit": 10, "cobertura": 25})
        criterios[0].puntos = 0
        self.assertEqual(calcular_fit(criterios, pesos)["fit"], 1)
        criterios[0].puntos = "Sin datos"
        self.assertEqual(calcular_fit(criterios, pesos), {"fit": None, "cobertura": 0})

    def test_preferencias_cambian_orden_sin_excluir(self):
        a = oferta_ficticia(puntos=[0, 0, 0, 0, 2, 0, 0])
        b = oferta_ficticia(puesto="Otra", enlace="https://example.com/2", puntos=[0, 0, 0, 0, 0, 2, 0])
        datos = [a.model_dump(), b.model_dump()]
        pesos = normalizar_pesos({"importancia_ubicacion": "Alta", "importancia_modalidad": "Baja"})
        self.assertEqual(ordenar_evaluaciones(datos, pesos)[0]["oferta"].enlace, a.enlace)
        pesos = normalizar_pesos({"importancia_ubicacion": "Baja", "importancia_modalidad": "Alta"})
        self.assertEqual(ordenar_evaluaciones(datos, pesos)[0]["oferta"].enlace, b.enlace)
        self.assertEqual(len(ordenar_evaluaciones(datos, pesos)), 2)

    def test_salario_no_comparable_y_evidencia_confirmada(self):
        oferta = oferta_ficticia()
        perfil = migrar_perfil({"puesto": "Analista", "capacidades": "Python", "ubicacion": "Madrid"})
        perfil.update(salario_minimo=40000, moneda="EUR")
        texto = "Empresa ficticia Analista Madrid Analizar datos Python. Salario bruto anual: 50000–60000 EUR."
        recuperadas = {oferta.enlace: {"descripcion_recuperada": texto}}
        oferta.salario_documentado = DatosSalario(minimo=50000, maximo=60000, moneda="EUR",
            periodo="Anual", tipo="Bruto", evidencia="Salario bruto anual: 50000–60000 EUR.")
        def validar():
            return validar_recomendaciones(Resultado(ofertas=[oferta], descartadas=[]), recuperadas,
                                           perfil_para_modelo(perfil))[0]
        self.assertEqual(validar().criterios[-1].puntos, 2)
        perfil["moneda"] = "GBP"
        self.assertEqual(validar().criterios[-1].puntos, "Sin datos")
        perfil["moneda"] = "EUR"
        oferta.salario_documentado.periodo = "Mensual"
        self.assertEqual(validar().criterios[-1].puntos, "Sin datos")
        oferta.salario_documentado.periodo = "Anual"
        oferta.salario_documentado.minimo = 70000
        self.assertEqual(validar().criterios[-1].puntos, "Sin datos")

    def test_aspiracion_no_acredita_skill(self):
        oferta = oferta_ficticia()
        perfil = migrar_perfil({"puesto": "Analista", "capacidades": "SQL"})
        perfil["que_buscas"] = "Python"
        recuperadas = {oferta.enlace: {"descripcion_recuperada": "Empresa ficticia Analista Madrid Analizar datos Python"}}
        validada = validar_recomendaciones(Resultado(ofertas=[oferta], descartadas=[]), recuperadas,
                                          perfil_para_modelo(perfil))[0]
        self.assertEqual(validada.criterios[1].puntos, "Sin datos")


class PruebasInterfaz(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.archivo = Path(self.temporal.name) / "perfil.json"
        self.evaluaciones = Path(self.temporal.name) / ".datos" / "evaluaciones.json"
        self.perfil = {"puesto": "Analista", "ubicacion": "Madrid", "experiencia_profesional": "3 años",
                       "capacidades": "Python", "preferencias_laborales": "Híbrido", "dato_extra": "conservar"}
        guardar_json(self.archivo, self.perfil)
        self.parches = [patch.object(datos_locales, "ARCHIVO_PERFIL", self.archivo),
                        patch("formulario.ARCHIVO_PERFIL", self.archivo),
                        patch("mejoras.ARCHIVO_PERFIL", self.archivo),
                        patch("skills.ARCHIVO_PERFIL", self.archivo),
                        patch.object(datos_locales, "ARCHIVO_EVALUACIONES", self.evaluaciones),
                        patch("agente.buscar_ofertas")]
        for p in self.parches:
            ultimo = p.start()
        self.buscar = ultimo
        self.buscar.return_value = {"evaluaciones": [oferta_ficticia().model_dump()], "eventos": [],
                                    "fecha": "2026-10-09T12:00:00Z", "llamadas": 2, "error": False}

    def tearDown(self):
        for p in reversed(self.parches):
            p.stop()
        self.temporal.cleanup()

    def app(self):
        return AppTest.from_file(str(Path(__file__).parent / "app.py"), default_timeout=15).run()

    def boton(self, app, etiqueta):
        return next(b for b in app.button if b.label == etiqueta)

    def test_editar_cancelar_guardar_y_unico_trigger(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertFalse(any(b.label == "Guardar perfil" for b in app.button))
        self.buscar.assert_not_called()
        original = self.archivo.read_bytes()
        self.boton(app, "Editar perfil").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="editor_experiencia").value, "1–3 años")
        self.assertTrue(app.selectbox(key="editor_preferencia_modalidad_Remoto").disabled)
        app.text_area(key="editor_que_buscas").set_value("Aprender Rust").run()
        self.boton(app, "Cancelar").click().run()
        self.assertEqual(self.archivo.read_bytes(), original)
        self.boton(app, "Editar perfil").click().run()
        self.assertEqual(app.text_area(key="editor_que_buscas").value, "")
        app.text_area(key="editor_que_buscas").set_value("Mejorar en análisis").run()
        self.boton(app, "Guardar perfil").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(any(b.label == "Guardar perfil" for b in app.button))
        self.buscar.assert_not_called()
        guardado = datos_locales.cargar_perfil()
        self.assertEqual(guardado["datos_anteriores"]["dato_extra"], "conservar")
        self.boton(app, "Editar perfil").click().run()
        self.assertEqual(app.text_area(key="editor_que_buscas").value, "Mejorar en análisis")
        self.boton(app, "Cancelar").click().run()
        self.boton(app, "Buscar ofertas").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.buscar.call_count, 1)
        self.assertTrue(self.evaluaciones.exists())
        self.boton(app, "Editar perfil").click().run()
        app.selectbox(key="editor_importancia_ubicacion").select("Alta").run()
        self.boton(app, "Guardar perfil").click().run()
        self.assertFalse(any("El perfil ha cambiado" in w.value for w in app.warning))
        self.assertTrue(any(h.value == "Resultado de Busqueda" for h in app.subheader))
        self.assertTrue(any(b.label == "Buscar ofertas" for b in app.button))
        self.assertFalse(any("OpenAI" in c.value or "Tavily" in c.value or "Git" in c.value for c in app.caption))
        self.assertEqual(self.buscar.call_count, 1)
        self.boton(app, "Buscar ofertas").click().run()
        self.assertEqual(self.buscar.call_count, 2)
        app.session_state.buscando = True
        app.run()
        self.assertTrue(self.boton(app, "Buscar ofertas").disabled)
        self.assertEqual(self.buscar.call_count, 2)

    def test_anadir_limite_eliminar_duplicados_y_nivel(self):
        app = self.app()
        self.boton(app, "Editar perfil").click().run()
        app.button(key="editor_anadir_puestos_objetivo").click().run()
        self.assertTrue(any("vacía" in e.value for e in app.error))
        app.text_input(key="editor_nuevo_puestos_objetivo").set_value(" ANALISTA ")
        app.button(key="editor_anadir_puestos_objetivo").click().run()
        self.assertTrue(any("ya está" in e.value for e in app.error))
        for n in range(4):
            app.text_input(key="editor_nuevo_puestos_objetivo").set_value(f"Puesto {n}")
            app.button(key="editor_anadir_puestos_objetivo").click().run()
        self.assertTrue(app.button(key="editor_anadir_puestos_objetivo").disabled)
        app.button(key=clave_opcion("puestos_objetivo_eliminar", "Puesto 0")).click().run()
        self.assertFalse(app.button(key="editor_anadir_puestos_objetivo").disabled)
        app.text_input(key="editor_nuevo_idiomas").set_value("Inglés")
        app.button(key="editor_anadir_idiomas").click().run()
        app.selectbox(key=clave_opcion("idiomas_nivel", "Inglés")).select("Alto").run()
        app.checkbox(key="editor_modalidad_Remoto").check().run()
        self.assertFalse(app.selectbox(key="editor_preferencia_modalidad_Remoto").disabled)
        self.buscar.assert_not_called()
        self.assertFalse(app.exception)

    def test_sin_archivo_formulario_vacio_y_perfil_incompleto_persistente(self):
        self.archivo.unlink()
        app = self.app()
        self.assertFalse(app.exception)
        self.assertFalse(self.archivo.exists())
        for campo in ("puestos_objetivo", "ubicaciones", "skills", "idiomas"):
            self.assertEqual(app.text_input(key="editor_nuevo_" + campo).value, "")
        self.assertEqual(app.text_area(key="editor_que_buscas").value, "")
        self.assertIsNone(app.selectbox(key="editor_experiencia").value)
        self.assertIsNone(app.selectbox(key="editor_moneda").value)
        self.assertIsNone(app.number_input(key="editor_salario").value)
        for modalidad in ("Presencial", "Híbrido", "Remoto"):
            self.assertFalse(app.checkbox(key="editor_modalidad_" + modalidad).value)
        self.boton(app, "Guardar perfil").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(self.boton(app, "Buscar ofertas").disabled)
        self.assertFalse(any(b.label == "Guardar perfil" for b in app.button))
        guardado = datos_locales.cargar_perfil()
        self.assertEqual(guardado["puestos_objetivo"], [])
        self.assertEqual(guardado["skills"], [])
        self.assertIsNone(guardado["salario_minimo"])
        self.assertIsNone(guardado["importancia_ubicacion"])
        # Reabrir carga el perfil incompleto y muestra su resumen.
        app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(self.boton(app, "Buscar ofertas").disabled)
        self.boton(app, "Editar perfil").click().run()
        app.text_input(key="editor_nuevo_puestos_objetivo").set_value("Analista")
        app.button(key="editor_anadir_puestos_objetivo").click().run()
        self.boton(app, "Guardar perfil").click().run()
        app = self.app()
        self.assertFalse(self.boton(app, "Buscar ofertas").disabled)
        self.boton(app, "Editar perfil").click().run()
        self.assertEqual(app.session_state.borrador["puestos_objetivo"], ["Analista"])
        app.button(key=clave_opcion("puestos_objetivo_eliminar", "Analista")).click().run()
        self.boton(app, "Cancelar").click().run()
        app = self.app()
        self.assertEqual(app.session_state.perfil["puestos_objetivo"], ["Analista"])
        self.buscar.assert_not_called()

    def test_cancelar_creacion_no_guarda_y_reabre_vacio(self):
        self.archivo.unlink()
        app = self.app()
        app.text_input(key="editor_nuevo_skills").set_value("Python")
        app.button(key="editor_anadir_skills").click().run()
        self.boton(app, "Cancelar").click().run()
        self.assertFalse(self.archivo.exists())
        self.boton(app, "Crear perfil").click().run()
        self.assertEqual(app.session_state.borrador["skills"], [])
        self.buscar.assert_not_called()

    def test_empresa_actual_se_guarda_y_se_recupera(self):
        app = self.app()
        self.boton(app, "Editar perfil").click().run()
        app.text_input(key="editor_empresa_actual").set_value("Empresa ficticia")
        app.checkbox(key="editor_excluir_empresa").check().run()
        self.boton(app, "Guardar perfil").click().run()
        app = self.app()
        self.boton(app, "Editar perfil").click().run()
        self.assertEqual(app.text_input(key="editor_empresa_actual").value, "Empresa ficticia")
        self.assertTrue(app.checkbox(key="editor_excluir_empresa").value)
        self.buscar.assert_not_called()

    def test_resultados_explicados_sin_notas_ni_etiqueta_global(self):
        app = self.app()
        self.boton(app, "Buscar ofertas").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        texto = "\n".join(m.value for m in app.markdown)
        for seccion in ("Motivos de interés", "Requisitos que cumple", "Gaps", "Información pendiente de confirmar"):
            self.assertIn(seccion, texto)
        for etiqueta in ("Fit global", "Encaje profesional", "Fit no calculable"):
            self.assertNotIn(etiqueta, texto)
        self.assertEqual(self.buscar.call_count, 1)


if __name__ == "__main__":
    unittest.main()
