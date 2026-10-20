---
name: preferencias
description: Entrevista a la persona para entender qué busca en su próximo empleo (rol, condiciones, empresa, cultura, dealbreakers) y lo guarda en perfil/preferencias.md. Úsalo cuando quiera definir o cambiar sus preferencias, o diga qué busca o qué no quiere.
---

# /preferencias — Conocer a la persona

Objetivo: saber qué quiere de verdad, distinguiendo lo innegociable de lo deseable, para poder
filtrar y ponderar ofertas.

## Antes de empezar

- Lee `perfil/perfil.md` si existe: úsalo para hacer preguntas concretas ("Llevas 3 años en
  consultoría, ¿quieres seguir en consultoría o pasar a producto?") y proponer opciones realistas.
- Si ya existe `perfil/preferencias.md`, muéstralo resumido y pregunta qué quiere cambiar en
  lugar de repetir la entrevista entera.

## Entrevista

Ve bloque a bloque, no todo de golpe. Usa AskUserQuestion para preguntas cerradas (con opciones
adaptadas a su perfil, y `multiSelect` cuando aplique) y texto libre para las abiertas. Cuando
una respuesta sea vaga ("algo con buen ambiente"), repregunta una vez para concretarla.

1. **El rol**: qué puestos quiere (propón los títulos objetivo del perfil), qué quiere hacer en el
   día a día y qué quiere dejar de hacer, nivel buscado (mismo, subir, gestionar personas o no),
   ¿abierto a un cambio de función o sector?
2. **Ubicación y modalidad**: ciudad/es, remoto / híbrido (cuántos días) / presencial, tiempo
   máximo de desplazamiento, ¿reubicación?, ¿trabajar en remoto para empresas de otros países?
3. **Condiciones**: salario bruto anual mínimo aceptable y objetivo, tipo de contrato (indefinido,
   freelance, temporal), jornada, beneficios que le importan, disponibilidad de incorporación.
4. **Empresa**: sector(es) que le atraen y que evita, tamaño (startup, scale-up, pyme,
   multinacional, consultora, sector público), empresas concretas que le gustaría o que descarta.
5. **Cultura y crecimiento**: qué valora (aprendizaje, estabilidad, impacto, flexibilidad,
   buen liderazgo, propósito…), qué le hizo querer cambiar de su empleo actual o anterior.
6. **Idiomas de trabajo**: en qué idiomas está dispuesta a trabajar.
7. **Dealbreakers**: pregunta explícitamente "¿Qué haría que descartaras una oferta sin dudarlo?"
8. **Prioridades**: pide que ordene los bloques (rol, condiciones, empresa, cultura, ubicación)
   o que elija los 3 factores que más pesan. Tradúcelo en pesos para la puntuación.

## Guardar `perfil/preferencias.md`

```markdown
# Preferencias de búsqueda
_Actualizado el AAAA-MM-DD_

## Resumen en una frase
<qué busca, en sus palabras>

## Dealbreakers (filtros duros)
- ...

## Rol
- Puestos objetivo: ...
- Quiere hacer: ...
- Quiere evitar: ...
- Nivel: ...
- Abierto a cambio de función/sector: sí/no — ...

## Ubicación y modalidad
- Ciudades: ...
- Modalidad: ...
- Reubicación: ...
- Remoto para el extranjero: ...

## Condiciones
- Salario mínimo aceptable: X € brutos/año
- Salario objetivo: X € brutos/año
- Contrato: ...
- Beneficios valorados: ...
- Disponibilidad: ...

## Empresa
- Sectores preferidos: ...
- Sectores a evitar: ...
- Tamaño/tipo: ...
- Empresas deseadas: ...
- Empresas descartadas: ...

## Cultura y crecimiento
- ...

## Idiomas de trabajo
- ...

## Prioridades y pesos
| Bloque | Peso |
|---|---|
| Requisitos técnicos | 30 |
| Experiencia y seniority | 20 |
| Funciones del puesto | 20 |
| Encaje con preferencias | 20 |
| Condiciones | 10 |
_(Ajusta los dos últimos bloques y, si hace falta, Funciones según sus prioridades; deben sumar 100.)_

## Señales aprendidas
_(Las propone /revisar)_

## Aprendido de su feedback
_(Lo rellena /revisar)_
```

Cierra con un resumen de 3 líneas de lo que has entendido y sugiere `/buscar`.
