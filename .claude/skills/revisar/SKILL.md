---
name: revisar
description: Presenta las ofertas recomendadas una a una en lenguaje sencillo (qué harías, por qué encaja, por qué no encaja), recoge si a la persona le interesan o no y por qué, y aprende de sus decisiones actualizando perfil/preferencias.md. Úsalo después de /buscar, o cuando la persona quiera valorar ofertas o diga que algo le gusta o no.
---

# /revisar — Decidir oferta a oferta y aprender

Objetivo: que la persona decida rápido con información clara, y que cada decisión haga mejor la
siguiente búsqueda.

## 1. Preparar

- **Primero, decisiones tomadas en la app:** `.venv/bin/python -I app/cli.py ofertas --sin-aprender`.
  Si hay, no las vuelvas a preguntar: pasa directamente al paso 4 (Aprender) con ellas y, si la
  persona solo quería eso, termina ahí.
- Ofertas por decidir: `.venv/bin/python -I app/cli.py ofertas --pendientes` (ya excluye las decididas;
  comprueba con `.venv/bin/python -I app/cli.py candidaturas` que no haya aplicado ya por otra vía).
  Si la persona indica un informe concreto, filtra por su campo `informe`.
- Si una oferta no tiene `sencillo` ni `rasgos`, créalos tú a partir de su
  contenido (formato y vocabulario de rasgos en `.claude/agents/analista-ofertas.md`).
- Di cuántas ofertas hay por revisar. Si son más de 8, propón empezar por las 8 de mayor encaje.

## 2. Presentar y preguntar (en tandas de 3-4)

Para cada oferta de la tanda, muestra una tarjeta breve:

```
### 1. <Puesto> — <Empresa> · ⭐ <encaje>/100
<ubicación> · <modalidad> · <salario> · [Ver oferta](<url>)

**Qué harías:** ...
**Por qué encaja:** ...
**Por qué no encaja:** ...
```

Usa los campos `sencillo.que_harias`, `por_que_encaja` y `por_que_no_encaja` de la oferta. Cada
tarjeta se lee sola: nunca hagas referencia a otra oferta.

Sin jerga, sin repetir lo obvio, máximo ~10 líneas por tarjeta.

Después, un solo AskUserQuestion con una pregunta por oferta (máx. 4), header = empresa:
- "Sí, me interesa" — pasa a sus candidaturas como «Por aplicar».
- "No"

Solo hay dos respuestas (igual que en la app). Si dice que ya aplicó, márcala como "Sí" y luego
mueve la candidatura a enviada con `app/cli.py actualizar <id_cand> --estado enviada`.

Recuérdale que puede escribir el motivo en las notas.

Para cada "No me interesa" sin motivo en las notas, haz una segunda pregunta (multiSelect) con
**motivos concretos de esa oferta**, sacados de sus rasgos y datos. Ejemplos: "Tiene cuota de
ventas", "Viajes del 50 %", "Presencial en Dublín", "Pide 6+ años: no llego", "Demasiado técnico
para mí", "No me atrae el producto/sector", "Muy parecido a mi trabajo actual". Máximo 4 opciones;
"Other" queda para lo demás.

Para las "Me interesa", si no dio motivo, una pregunta opcional (multiSelect) por tanda:
"¿Qué es lo que más te atrae de las que te interesan?", con opciones sacadas de sus rasgos
comunes.

## 3. Registrar

Registra cada decisión con la CLI (usa sus palabras como motivo):

```bash
.venv/bin/python -I app/cli.py decidir <id_oferta> "<interesa|no interesa>" --motivo "..."
```

`interesa` crea sola la candidatura `por aplicar` (si no estaba ya enlazada). Si una oferta trae
`nota_previa` (la había dejado para más adelante), muéstrala en la tarjeta.

## 4. Aprender

Al terminar (o si la persona quiere parar), analiza **todas** las decisiones
(`.venv/bin/python -I app/cli.py ofertas` → las que tienen `decision`), no solo las de hoy, incluidas las
tomadas en la app:

1. **Reglas explícitas.** Si la persona dice algo como regla ("nada de cuota", "nunca más de X
   viajes"), es candidata a dealbreaker aunque solo haya pasado una vez.
2. **Patrones por rasgo.** Para cada rasgo, cuenta cuántas veces aparece en `interesa`
   y cuántas en `no interesa`:
   - ≥ 2 rechazos con el mismo motivo y ningún interés → **señal negativa**.
   - ≥ 2 intereses y ningún rechazo → **señal positiva**.
   - Si una señal existente se contradice con decisiones nuevas, propón suavizarla o quitarla.
3. **Desajustes de puntuación.** Si rechaza ofertas con encaje ≥ 70 o le interesan ofertas < 60,
   busca qué bloque de la escala lo explica y propón ajustar los pesos (deben sumar 100).

Propón los cambios en una lista corta, en lenguaje llano, con la evidencia ("Has descartado 3
ofertas con cuota de ventas → bajarlas 8 puntos"). Pide el visto bueno con un AskUserQuestion
(multiSelect si hay varios cambios). Aplica solo lo aprobado en `perfil/preferencias.md`:

- Señales → tabla de la sección `## Señales aprendidas` (créala si no existe, justo antes de
  `## Aprendido de su feedback`):

  ```markdown
  ## Señales aprendidas
  _Las aplica el analista al puntuar "Encaje con preferencias". Intensidad: +/-3 leve, +/-6 media, +/-10 fuerte._

  | Señal (rasgo o descripción) | Efecto | Evidencia | Desde |
  |---|---|---|---|
  | con-cuota | -10 | 3 rechazos (Notion, ...) | 2026-10-17 |
  ```

- Dealbreakers nuevos → sección de dealbreakers.
- Pesos → tabla de prioridades.
- Una línea fechada en `## Aprendido de su feedback` resumiendo qué ha cambiado.

Al final, aunque no se haya aprobado ningún cambio, marca como aprendidas las decisiones que has
analizado: `.venv/bin/python -I app/cli.py aprendidas <id> <id> ...`. Así la app deja de avisar de ellas.

## 5. Cerrar

En 2-3 líneas: cuántas le interesan (con enlace), qué ha aprendido el agente y qué cambiará en
la próxima `/buscar`. Si hay ofertas marcadas como `interesa`, ofrece ayudar con la candidatura
(CV adaptado, carta, mensaje a un contacto) usando "Cómo presentarse" de `perfil/perfil.md`.
