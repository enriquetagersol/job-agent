#!/bin/bash
# Doble clic para abrir la app de Job Agent en el navegador. Cierra esta ventana para pararla.
cd "$(dirname "$0")"
PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "Primera vez: preparando el entorno (.venv) e instalando dependencias…"
  python3 -m venv .venv && .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r requirements.txt \
    || { echo "❌ No se pudo preparar el entorno. ¿Tienes Python 3 instalado?"; read -r -p "Intro para cerrar."; exit 1; }
fi
# Dependencias añadidas después de crear el entorno (p. ej. Slack)
"$PY" -c "import anthropic, certifi, slack_bolt" 2>/dev/null || .venv/bin/pip install -q -r requirements.txt
if curl -s -o /dev/null "http://127.0.0.1:8765/api/estado"; then
  open "http://127.0.0.1:8765"
else
  "$PY" -I app/servidor.py --puerto 8765 --abrir
fi
