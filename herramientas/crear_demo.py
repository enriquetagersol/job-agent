"""Crea una copia de demostración de Job Agent con DATOS FICTICIOS (persona, empresas y ofertas inventadas).

Sirve para enseñar la app (capturas, portfolio, «Abrir demo») sin mostrar datos reales.
Uso:  python3 -I herramientas/crear_demo.py <carpeta_destino>
Copia el código de la app a <carpeta_destino> y rellena datos/, perfil/ y cv/ con la demo.
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOY = dt.date.today()


def d(dias):
    return (HOY - dt.timedelta(days=dias)).isoformat()


def f(dias):
    return (HOY + dt.timedelta(days=dias)).isoformat()


CV = {
    "_nota": "CV ficticio para la demo de Job Agent.",
    "idioma": "en", "nombre": "Alex Example",
    "contacto": ["Madrid, Spain", "alex@example.com", "linkedin.com/in/alex-example"],
    "resumen": "Engineer with a business background and three years in technology consulting. I build tools that "
               "remove manual work, translate technical solutions into business cases and work hands-on with clients.",
    "experiencia": [
        {"id": "northwind", "empresa": "Northwind Consulting", "equipo": "Technology Strategy", "cargo": "Consultant",
         "fechas": "Sep 2023 – Present", "bullets": [
             "Built the business case for a 25-FTE shared services centre: investment, ROI and three scenarios.",
             "Created an automated tracking tool that the whole project team adopted to follow 40+ initiatives.",
             "Coordinated vendors and client stakeholders to prioritise and budget platform improvements."]},
        {"id": "contoso", "empresa": "Contoso Labs", "equipo": "Growth", "cargo": "Business Analyst Intern",
         "fechas": "Jan 2023 – Jun 2023", "bullets": [
             "Analysed funnel data in SQL and proposed two onboarding experiments for the product team."]}],
    "proyectos": [
        {"id": "saas", "nombre": "Serverless Booking SaaS", "contexto": "Master's Thesis",
         "texto": "Designed and built an end-to-end serverless web app on AWS (Lambda, DynamoDB, Cognito) with three user roles."},
        {"id": "agentes", "nombre": "AI Research Assistant", "contexto": "Personal project",
         "texto": "Prototyped a multi-agent assistant that summarises market research for go-to-market teams."}],
    "educacion": [{"centro": "Universidad Ejemplo", "titulo": "MEng Telecommunications Engineering", "fecha": "2023"},
                  {"centro": "Universidad Ejemplo", "titulo": "BSc Business Administration", "fecha": "2022"}],
    "skills": [{"categoria": "Technical", "items": ["Python", "SQL", "JavaScript", "AWS", "REST APIs"]},
               {"categoria": "Business", "items": ["Business cases", "Process design", "Stakeholder management"]}],
    "certificaciones": ["Scrum Master (PSM I)"], "idiomas": "Spanish (native), English (C1)"}

PERFIL = """# Perfil profesional
_Perfil ficticio de la demo de Job Agent._

## Resumen
Ingeniero/a de Telecomunicación con formación en ADE y tres años en consultoría tecnológica. Hace business cases,
diseña procesos y construye herramientas que eliminan trabajo manual. Busca puestos de soluciones, estrategia o
despliegue en empresas de producto, idealmente de IA.

