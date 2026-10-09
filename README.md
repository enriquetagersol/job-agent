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

1. **Perfil:** recoger el CV, las capacidades y las preferencias del usuario.
2. **Ofertas manuales:** permitir añadir ofertas para analizarlas y compararlas.
3. **Recomendaciones:** explicar el encaje y los gaps, mostrar el fit y ayudar a priorizar las ofertas añadidas.
4. **Tracker:** mantener el seguimiento de cada oportunidad y candidatura, con su estado, notas y próximos pasos.

Esta versión se centrará en las ofertas añadidas manualmente. La búsqueda automática, la adaptación del CV y el envío de candidaturas pertenecen a etapas posteriores.

## Etapas posteriores

1. **Búsqueda diaria:** encontrar nuevas ofertas a partir del perfil y las preferencias.
2. **Adaptación del CV:** proponer ajustes para una oferta concreta sin inventar experiencia, capacidades ni logros.
3. **Envío de candidaturas:** preparar la candidatura y enviarla únicamente tras la aprobación explícita del usuario para esa candidatura, después de que pueda revisar la oferta y el contenido que se enviará.

## Privacidad y secretos

- No guardar en Git CV, datos personales, notas privadas del tracker ni candidaturas reales.
- No guardar en Git claves de API, contraseñas, tokens ni otros secretos.
- Utilizar únicamente datos ficticios en ejemplos o futuras pruebas del repositorio.
- Definir el almacenamiento y la protección de los datos personales antes de implementar su recogida. Este README no establece todavía una arquitectura ni un sistema de persistencia.
