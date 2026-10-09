# job-agent

Aplicación de búsqueda de empleo que compara ofertas con la trayectoria y las preferencias del usuario, explica por qué pueden interesarle y facilita el seguimiento de sus candidaturas.

Actualmente es un **prototipo local en Python y Streamlit para un único usuario**, con persistencia en archivos JSON. No tiene base de datos ni cuentas de múltiples usuarios.

## Objetivo de la primera versión

1. **Perfil del usuario:** datos personales, trayectoria y preferencias, con CV de entrada opcional.
2. **Búsqueda real de ofertas:** encontrar publicaciones y recuperar sus descripciones para analizarlas.
3. **Recomendaciones explicadas y priorizadas:** distinguir interés, coincidencias, gaps confirmados e información pendiente.
4. **CV personalizado para cada oferta:** generar un PDF adaptado, revisable y descargable, exclusivamente desde información confirmada.
5. **Registro «He aplicado»:** registrar una candidatura realizada por el usuario y el CV exacto que utilizó, cuando corresponda.
6. **Tracker de candidaturas:** consultar y actualizar estados, notas y próximos pasos.

Estos seis puntos son el alcance objetivo; su inclusión no significa que ya estén implementados o validados. El CV base es complementario y **no sustituye al CV personalizado por oferta**.

## Estado actual

### Implementado

- Perfil separado en «Datos personales», «Trayectoria profesional» y «Preferencias de búsqueda», con edición individual y completa, guardado y cancelación.
- Experiencias, formación y proyectos editables y eliminables; skills confirmadas e idiomas con niveles.
- Validaciones de campos obligatorios y fechas. Las entradas antiguas incompletas se conservan como pendientes.
- Una lista de skills confirmadas común a la búsqueda, evaluación y CV; propuestas de IA con aceptación explícita, control de duplicados, eliminación y propuestas de fusión con confirmación.
- Búsqueda con OpenAI y Tavily, recuperación de descripciones, eliminación de duplicados y hasta cinco recomendaciones explicadas, con evidencias consultables.
- «Mejorar mi perfil»: preguntas generales, confirmación y persistencia de respuestas, edición y eliminación. «Actualizar recomendaciones» reevalúa ofertas existentes.
- CV base en PDF, generado localmente, con vista previa y descarga. Actualmente no hay editor de texto del borrador en la interfaz.
- Persistencia privada del perfil, evaluaciones, fuentes disponibles y decisiones sobre skills; diagnóstico local sin claves ni datos personales.

### Pendiente de validar

**El flujo de mejora progresiva del perfil todavía no se ha probado de extremo a extremo.** Falta comprobar con uso real la secuencia completa de preguntas, respuestas confirmadas, reapertura de la aplicación y reevaluación con el perfil enriquecido, sin nueva búsqueda web.

También queda validar de forma continuada la calidad de las explicaciones, la relevancia de las propuestas de skills, la recuperación de distintas páginas de empleo y la vista previa y descarga del CV en los navegadores utilizados.

Existen pruebas automatizadas de reglas, persistencia e interacción. Las pruebas con servicios simulados no validan por sí solas el flujo completo con servicios reales. Se han realizado pruebas puntuales de búsqueda real y revisión visual de PDFs con datos ficticios. **Programado no equivale a validado de extremo a extremo.**

### Pendiente de implementar

- Incorporación de un CV de entrada opcional al perfil.
- CV personalizado por oferta, registro «He aplicado» y tracker, en el orden indicado más abajo.
- Funciones de etapas posteriores: base de datos, cuentas de múltiples usuarios, búsqueda diaria, envío de candidaturas y plantillas visuales de CV.

## Perfil y trayectoria

El perfil recoge:

- **Datos personales:** nombre, apellidos, teléfono, email y LinkedIn. No bastan por sí solos para iniciar una búsqueda.
- **Experiencia profesional:** empresa, puesto, fechas, responsabilidades y, opcionalmente, logros y herramientas. Se permiten varios empleos, incluidos los anteriores al actual.
- **Formación:** institución, estudios, cursos o certificaciones, fechas y, opcionalmente, contenidos y proyectos.
- **Proyectos:** nombre, descripción, contribución personal, herramientas y enlace opcional.
- **Skills e idiomas:** una única lista de skills confirmadas y niveles de idioma declarados.
- **Preferencias:** puestos objetivo, ubicaciones, modalidades, salario mínimo bruto anual, preferencias e importancias y «¿Qué buscas?». Se mantiene la exclusión opcional de la empresa actual; si hay varios empleos actuales, se puede elegir cuál excluir.

