---
name: adaptar-cv
description: Adapta el CV a una oferta concreta, solo cuando la persona lo pide: lee la oferta, identifica lo que más se valora y genera un CV de una página en PDF que pone eso en primer plano, sin inventar nada. Úsalo cuando pida adaptar, ajustar, tunear o preparar su CV para un puesto o candidatura. Argumento: URL de la oferta, o empresa/puesto de una candidatura u oferta guardada.
---

# /adaptar-cv — CV a medida para una oferta

## Regla de oro: verdad
Solo puedes **seleccionar, reordenar, resumir y reformular** contenido de `cv/cv_maestro.json`
y `perfil/perfil.md`. Nunca:
- inventes experiencia, responsabilidades, herramientas, cifras, títulos o fechas;
- subas el nivel de una skill (Python sigue siendo "learning" mientras lo diga el maestro);
- pongas una palabra clave de la oferta que no puedas respaldar con algo real.

Si una cifra o un logro mejoraría mucho el CV y no está en el maestro, **pregúntalo** (paso 4) y,
si la persona lo da, añádelo también a `cv/cv_maestro.json` para la próxima vez.

## 1. Identificar la oferta
- Argumento: URL, o empresa/puesto. Saca la URL con `.venv/bin/python -I app/cli.py candidaturas` u
  `.venv/bin/python -I app/cli.py ofertas` (busca por empresa/puesto).
- Lee la oferta completa: WebFetch a la URL (o la API del ATS: Ashby
  `api.ashbyhq.com/posting-api/job-board/<empresa>`, Greenhouse
  `boards-api.greenhouse.io/v1/boards/<empresa>/jobs?content=true`, Lever
  `api.lever.co/v0/postings/<empresa>?mode=json`). Si no se puede leer, pide a la persona que
  pegue el texto.
- Idioma del CV = idioma de la oferta (`"idioma": "en"` o `"es"`). Si hay que traducir,
  traduce fielmente.

## 2. Qué valora el puesto
Extrae y ordena por importancia:
- **Imprescindibles** y **deseables** (con las palabras exactas que usa la oferta).
- **Qué hará de verdad** y qué tipo de persona buscan (ownership, ambigüedad, cliente, datos…).
- **Palabras clave** que un ATS o un recruiter buscará (herramientas, funciones, sector).

## 3. Mapa requisito → evidencia
Para cada requisito, busca la mejor evidencia real en el maestro y en `perfil.md` (incluida
"Cómo presentarse"). Clasifica: ✅ evidencia directa · ⚠️ transferible · ❌ no hay.
Los ❌ no se tapan: van a la nota final como gaps a preparar para la entrevista.

## 4. Preguntar solo lo que falte (opcional)
Si hay 1-3 datos que cambiarían el CV (una cifra de impacto, el tamaño de un equipo, una
herramienta usada de verdad), pregúntalos en un único AskUserQuestion. Si no hace falta, sigue.

## 5. Construir el CV adaptado
Parte de una copia del maestro y decide:
- **Resumen** (3-4 líneas): reescríbelo para este puesto. Primera frase = quién eres en
  relación con el rol, usando su vocabulario. Incluye 2-3 de sus imprescindibles que cumples.
- **Experiencia**: mantén todos los puestos (sin huecos en la cronología). Dentro de cada uno,
  ordena los bullets por relevancia para la oferta, reformula para usar su vocabulario y poner
  delante el resultado o el ownership. Recorta o elimina bullets que no sumen (p. ej. el PMO en
  roles de despliegue o startup, según "Cómo presentarse"). Las prácticas antiguas pueden
  quedarse en una línea.
- **Proyectos**: solo los que respalden la oferta (normalmente 2-3), los más relevantes primero.
  Reformula la frase inicial hacia lo que valora el puesto.
- **Skills**: reordena las categorías y los items para que lo pedido salga primero; puedes
  renombrar categorías (p. ej. "AI & automation"). Quita lo irrelevante. Las marcas "(extra)"
  son contenido verdadero.
- **Orden de secciones** (`"orden"`): por defecto resumen → experiencia → proyectos →
  educación → skills. Si el puesto es muy técnico o de IA y los proyectos son la mejor prueba,
  valora proyectos antes que educación (nunca antes que experiencia).
- **Una página**. Si no cabe, recorta los bullets menos relevantes antes que la letra.

Escribe el resultado en
`cv/adaptados/AAAA-MM-DD_<empresa>_<puesto-corto>/cv.json` (mismo formato que el maestro) y
genera el PDF:

```bash
.venv/bin/python -I herramientas/render_cv.py cv/adaptados/<carpeta>/cv.json "cv/adaptados/<carpeta>/CV_<Nombre>_<Empresa>.pdf"
```

Si avisa de que no cabe en una página, recorta y repite. Lee el PDF con Read para comprobar
que se ve bien.

## 6. Nota de cambios
Escribe `cv/adaptados/<carpeta>/notas.md`:

```markdown
# CV para <Puesto> — <Empresa>
Oferta: <URL> · Generado: AAAA-MM-DD

## Lo que más valoran
1. ... (imprescindible)
2. ...

## Cómo lo responde el CV
| Lo que piden | Dónde aparece en el CV | |
|---|---|---|
| ... | Resumen + bullet SSC Sudamérica | ✅ |

## Cambios respecto al CV maestro
- Resumen: ...
- Reordenado / reformulado: ...
- Quitado: ...

## Gaps que el CV no cubre (prepáralos para la entrevista)
- ...
```

## 7. Cerrar
- Enlaza el CV en la candidatura (aparecerá en la app):
  `.venv/bin/python -I app/cli.py actualizar <id_cand> --cv "cv/adaptados/<carpeta>/<fichero>.pdf" --nota "CV adaptado generado"`.
  Si no existía la candidatura, créala con `app/cli.py nueva-candidatura "<Empresa>" "<Puesto>"
  --url <url> --cv <ruta>` (queda como `por aplicar`).
- En el chat: enlace al PDF, las 3-4 decisiones más importantes del ajuste, los gaps y,
  si alguna información era dudosa, qué debería revisar la persona antes de enviarlo.
- Ofrece, si lo quiere, una carta o un mensaje corto para el recruiter con el mismo enfoque.
