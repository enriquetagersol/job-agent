#!/bin/bash
# Conecta Job Agent a tu Gmail (leer y poner la etiqueta JOB SEARCH). También sirve para volver a conectarlo
# si Google caduca el permiso. La primera vez necesitas el JSON de un cliente OAuth «App de escritorio» (ver README).
cd "$(dirname "$0")"
if security find-generic-password -s job-agent-gmail-cliente >/dev/null 2>&1; then
  echo "Volviendo a conectar Gmail con el cliente que ya tienes guardado…"
  .venv/bin/python -I app/gmail_lector.py --reconectar || { read -r -p "Pulsa Intro para cerrar."; exit 1; }
else
  JSON=$(grep -l '"installed"' ~/Downloads/client_secret_*.json 2>/dev/null | xargs ls -t 2>/dev/null | head -1)
  if [ -z "$JSON" ]; then
    echo "No encuentro en Descargas un JSON de cliente «App de escritorio» (client_secret_….json)."
    read -r -p "Arrastra aquí el archivo y pulsa Intro: " JSON
    JSON="${JSON//\\ / }"; JSON="${JSON%\"}"; JSON="${JSON#\"}"; JSON="${JSON%% }"
  fi
  echo "Usando: $JSON"
  .venv/bin/python -I app/gmail_lector.py --autorizar "$JSON" || { read -r -p "Pulsa Intro para cerrar."; exit 1; }
  echo "Las credenciales quedan en el Llavero; puedes borrar el JSON de Descargas si quieres."
fi
.venv/bin/python -I app/gmail_lector.py --probar
# Si la app arranca sola al iniciar sesión, la reinicia para que vuelva a vigilar el correo ya mismo
launchctl kickstart -k "gui/$(id -u)/com.jobagent.app" 2>/dev/null && echo "Job Agent reiniciado: ya vuelve a leer tu correo."
echo
read -r -p "Pulsa Intro para cerrar."
