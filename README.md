# job-agent

Aplicación web de búsqueda de empleo que ayuda a comparar ofertas con el perfil del usuario, entender su encaje y llevar un seguimiento de las candidaturas.

## Estado del proyecto

El repositorio contiene únicamente la documentación inicial del producto. La aplicación todavía no está implementada; las funciones descritas a continuación son el alcance previsto.

## Cómo funcionará

El usuario aportará su CV, capacidades y preferencias: roles, ubicaciones, sueldo y condiciones laborales. Con esa información, la aplicación comparará ofertas y ofrecerá:

- Una explicación del encaje entre el perfil y cada oferta.
- Los gaps: requisitos que faltan o que no están acreditados en el perfil.
- Una puntuación de fit del **1 al 10**, con criterios visibles y una justificación comprensible.
- Un tracker para registrar el estado y los próximos pasos de cada oportunidad.

La puntuación orientará la comparación; no será una garantía de contratación. Los criterios previstos incluyen capacidades, experiencia acreditada, rol, ubicación, sueldo y condiciones. La aplicación deberá señalar la información ausente en lugar de asumir que se cumple un requisito. La fórmula y los pesos de la puntuación quedan pendientes de definir.

## Primera versión

1. **Perfil:** recoger el CV (opcional), las capacidades, las preferencias y la experiencia (años) del usuario.
2. **Ofertas** el sistema busca en internet, recupera y analiza sus descripciones completas para compararlas con las capacidades y preferencias del usuario, no evalua slamente titulos o palabras clave.
3. **Recomendaciones:** explicar el encaje y los gaps, mostrar el fit y ayudar a priorizar las ofertas añadidas.
4. **Generar CV:** cada oferta tendrá un botón «Generar CV» que generará un PDF adaptado a esa oferta, basándose exclusivamente en información confirmada del perfil, sin inventar experiencia, capacidades ni logros. El PDF estará disponible para revisión y descarga.
5. **He aplicado:** cada oferta tendrá un botón «He aplicado» para registrar la oferta, su enlace, la fecha de candidatura y su estado. Permitirá asociar la versión exacta del CV utilizado: si existen varias versiones, el usuario elegirá cuál envió. También podrá aportar un CV externo o registrar la candidatura sin CV. Pulsar este botón registrará una candidatura realizada por el usuario; no enviará la candidatura.
6. **Tracker:** mantener el seguimiento de cada oportunidad y candidatura, con su estado, notas y próximos pasos, y la versión exacta del CV utilizado cuando se haya asociado una.

La generación de CV adaptados y el registro de candidaturas forman parte de la primera versión. La búsqueda diaria y el envío de candidaturas desde la aplicación pertenecen a etapas posteriores.

## Etapas posteriores

1. **Búsqueda diaria:** encontrar nuevas ofertas a partir del perfil y las preferencias.
2. **Envío de candidaturas:** preparar la candidatura y enviarla únicamente tras la aprobación explícita del usuario para esa candidatura, después de que pueda revisar la oferta y el contenido que se enviará.

## Privacidad y secretos

- No guardar en Git CV (incluidos los PDFs generados y los CV externos), datos personales, notas privadas del tracker ni candidaturas reales.
- No guardar en Git claves de API, contraseñas, tokens ni otros secretos.
- Utilizar únicamente datos ficticios en ejemplos o futuras pruebas del repositorio.
- Definir el almacenamiento y la protección de los datos personales antes de implementar su recogida. Este README no establece todavía una arquitectura ni un sistema de persistencia.
