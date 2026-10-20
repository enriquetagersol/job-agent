#!/bin/bash
# Guarda tu API key de Claude en el Llavero de macOS (no queda en ningún archivo del proyecto).
# La app la lee de ahí para crear CVs adaptados.
SERVICIO="job-agent-anthropic"
echo "El Llavero te pedirá la clave dos veces («password data for new item» y «retype»)."
echo "Pega tu API key de Claude (empieza por sk-ant-) y pulsa Intro. No se verá lo que pegas."
echo
security delete-generic-password -s "$SERVICIO" >/dev/null 2>&1
if security add-generic-password -s "$SERVICIO" -a anthropic -w; then
  echo; echo "✅ Guardada en el Llavero. Vuelve a la app y recarga la página."
else
  echo; echo "❌ No se pudo guardar. Vuelve a intentarlo."
fi
read -r -p "Pulsa Intro para cerrar."