## Datos clave
- Madrid · híbrido o remoto desde España · inglés C1
"""

PREF = {"puestos": ["Solutions Engineer", "Deployment Strategist", "Strategy & Operations", "Business Analyst"],
        "ubicaciones": ["Madrid", "Remoto desde España"], "mudarme_a": [], "modalidad": "Híbrido",
        "salario_minimo": 38000, "salario_objetivo": 45000, "sectores": ["IA", "SaaS B2B", "Empresa de producto"],
        "valoro": ["Ownership", "Aprendizaje técnico", "Impacto visible"], "evitar": ["Solo reporting", "Muchos viajes"],
        "descarto": ["Consultoras", "Venta con cuota"], "frases": {}, "actualizado": d(3)}


def ev(dias, texto, tipo="nota", **extra):
    return {"fecha": d(dias), "tipo": tipo, "texto": texto, **extra}


def paso(texto, dias):
    return {"texto": texto, "fecha": f(dias), "sugerido": True}


CANDS = [
    ("Nimbus AI", "Deployment Strategist", "en_proceso", 2, paso("Preparar la entrevista técnica con el Head of Deployment", 2), [
        ev(20, "Creada como Aplicada", "estado"), ev(9, "Enviada → En proceso", "estado"),
        ev(2, "Te invitan a una entrevista técnica el jueves a las 11:00", origen="correo")]),
    ("Lumen Pay", "Strategy & Operations Analyst", "en_proceso", 4, paso("Enviar la nota de agradecimiento a la hiring manager", 0), [
        ev(18, "Creada como Aplicada", "estado"), ev(4, "Primera entrevista con la hiring manager: muy buena conversación")]),
    ("Orbita Labs", "Solutions Engineer", "oferta", 1, paso("Responder a la oferta y negociar la parte variable", 3), [
        ev(30, "Creada como Aplicada", "estado"), ev(12, "Caso práctico entregado"),
        ev(1, "En proceso → Oferta", "estado"), ev(1, "Oferta: 46.000 € + equity, híbrido en Madrid", origen="correo")]),
    ("Kelpie", "Business Analyst – AI", "enviada", 6, paso("Hacer follow-up con el recruiter si no hay respuesta", 1), [
        ev(6, "Creada como Aplicada", "estado"), ev(6, "Confirmación de la candidatura", origen="correo")]),
    ("Atlas Mobility", "Operations Strategy Associate", "enviada", 16, paso("Follow-up por LinkedIn a la recruiter", 0), [
        ev(16, "Creada como Aplicada", "estado")]),
    ("Polar Data", "Customer Solutions Analyst", "enviada", 9, paso("Esperar respuesta; follow-up la semana que viene", 5), [
        ev(9, "Creada como Aplicada", "estado"), ev(7, "Han visto tu solicitud", origen="correo")]),
    ("Fresco Market", "Growth Analyst", "rechazada", 3, None, [
        ev(25, "Creada como Aplicada", "estado"), ev(3, "Aplicada → Rechazada", "estado"),
        ev(3, "Buscaban más experiencia en SQL avanzado", origen="correo")]),
    ("Brisa Energy", "Strategy Analyst", "retirada", 11, None, [
        ev(28, "Creada como Aplicada", "estado"), ev(11, "Aplicada → Retirada", "estado"), ev(11, "Era 100 % presencial")]),
]

OFERTAS = [
    {"empresa": "Quanta Legal", "puesto": "Deployment Strategist", "encaje": 86, "nueva": True,
     "datos": "Madrid · híbrido (2 días) · salario no publicado · hace 3 días",
     "empresa_desc": "Scale-up de legaltech que automatiza la revisión de contratos con IA para despachos y equipos legales.",
     "que_harias": "Llevarías los despliegues de la plataforma en grandes despachos: entender sus procesos, decidir qué automatizar y medir el retorno junto al equipo técnico.",
     "por_que_encaja": "Tu business case con ROI y escenarios y tu herramienta de seguimiento que adoptó el equipo encajan con «diseñar el despliegue y demostrar valor». Además, piden perfil técnico-negocio, que es justo tu mezcla.",
     "por_que_no_encaja": "Piden experiencia con clientes del sector legal, que no tienes. Es salvable: tu experiencia con stakeholders de cliente compensa."},
    {"empresa": "Vertex Robotics", "puesto": "Solutions Engineer", "encaje": 78, "nueva": True,
     "datos": "Remoto desde España · viajes 10 % · 42.000-50.000 € · hace 1 semana",
     "empresa_desc": "Startup de robótica para almacenes; vende software de orquestación de robots a operadores logísticos.",
     "que_harias": "Acompañarías al equipo comercial en las demos y pruebas piloto, y diseñarías la integración con los sistemas de cada cliente.",
     "por_que_encaja": "Tu base de Teleco, tus APIs en AWS y tu experiencia traduciendo lo técnico a negocio encajan con preventa técnica sin cuota.",
     "por_que_no_encaja": "Valoran experiencia en logística o WMS, que no tienes."},
    {"empresa": "Kelpie", "puesto": "Product Operations Analyst", "encaje": 71, "nueva": False,
     "datos": "Madrid · híbrido · salario no publicado · hace 2 semanas",
     "empresa_desc": "SaaS B2B de gestión de turnos para retail y hostelería, con oficinas en Madrid y Lisboa.",
     "que_harias": "Mejorarías los procesos del equipo de producto: métricas, priorización de peticiones de clientes y automatización de tareas internas.",
     "por_que_encaja": "Tu instinto de automatizar (la herramienta que adoptó tu equipo) y tu análisis de funnels en SQL encajan con el día a día.",
     "por_que_no_encaja": "Es más operativo que estratégico; puede tener bastante reporting."},
]
GUARDADAS = [
    {"empresa": "Nimbus AI", "puesto": "Implementation Lead", "encaje": 82,
     "datos": "Madrid · híbrido · 45.000-52.000 € · hace 5 días",
     "empresa_desc": "Startup de agentes de IA para atención al cliente; ronda Serie A en 2026.",
     "que_harias": "Liderarías la puesta en marcha de los agentes en clientes nuevos: configuración, formación y seguimiento del valor.",
     "por_que_encaja": "Has coordinado proveedores y clientes en programas complejos y has prototipado agentes de IA por tu cuenta.",
     "por_que_no_encaja": "El título dice «Lead», aunque piden 2-3 años: confirma el nivel en la primera llamada."},
    {"empresa": "Lumen Pay", "puesto": "Strategy Associate", "encaje": 77,
     "datos": "Madrid · híbrido · salario no publicado · hace 1 semana",
     "empresa_desc": "Fintech de pagos para pymes en Europa, con 300 empleados.",
     "que_harias": "Trabajarías con el equipo de dirección en proyectos estratégicos: nuevos mercados, pricing y modelos de negocio.",
     "por_que_encaja": "Tus business cases y tu formación en ADE encajan con proyectos estratégicos de principio a fin.",
     "por_que_no_encaja": "No tienes experiencia en pagos; lo compensa tu perfil analítico."},
]

NOTAS = """# CV para Implementation Lead — Nimbus AI
_Demo con datos ficticios._