Cada campo o bloque puede editarse individualmente con «Guardar» y «Cancelar». Las experiencias, estudios y proyectos tienen sus propios editores. Guardar un bloque conserva los demás datos; cancelar mantiene el valor anterior. Editar o guardar no inicia búsquedas ni llamadas al modelo.

Para guardar una experiencia se exigen empresa, puesto, inicio y responsabilidades. Para formación se exigen institución, estudios e inicio. Ambas requieren fecha de fin salvo que sigan en curso, y rechazan fechas incoherentes. No se convierten rangos antiguos de años en empleos inventados.

Las skills manuales se consideran confirmadas. Las sugeridas por IA solo se incorporan al aceptarlas; se puede editar su nombre antes de añadirlas. Se evitan duplicados por mayúsculas o espacios y las posibles equivalencias se fusionan solo tras confirmación. El límite es de **10 skills confirmadas**; las propuestas pendientes no consumen huecos. Cualquier skill puede eliminarse, conservando internamente sus fuentes. Las habilidades descartadas o eliminadas no deben volver a proponerse con la misma evidencia.

«Proponer skills» está en el resumen de skills y requiere contenido guardado sobre tareas, conocimientos o herramientas. Solo su pulsación inicia esa llamada al modelo. No se deducen skills del título de unos estudios. Se distingue aprendizaje en formación, aplicación en proyectos y trabajo profesional: un curso no acredita dominio avanzado ni experiencia laboral.

## Mejora progresiva del perfil

«Mejorar mi perfil» reúne hasta tres preguntas generales relevantes y sin duplicados, fuera de las tarjetas de ofertas. El usuario puede responderlas u omitirlas. Antes de guardar una respuesta se muestra la información propuesta y se pide confirmación.

Las respuestas confirmadas enriquecen el perfil, persisten entre sesiones y pueden revisarse, editarse o eliminarse. No se vuelven a preguntar datos ya respondidos o documentados. Esta persistencia es **información guardada del usuario, no entrenamiento del modelo**.

Las dudas sobre el usuario se separan de las relativas a una oferta, como salario, requisitos no documentados o actividad de la vacante. Estas últimas permanecen en la oferta correspondiente.

«Actualizar recomendaciones» llama al modelo para reevaluar ofertas existentes con el perfil actualizado, reutilizando las descripciones locales y **sin repetir la búsqueda web ni la extracción con Tavily**. Algunos resultados antiguos solo conservan fragmentos verificados: la reevaluación queda limitada a esa evidencia y no completa lo que falta con suposiciones. El flujo completo sigue pendiente de validación de extremo a extremo.

## Búsqueda y recomendaciones

«Buscar ofertas» es el único inicio de una nueva búsqueda. Basta al menos un dato significativo guardado en la trayectoria o las preferencias; no se exige un puesto objetivo. Los contactos, valores predeterminados, entradas vacías y selectores sin elección explícita no son suficientes. Un perfil parcial permite buscar sin inventar criterios ausentes.

El agente carga `instrucciones_agente.md`, utiliza tool calling y limita cada búsqueda a **diez llamadas a herramientas de búsqueda y extracción**. Prioriza las publicaciones originales de empresas o sus sistemas de empleo; los portales sirven para descubrir ofertas. No se evalúan únicamente títulos ni fragmentos del buscador: se requiere una descripción recuperada con responsabilidades y requisitos. Se descartan páginas sin evidencia suficiente, se evitan duplicados y no se inventan resultados para completar cinco.

La interfaz no muestra una nota de fit del 1 al 10 ni una etiqueta global de encaje. Mantiene una ordenación calculada en Python según las preferencias y las dimensiones evaluadas por el modelo con evidencia: relevancia del puesto, capacidades, experiencia, idiomas, ubicación, modalidad y salario.

Cada oferta presenta empresa, puesto, ubicación, enlace y explicaciones de:

- Motivos de interés, separados de la cualificación.
- Requisitos que cumple y coincidencias parciales.
- Gaps confirmados.
- Información pendiente de confirmar sobre la oferta.

Las evidencias pueden consultarse en «Ver detalles». Declarar una skill no confirma dominio ni experiencia laboral. «¿Qué buscas?» orienta el interés, sin convertirse en capacidades confirmadas. La ausencia de información no se trata como incumplimiento: se señala como «No documentado» o mediante una pregunta concreta. Si no se confirma que la vacante sigue activa, se indica.

