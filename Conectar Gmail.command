#!/bin/bash
# Conecta Job Agent a tu Gmail con permiso de SOLO LECTURA (para «revisa mi correo» en Slack).
# Necesitas el JSON de un cliente OAuth «App de escritorio» de Google Cloud (ver README).
cd "$(dirname "$0")"
JSON=$(grep -l '"installed"' ~/Downloads/client_secret_*.json 2>/dev/null | xargs ls -t 2>/dev/null | head -1)
if [ -z "$JSON" ]; then
  echo "No encuentro en Descargas un JSON de cliente «App de escritorio» (client_secret_….json)."
  read -r -p "Arrastra aquí el archivo y pulsa Intro: " JSON
  JSON="${JSON//\\ / }"; JSON="${JSON%\"}"; JSON="${JSON#\"}"; JSON="${JSON%% }"
fi
echo "Usando: $JSON"
.venv/bin/python -I app/gmail_lector.py --autorizar "$JSON" && .venv/bin/python -I app/gmail_lector.py --probar
echo; echo "Las credenciales quedan en el Llavero; puedes borrar el JSON de Descargas si quieres."
read -r -p "Pulsa Intro para cerrar."
