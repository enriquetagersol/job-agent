---
name: perfil
description: Lee el CV de la carpeta cv/ y construye un perfil profesional estructurado (experiencia, años, tareas, empresas, proyectos, skills) en perfil/perfil.md. Úsalo cuando la persona pida analizar, leer o actualizar su CV o su perfil.
---

# /perfil — Entender el CV

Objetivo: convertir el CV en un perfil estructurado y fiable que sirva para comparar con ofertas.

## 1. Localizar el CV

- Busca en `cv/` archivos `.pdf`, `.docx`, `.md`, `.txt` (ignora `.gitkeep`). También vale un
  archivo o texto que la persona haya adjuntado en el chat, o una ruta que indique.
- Si no hay nada, pide que deje el CV en la carpeta `cv/` o lo pegue en el chat, y para.
- Si hay varios (p. ej. CV en español e inglés, o un perfil de LinkedIn exportado), léelos
  todos y combínalos; si se contradicen, pregunta.
- PDF: usa la herramienta Read (con `pages` si tiene más de 10 páginas). DOCX: extrae el texto
  (p. ej. `textutil -convert txt -stdout archivo.docx` en macOS).

## 2. Extraer e interpretar

No te limites a copiar: **interpreta**.

- **Experiencia**: para cada puesto → empresa, sector de la empresa, tamaño aproximado si se
  deduce, cargo, fechas, duración en meses, ubicación/modalidad, tareas y logros (con cifras si
  las hay), tecnologías usadas en ese puesto, y nivel de responsabilidad (individual, lidera
  personas, gestiona presupuesto/clientes…).
- **Años de experiencia**: total y **por función** (p. ej. 4,5 años en análisis de datos, 2 en
  gestión de equipos). Hoy es la fecha actual del sistema; "actualidad" cuenta hasta hoy. No
  sumes dos veces periodos solapados.
- **Seniority estimado**: junior / mid / senior / lead / manager, con una frase que lo justifique.
- **Skills**: agrupa en técnicas (lenguajes, herramientas, plataformas), de dominio/negocio,
  metodologías, idiomas (con nivel) y blandas. Para cada skill técnica indica **años de uso y
  dónde se usó** (deducido de los puestos/proyectos). Marca como `declarada` la que solo aparece
  en una lista de skills sin evidencia de uso.
- **Proyectos**: nombre, contexto (laboral, personal, académico), qué hizo, tecnologías, resultado.
- **Formación y certificaciones**.
- **Lectura entre líneas**: trayectoria (hacia dónde evoluciona), puntos fuertes diferenciales,
  posibles huecos o señales a explicar (gaps temporales, cambios frecuentes), y **puestos y
  títulos alternativos** a los que encaja (sinónimos y variantes en español e inglés). Esto
  último alimenta las búsquedas.

## 3. Validar con la persona

Antes de guardar, muestra un resumen corto (5-8 líneas: seniority, años por función, top skills,
títulos objetivo) y pregunta solo lo que sea ambiguo o falte de verdad (fechas sin mes, tecnologías
de un puesto no especificadas, nivel de idiomas…). Usa AskUserQuestion si son pocas preguntas
cerradas. No preguntes lo que ya está claro.

## 4. Guardar `perfil/perfil.md`

Usa exactamente esta estructura (rellena con lo extraído; `desconocido` si falta):

```markdown
# Perfil profesional
_Generado el AAAA-MM-DD a partir de: <archivos>_

## Resumen
<3-4 frases: quién es profesionalmente, seniority, especialidad, diferencial>

## Datos clave
- Experiencia total: X años (Y meses)
- Seniority estimado: <nivel> — <justificación>
- Ubicación actual: <ciudad, país>
- Idiomas: <idioma (nivel)>, ...

## Años por función
| Función | Años | Dónde |
|---|---|---|

## Experiencia
### <Cargo> — <Empresa> (<sector>, <tamaño>)
- Fechas: MM/AAAA – MM/AAAA (N meses) · <ubicación/modalidad>
- Responsabilidad: <nivel>
- Tareas: ...
- Logros: ...
- Tecnologías: ...

## Proyectos
### <Nombre> (<laboral|personal|académico>)
...

## Skills
| Skill | Tipo | Años | Evidencia | Nivel estimado |
|---|---|---|---|---|

## Formación y certificaciones
...

## Lectura entre líneas
- Trayectoria: ...
- Puntos fuertes diferenciales: ...
- Posibles huecos / a explicar: ...

## Títulos objetivo para búsqueda
- ES: ...
- EN: ...
- Palabras clave técnicas: ...
```

## 5. CV maestro
Crea o actualiza `cv/cv_maestro.json` (formato: el propio archivo si existe) con el texto del CV
tal cual, más el contenido real confirmado que no estaba en el CV, marcado con "(extra)". Es la
base de `/adaptar-cv`. Si ya existe, no borres lo que haya añadido la persona: solo añade o
corrige lo que cambie en el CV nuevo.

Al terminar, di en 2-3 líneas lo más relevante que has entendido y sugiere el siguiente paso:
`/preferencias` (o `/buscar` si ya existen preferencias).
