#!/bin/bash
# Deshace «Arrancar al iniciar sesión.command»: Job Agent deja de arrancar solo (y se cierra ahora).
ID="com.jobagent.app"
launchctl bootout "gui/$(id -u)/$ID" 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/$ID.plist"
echo "✅ Job Agent ya no arrancará solo. Ábrelo cuando quieras con «Abrir Job Agent.command»."
read -r -p "Pulsa Intro para cerrar."
