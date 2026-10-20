#!/bin/bash
# Guarda las credenciales del bot de Slack en el Llavero de macOS (no quedan en ningún archivo del proyecto).
# Antes, crea la app en https://api.slack.com/apps → «Create New App» → «From a manifest» con slack/manifest.json.
# Comprueba cada dato al pegarlo: si no es el correcto, te dice cuál toca y te lo vuelve a pedir.

pedir() {  # servicio, prefijo, título, dónde encontrarlo, ¿oculto?
  local servicio="$1" prefijo="$2" titulo="$3" donde="$4" oculto="$5" valor
  while true; do
    echo; echo "$titulo"; echo "   Dónde: $donde"
    if [ "$oculto" = "si" ]; then
      read -r -s -p "   Pégalo aquí (no se verá) y pulsa Intro: " valor; echo
    else
      read -r -p "   Pégalo aquí y pulsa Intro: " valor
    fi
    valor="$(echo "$valor" | tr -d '[:space:]')"
    if [[ "$valor" == "$prefijo"* ]] && [ ${#valor} -gt 8 ]; then
      security delete-generic-password -s "$servicio" >/dev/null 2>&1
      security add-generic-password -s "$servicio" -a slack -w "$valor" && echo "   ✅ Guardado." && return
      echo "   ❌ No se pudo guardar en el Llavero. Vuelve a intentarlo."
    elif [ -z "$valor" ]; then
      echo "   ⚠️  No has pegado nada."
    else
      echo "   ⚠️  Eso no es lo que toca: debería empezar por «$prefijo» y empieza por «${valor:0:5}…»."
      [[ "$valor" == xoxb-* ]] && echo "      (Eso es el token del bot: lo pediré en su paso.)"
      [[ "$valor" == xapp-* ]] && echo "      (Eso es el token de la app: lo pediré en su paso.)"
      [[ "$valor" == U* ]] && echo "      (Eso parece tu ID de miembro: lo pediré en el último paso.)"
    fi
  done
}

echo "Configurar Slack para Job Agent (3 datos). Copia cada uno justo antes de pegarlo."
pedir job-agent-slack-bot xoxb- "1/3 · Bot token (empieza por xoxb-)" \
  "api.slack.com/apps → tu app → Install App (u OAuth & Permissions) → «Bot User OAuth Token»" si
pedir job-agent-slack-app xapp- "2/3 · App token (empieza por xapp-)" \
  "api.slack.com/apps → tu app → Basic Information → App-Level Tokens → pulsa el token" si
pedir job-agent-slack-usuario U "3/3 · Tu ID de miembro (empieza por U)" \
  "Slack → tu foto → Perfil → ⋮ → «Copiar ID de miembro»" no
echo; echo "✅ Listo. Job Agent se reiniciará solo en unos segundos para conectarse a Slack."
launchctl kickstart -k "gui/$(id -u)/com.jobagent.app" >/dev/null 2>&1
read -r -p "Pulsa Intro para cerrar."
