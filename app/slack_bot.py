"""Bot de Slack para hablar con Job Agent (mensajes directos o mencionándolo en un canal).

Usa Socket Mode: funciona con la app en tu Mac, sin servidor público. Solo responde a la persona
configurada (SLACK_USUARIO); a cualquier otra le dice que es privado.

Credenciales (mismo orden que la API key): variable de entorno → .env → Llavero de macOS
  SLACK_BOT_TOKEN (xoxb-…)  SLACK_APP_TOKEN (xapp-…)  SLACK_USUARIO (tu Member ID, U…)
En Mac: «Configurar Slack.command». Arranca solo con la app; para probarlo aparte:
  .venv/bin/python -I app/slack_bot.py
Aviso directo:  .venv/bin/python -I app/slack_bot.py --avisar "texto"
"""
import os
import re
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv_ia  # noqa: E402
import agente_chat  # noqa: E402

CLAVES = {"bot": ("SLACK_BOT_TOKEN", "job-agent-slack-bot"),
          "app": ("SLACK_APP_TOKEN", "job-agent-slack-app"),
          "usuario": ("SLACK_USUARIO", "job-agent-slack-usuario")}
estado = {"estado": "sin configurar", "mensaje": ""}


def _config():
    return {k: cv_ia.secreto(env, srv) for k, (env, srv) in CLAVES.items()}


def a_mrkdwn(t):
    """Markdown habitual → formato de Slack."""
    t = re.sub(r"^#{1,6}\s*(.+)$", r"*\1*", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"*\1*", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"<\2|\1>", t)
    return re.sub(r"^(\s*)[-*] ", r"\1• ", t, flags=re.M)


def crear_app(cfg):
    import ssl
    import certifi
    from slack_bolt import App
    from slack_sdk import WebClient
    # El Python de python.org no trae certificados: usamos los de certifi (también para el websocket).
    cliente = WebClient(token=cfg["bot"], ssl=ssl.create_default_context(cafile=certifi.where()))
    app = App(client=cliente)

    def atender(texto, canal, hilo, usuario, client):
        if usuario != cfg["usuario"]:
            client.chat_postMessage(channel=canal, thread_ts=hilo, text="Este asistente es privado. 🙂")
            return
        texto = re.sub(r"<@[A-Z0-9]+>", "", texto or "").strip()
        conv = f"slack:{canal}" + (f":{hilo}" if hilo else "")
        if texto.lower() in ("olvida", "/olvida", "empezar de nuevo", "reset"):
            agente_chat.olvidar(conv)
            client.chat_postMessage(channel=canal, thread_ts=hilo, text="Hecho, empezamos de cero.")
            return
        espera = client.chat_postMessage(channel=canal, thread_ts=hilo, text="_Un momento…_")
        try:
            r = agente_chat.responder(conv, texto)
        except Exception as e:  # noqa: BLE001 - se lo contamos en el chat
            r = f"Algo ha fallado: {e.__class__.__name__}. Inténtalo de nuevo en un rato."
        client.chat_update(channel=canal, ts=espera["ts"], text=a_mrkdwn(r))

    @app.event("message")
    def mensaje_directo(event, client):
        if event.get("channel_type") != "im" or event.get("subtype") or event.get("bot_id"):
            return
        atender(event.get("text"), event["channel"], None, event.get("user"), client)

    @app.event("app_mention")
    def mencion(event, client):
        atender(event.get("text"), event["channel"], event.get("thread_ts") or event["ts"], event.get("user"), client)

    return app


def avisar(texto):
    """Te manda un mensaje directo (lo usa la tarea diaria de avisos del correo)."""
    cfg = _config()
    if not (cfg["bot"] and cfg["usuario"]):
        return "Slack sin configurar: no se envía."
    import ssl
    import certifi
    from slack_sdk import WebClient
    cliente = WebClient(token=cfg["bot"], ssl=ssl.create_default_context(cafile=certifi.where()))
    canal = cliente.conversations_open(users=cfg["usuario"])["channel"]["id"]
    cliente.chat_postMessage(channel=canal, text=a_mrkdwn(texto))
    return "Aviso enviado por Slack."


def arrancar(en_hilo=True):
    """Arranca el bot si está configurado. Devuelve un texto de estado para la consola."""
    cfg = _config()
    falta = [CLAVES[k][0] for k, v in cfg.items() if not v]
    if falta:
        estado.update(estado="sin configurar", mensaje="Falta " + ", ".join(falta))
        return "Slack: sin configurar (opcional)."
    try:
        from slack_bolt.adapter.socket_mode import SocketModeHandler
        handler = SocketModeHandler(crear_app(cfg), cfg["app"])
        handler.connect() if en_hilo else handler.start()
    except Exception as e:  # noqa: BLE001
        estado.update(estado="error", mensaje=str(e))
        return f"Slack: no se pudo conectar ({e})."
    estado.update(estado="conectado", mensaje="")
    return "Slack: conectado. Escríbele a Job Agent por mensaje directo."


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--avisar":
        print(avisar(sys.argv[2]))
    else:
        print(arrancar(en_hilo=False))
