#!/bin/bash
# Hace que Job Agent arranque solo al iniciar sesión en el Mac (y se reinicie si se cierra por un error).
# Así el bot de Slack y la vigilancia del correo funcionan sin abrir nada. Para quitarlo:
# «Quitar arranque automático.command».
cd "$(dirname "$0")"
DIR="$(pwd)"
ID="com.jobagent.app"
PLIST="$HOME/Library/LaunchAgents/$ID.plist"
if [ ! -x "$DIR/.venv/bin/python" ]; then
  echo "Primero abre la app una vez con «Abrir Job Agent.command» (prepara el entorno)."; read -r -p "Intro para cerrar."; exit 1
fi
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$ID</string>
  <key>ProgramArguments</key><array>
    <string>$DIR/.venv/bin/python</string><string>-I</string>
    <string>$DIR/app/servidor.py</string><string>--puerto</string><string>8765</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/JobAgent.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/JobAgent.log</string>
</dict></plist>
PL
# Si la app ya está abierta a mano, se cierra para que la gestione el Mac
lsof -ti tcp:8765 | xargs kill 2>/dev/null; sleep 1
launchctl bootout "gui/$(id -u)/$ID" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" && echo "✅ Job Agent arrancará solo al iniciar sesión. Ya está funcionando: http://127.0.0.1:8765" \
  || echo "❌ No se pudo activar."
read -r -p "Pulsa Intro para cerrar."