Las preferencias ordenan oportunidades; no son filtros excluyentes automáticos. Ya no hay condiciones imprescindibles en la interfaz ni en el flujo de evaluación. No se comparan salarios de monedas distintas sin conversión fiable ni se deduce un salario anual si faltan datos.

## CV base complementario

«Generar CV base» prepara un borrador en PDF desde los datos personales y la trayectoria confirmada, para revisarlo mediante la vista previa y descargarlo. Actualmente no hay un borrador de texto editable en la interfaz: para corregir los datos se edita el perfil y se vuelve a generar el PDF.

No incorpora salario, ubicaciones, modalidad ni condiciones de búsqueda, ni inventa logros, fechas, títulos o niveles de dominio. La descripción inicial puede recoger fragmentos de intereses profesionales de «¿Qué buscas?», identificados como aspiraciones y nunca como experiencia adquirida. Esta es la única utilización de ese campo en el CV base.

Se requieren nombre y apellidos, email con formato válido y al menos una experiencia, formación o proyecto completo. Un proyecto completo exige nombre, descripción y contribución personal. Teléfono y enlaces son opcionales. Las entradas incompletas se conservan en el perfil, pero se omiten del CV. El bloqueo del CV no impide buscar ofertas.

El PDF se genera localmente en memoria. No se adapta todavía a una oferta y no sustituye al próximo desarrollo de CV personalizado. Las plantillas visuales quedan pospuestas.

## Próximas funcionalidades por programar

En este orden:

1. **CV personalizado:** botón «Generar CV» en cada oferta. Preparar un PDF adaptado exclusivamente desde información confirmada, sin inventar experiencia, skills, fechas ni logros; permitir revisión y descarga.
2. **He aplicado:** registrar oferta, enlace, fecha y estado de una candidatura realizada por el usuario. Asociar la versión exacta del CV enviado; si hay varias, el usuario elige cuál utilizó. Permitir un CV externo o registrar sin CV. **No envía candidaturas.**
3. **Tracker:** consultar y actualizar estados, notas y próximos pasos. Conservar el CV histórico asociado sin alterarlo cuando cambie el perfil.

## Etapas posteriores

- Base de datos y cuentas de múltiples usuarios, con almacenamiento y acceso adecuados a los datos personales.
- Búsqueda diaria de nuevas ofertas.
- Plantillas visuales de CV.
- Envío de candidaturas desde la aplicación. Cualquier envío, incluido uno automatizado, requerirá aprobación explícita del usuario para esa candidatura, tras revisar la oferta y el contenido que se enviará. El prototipo actual no envía candidaturas ni contacta con empresas.

## Ejecutar la interfaz local

Con las dependencias de `requirements.txt` instaladas en `.venv`, desde la carpeta del repositorio:

```bash
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Abre la dirección local que muestra la terminal, habitualmente `http://127.0.0.1:8501`.

Las claves `OPENAI_API_KEY` y `TAVILY_API_KEY` se configuran manualmente en `.env`. `OPENAI_MODEL` permite cambiar el modelo predeterminado `gpt-6-luna`. Las búsquedas y propuestas de skills utilizan servicios externos; la reevaluación utiliza OpenAI con la evidencia guardada. La generación del CV base es local.

Guarda los datos antes de iniciar una acción. Editar o guardar no llama a servicios externos. El perfil se conserva en `perfil.json`; las evaluaciones, fuentes disponibles y diagnósticos se guardan en `.datos/`, incluyendo `.datos/evaluaciones.json`. Los resultados anteriores no se actualizan automáticamente al cambiar el perfil: hay que reevaluarlos o iniciar una nueva búsqueda.

## Privacidad y secretos

- No subir a Git claves de API, contraseñas, tokens ni `.env`.
- No subir perfiles, resultados reales, descripciones y respuestas personales, candidaturas, notas privadas ni CV, incluidos PDFs generados y documentos externos.
- Mantener `perfil.json`, `.datos/`, `.env`, el entorno virtual y los PDFs fuera de Git mediante `.gitignore`. Revisar también cualquier archivo nuevo antes de incluirlo en un commit.
- Utilizar únicamente datos ficticios en ejemplos y pruebas del repositorio.
- La persistencia actual es local en JSON; no implica una cuenta, sincronización ni entrenamiento del modelo. Al buscar o reevaluar se comparte con los servicios configurados la información necesaria para la acción.

El prototipo está orientado a uso personal local. La base de datos, el acceso para múltiples usuarios y el envío de candidaturas se abordarán en etapas posteriores.
