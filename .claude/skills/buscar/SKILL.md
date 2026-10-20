---
name: buscar
description: Busca ofertas de empleo en la web según perfil/perfil.md y perfil/preferencias.md, lee y analiza cada oferta completa, puntúa su encaje y genera un informe de recomendaciones con enlaces en resultados/. Úsalo cuando la persona pida buscar trabajo, ofertas o recomendaciones. Acepta como argumento un foco opcional (p. ej. "/buscar solo remoto" o "/buscar Barcelona").
---

# /buscar — Buscar, analizar y recomendar

## 0. Requisitos

- Lee `perfil/perfil.md`, `perfil/preferencias.md` y `perfil/preferencias.json` (lo que la
  persona ha editado en la app; manda si hay conflicto: puestos, ubicaciones, salario, descartes). Si falta el perfil, para y ofrece `/perfil`.
  Si faltan las preferencias, avisa de que la búsqueda será menos precisa y ofrece
  `/preferencias`; continúa solo si la persona lo pide.
- Los datos viven en `datos/` y se consultan con la CLI (la misma que usa la app):
  `.venv/bin/python -I app/cli.py urls-vistas` (ofertas ya vistas: no las repitas) y `.venv/bin/python -I app/cli.py candidaturas` (candidaturas reales). Aplica las
  candidaturas así:
  - **No recomiendes** ofertas a las que ya ha aplicado (misma empresa + mismo puesto o casi
    igual). Si una oferta nueva es de una empresa con candidatura abierta, inclúyela solo si es un
    puesto distinto, y avísalo ("ya estás en proceso con X para Y").
  - Empresa con **rechazo reciente** (< 6 meses) para un puesto similar: penaliza −10 en
    "preferencias" y añade un aviso; no la pongas en el top 3.
  - Usa las **lecturas** (`datos/candidaturas.json` → `lecturas`) y la fase a la que llega (screening, entrevista,
    oferta) para calibrar: da más peso a los tipos de puesto y empresa donde avanza, menos a
    donde la paran en screening.
  - Si tiene una **oferta pendiente**, recuérdalo en el resumen del informe: las recomendaciones
    deben valer la pena frente a esa oferta.
  - En el informe, añade una sección corta "Seguimiento de candidaturas" con las que llevan más
    de 14 días sin novedad.
- Si el comando trae argumentos, tómalos como foco adicional de esta búsqueda (no cambian
  `preferencias.md`).

## 1. Plan de búsqueda

### 1a. Fuente principal: APIs de empleo de empresas

Es la fuente más fiable: devuelve todas las ofertas abiertas con la descripción completa, sin
bloqueos. Ejecuta (con la carpeta de salida en tu scratchpad):

```bash
.venv/bin/python -I herramientas/ats_fetch.py <scratchpad>/busqueda --titulo "<regex>" --ubicacion "<regex>"
```

- `--titulo`: regex con los puestos objetivo y sus variantes en inglés (p. ej.
  `solution|sales engineer|pre-?sales|forward deployed|deployment|product manager|...`).
- `--ubicacion`: regex con las ciudades/países de `preferencias.md` (+ `remote|emea|europe` si
  acepta remoto).
- La lista de empresas está en `herramientas/empresas.json`. Añade antes las empresas
  "deseadas" de `preferencias.md` y las que aparezcan en 1b, si sabes su identificador en
  Ashby/Greenhouse/Lever (está en la URL de su página de empleo).
- Resultado: `<salida>/candidatas.json` (índice con id, empresa, título, ubicación, fecha,
  salario, `senior`) y `<salida>/ofertas/<id>.txt` (oferta completa). Revisa el índice con un
  script corto agrupando por ubicación; aparta los `senior: true` salvo que el perfil lo sea.

### 1b. Fuente complementaria: búsqueda web

Sirve para empresas que no están en la lista (sobre todo españolas o con otro ATS). Incluye
siempre:
- Las startups de `perfil/empresas_seguidas.md` (si existe): abre su página de empleo (YC, Kula…)
  con WebFetch o el navegador integrado.
- Startups de YC con sede o hub en España: `site:ycombinator.com/companies "Madrid" jobs` + el
  puesto objetivo (también `seedtable.com`, `choppingblock.ai`).

Construye además 5-10 consultas combinando:
- Títulos objetivo (ES y EN) de `perfil.md` y puestos objetivo de `preferencias.md`, incluidas
  variantes y sinónimos: el mismo trabajo se llama de formas distintas.
- 1-2 skills diferenciales del perfil (para encontrar puestos con otro título pero mismo contenido).
- Ubicación/modalidad (ciudad, "remoto", "remote Spain", "híbrido").
- Seniority ("senior", "lead"…) cuando aplique.

Fuentes (usa `site:` en WebSearch):
- Portales: `linkedin.com/jobs`, `infojobs.net`, `indeed.com` / `es.indeed.com`,
  `tecnoempleo.com`, `getmanfred.com`, `welcometothejungle.com`, `glassdoor.es`.
- Páginas de empleo de empresas (suelen tener la descripción completa y se leen bien):
  `boards.greenhouse.io`, `job-boards.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`,
  `apply.workable.com`, `*.teamtailor.com`, `*.personio.com`.
- Las empresas "deseadas" de `preferencias.md`: busca su página de empleo directamente.

Lanza las búsquedas en paralelo (varias llamadas WebSearch en el mismo turno). Muestra a la
persona en una línea qué estás buscando.

