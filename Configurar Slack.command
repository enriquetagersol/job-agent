#!/bin/bash
# Guarda las credenciales del bot de Slack en el Llavero de macOS (no quedan en ningún archivo del proyecto).
# Antes, crea la app en https://api.slack.com/apps → «Create New App» → «From a manifest» con slack/manifest.json.
guardar() {  # servicio, cuenta, descripción
  echo; echo "$3"
  echo "El Llavero te lo pedirá dos veces. No se verá lo que pegas."
  security delete-generic-password -s "$1" >/dev/null 2>&1
  security add-generic-password -s "$1" -a "$2" -w || { echo "❌ No se pudo guardar."; read -r -p "Intro para cerrar."; exit 1; }
}
guardar job-agent-slack-bot slack "1/3 · Bot token (OAuth & Permissions → «Bot User OAuth Token», empieza por xoxb-)"
guardar job-agent-slack-app slack "2/3 · App token (Basic Information → App-Level Tokens, con permiso connections:write; empieza por xapp-)"
echo; echo "3/3 · Tu Member ID de Slack (tu perfil → ⋮ → «Copy member ID», empieza por U)"
read -r -p "Member ID: " ID
security delete-generic-password -s job-agent-slack-usuario >/dev/null 2>&1
security add-generic-password -s job-agent-slack-usuario -a slack -w "$ID"
echo; echo "✅ Listo. Cierra y vuelve a abrir Job Agent: el bot se conecta solo al arrancar."
read -r -p "Pulsa Intro para cerrar."