## Lo que más valoran
1. **Poner en marcha producto en clientes**: configurar, formar y medir el valor.
2. **Perfil técnico-negocio**: entender APIs e integraciones y hablar con negocio.
3. **Ownership** de principio a fin.

## Cómo lo responde el CV
| Lo que piden | Dónde aparece | |
|---|---|---|
| Implantaciones en cliente | Coordinación de proveedores y stakeholders (Northwind) | ✅ |
| Base técnica | AWS, APIs, Python; SaaS serverless del TFM | ✅ |
| Agentes de IA | AI Research Assistant (proyecto personal) | ⚠️ prototipo |
| Experiencia en atención al cliente | — | ❌ |

## Cambios respecto al CV maestro
- **Resumen** reescrito alrededor de «implantar y demostrar valor».
- El **proyecto de agentes de IA** sube al primer lugar de Proyectos.
- La viñeta de la **herramienta de seguimiento** pasa delante: demuestra que construyes para quitar trabajo manual.

## Revisa antes de enviar
- Confirma que el prototipo de agentes puede enseñarse en la entrevista.
"""


def main(destino):
    destino = os.path.abspath(destino)
    if os.path.exists(destino):
        shutil.rmtree(destino)
    ignorar = shutil.ignore_patterns(".venv", "__pycache__", ".git", "cv", "perfil", "datos", "resultados")
    shutil.copytree(RAIZ, destino, ignore=ignorar)
    for sub in ("datos", "perfil", "cv/adaptados", "resultados"):
        os.makedirs(os.path.join(destino, sub), exist_ok=True)
    escribir = lambda ruta, obj: json.dump(obj, open(os.path.join(destino, ruta), "w", encoding="utf-8"),  # noqa: E731
                                           ensure_ascii=False, indent=1)
    escribir("cv/cv_maestro.json", CV)
    escribir("perfil/preferencias.json", PREF)
    open(os.path.join(destino, "perfil/perfil.md"), "w", encoding="utf-8").write(PERFIL)
    open(os.path.join(destino, "perfil/preferencias.md"), "w", encoding="utf-8").write("# Preferencias\n_Demo._\n")

    cands, n = [], 0
    for prio, (emp, puesto, estado, dias, pp, eventos) in enumerate(CANDS):
        n += 1
        cands.append({"id": f"c{n:03d}", "empresa": emp, "puesto": puesto, "url": "https://example.com/jobs",
                      "estado": estado, "detalle": "", "contacto": "", "fecha_aplicacion": eventos[0]["fecha"],
                      "fecha_actualizacion": d(dias), "proximo_paso": pp, "cv_adaptado": "", "oferta_id": None,
                      "eventos": eventos, "prioridad": prio})
    lote = dt.datetime.now().isoformat(timespec="seconds")
    ofertas, k = [], 0

    def oferta(o, decision=None, cid=None):
        nonlocal k
        k += 1
        return {"id": f"o{k:03d}", "url": f"https://example.com/jobs/{k}", "empresa": o["empresa"], "puesto": o["puesto"],
                "encaje": o["encaje"], "estado_analisis": "recomendada", "motivo_descarte": "", "fecha_analisis": d(1),
                "informe": "demo", "datos": o["datos"], "empresa_desc": o["empresa_desc"],
                "sencillo": {k2: o[k2] for k2 in ("que_harias", "por_que_encaja", "por_que_no_encaja")},
                "puntuacion": "", "rasgos": [], "decision": decision, "candidatura_id": cid,
                "lote": lote if o.get("nueva") else d(9)}
    for o in OFERTAS:
        ofertas.append(oferta(o))
    adaptados = os.path.join(destino, "cv", "adaptados", "demo_nimbus-ai_implementation-lead")
    os.makedirs(adaptados, exist_ok=True)
    for o in GUARDADAS:
        n += 1
        cid = f"c{n:03d}"
        of = oferta(o, {"valor": "interesa", "motivo": "", "fecha": d(1), "aprendida": True}, cid)
        ofertas.append(of)
        c = {"id": cid, "empresa": o["empresa"], "puesto": o["puesto"], "url": of["url"], "estado": "por_aplicar",
             "detalle": "", "contacto": "", "fecha_aplicacion": None, "fecha_actualizacion": d(1),
             "proximo_paso": paso("Revisar el CV optimizado y enviar la candidatura", 1), "cv_adaptado": "",
             "oferta_id": of["id"], "eventos": [ev(1, "Creada como Por aplicar", "estado")], "prioridad": None}
        if o["empresa"] == "Nimbus AI":
            json.dump(CV, open(os.path.join(adaptados, "cv.json"), "w", encoding="utf-8"), ensure_ascii=False)
            open(os.path.join(adaptados, "notas.md"), "w", encoding="utf-8").write(NOTAS)
            pdf = os.path.join(adaptados, "CV_Alex_Example_nimbus-ai.pdf")
            subprocess.run([sys.executable, "-I", os.path.join(RAIZ, "herramientas", "render_cv.py"),
                            os.path.join(adaptados, "cv.json"), pdf], capture_output=True, timeout=120)
            c["cv_adaptado"] = os.path.relpath(pdf, destino)
            c["cv_trabajo"] = {"estado": "listo", "notas": os.path.relpath(os.path.join(adaptados, "notas.md"), destino)}
        cands.append(c)
    escribir("datos/candidaturas.json", {"candidaturas": cands, "lecturas": []})
    escribir("datos/ofertas.json", {"ofertas": ofertas, "ultimo_lote": lote})
    escribir("datos/busqueda.json", {"estado": "listo", "fase": "3 ofertas nuevas para ti de 21 analizadas",
                                      "nuevas": 3, "fin": d(1) + "T09:00:00"})
    print(f"Demo creada en {destino}: {len(cands)} candidaturas, {len(ofertas)} ofertas.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