## 2. Selección de candidatas

- Reúne URLs de **ofertas individuales** (no listados ni páginas de búsqueda). Si solo
  encuentras un listado útil, ábrelo con WebFetch para sacar las URLs de las ofertas.
- Elimina duplicados (misma empresa + mismo puesto en varios portales: quédate con la fuente más
  completa, normalmente la página de la propia empresa) y las ya vistas en el historial.
- Descarta de entrada solo lo evidente por el snippet (empresa descartada, ciudad imposible).
  **No descartes por el título**: la decisión se toma leyendo la oferta.
- Objetivo: 20-40 candidatas. Si salen menos de 10, amplía consultas (sinónimos, ciudades
  cercanas, inglés) antes de seguir.

## 3. Análisis en paralelo

Reparte las candidatas en lotes de 5-8 ofertas y lanza un subagente `analista-ofertas` por lote,
todos en el mismo turno. (Si ese tipo de subagente no está disponible, usa `general-purpose` con
`model: sonnet` y dile que lea y siga `.claude/agents/analista-ofertas.md`.) A cada uno pásale:
- las rutas de los `.txt` de 1a (dile que los lea con Read) o la lista de URLs de 1b (con el
  título/empresa del snippet),
- las rutas absolutas de `perfil/perfil.md` y `perfil/preferencias.md`,
- el foco adicional de esta búsqueda, si lo hay.

Cada subagente devuelve una ficha por oferta (formato definido en su archivo). Si alguna oferta
no se pudo leer (portal bloquea el acceso), intenta abrirla tú con el navegador integrado
(`mcp__Claude_Browser__*`, leyendo con `get_page_text`); si tampoco, márcala como
`no verificada` y no la pongas en el top.

## 4. Revisión y ranking

- Revisa la coherencia de las puntuaciones entre lotes (mismos criterios, misma escala de
  `CLAUDE.md`). Corrige si un subagente fue demasiado generoso o severo.
- Ordena por puntuación. Top = ofertas ≥ 55 que pasan filtros duros (máx. 15). Las señales de
  `preferencias.md` con efecto "fuera del top" mandan la oferta al anexo aunque puntúe alto.
- En empates, prioriza: cumple dealbreakers con certeza > más requisitos obligatorios cumplidos >
  oferta más reciente.

## 5. Informe `resultados/AAAA-MM-DD.md`

(Si ya existe uno de hoy, añade sufijo `-2`, `-3`…)

```markdown
# Recomendaciones de empleo — AAAA-MM-DD
_Búsqueda: <consultas resumidas> · Candidatas analizadas: N · Recomendadas: M_

## Resumen
<3-4 líneas: cómo está el mercado para su perfil en esta búsqueda, patrones vistos
(skills que se repiten y le faltan, rangos salariales observados), mejor oportunidad.>

## Top recomendaciones
### 1. <Puesto> — <Empresa> · ⭐ 87/100
📍 <ubicación> · <modalidad> · 💶 <salario o "no publicado"> · 📅 <fecha> · [Ver oferta](<URL>)
_<Empresa en una frase: qué hace, etapa, tamaño>_

**Qué harías:** <1-2 frases: el día a día real, más allá del título>
**Por qué encaja:** <2-3 frases, cada idea uniendo algo de tu CV con algo de la oferta>
**Por qué no encaja:** <1-3 frases: lo que falta o choca con tus preferencias, y si es salvable>
**Para la candidatura:** <1-2 consejos concretos, usando "Cómo presentarse" del perfil>

<details><summary>Detalle de la puntuación</summary>

Puntuación por bloques · señales aprendidas aplicadas · rasgos
</details>

### 2. ...

Cada recomendación se lee sola: nunca escribas "igual que la n.º X" ni compares con otra oferta.

## Tabla resumen
| # | Puesto | Empresa | Encaje | Modalidad | Salario | Enlace |
|---|---|---|---|---|---|---|

## Anexo: descartadas y no recomendadas
| Puesto | Empresa | Motivo | Enlace |
|---|---|---|---|
```

## 6. Guardar las ofertas en la app

Escribe en tu scratchpad un JSON con **todas** las ofertas analizadas (recomendadas, descartadas
y no verificadas), una por objeto, con las claves del modelo Oferta de `app/datos.py`:
`url, empresa, puesto, encaje (número o null), estado_analisis ("recomendada" | "descartada" |
"no verificada"), motivo_descarte, datos (línea de ubicación · modalidad · salario · fecha),
empresa_desc, sencillo {que_harias, por_que_encaja, por_que_no_encaja}, puntuacion, rasgos [..]`.
Las descartadas no se muestran en la app, pero guárdalas para no volver a analizarlas. Impórtalo:

```bash
.venv/bin/python -I app/cli.py importar-ofertas <scratchpad>/fichas.json --informe resultados/AAAA-MM-DD.md
```

Así aparecen en la pestaña **Ofertas** de la app para que la persona decida desde allí.

## 7. Cierre

En el chat, muestra solo el top 5 en formato compacto (puesto, empresa, puntuación, una línea de
por qué, enlace), enlaza el informe completo y dile que puede decidir en la pestaña **Ofertas** de la app
(`Abrir Job Agent.command`) o aquí con `/revisar`. Lo que decida en la app lo aprenderá el
agente en el siguiente `/revisar`.
