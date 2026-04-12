import os

_IA_PASSWORD = os.getenv("IA_PASSWORD", "")
_GROQ_KEY    = os.getenv("GROQ_API_KEY", "")
_IA_MODEL    = os.getenv("IA_MODEL", "llama-3.3-70b-versatile")
_ADMIN_NICK  = os.getenv("IA_ADMIN_NICK", "Iggy")
_MAX_HISTORY = 20  # mensajes máximos en historial (sin contar system)

_SYSTEM_PROMPT = (
    "Eres el asistente administrador del bot IRC Steve. "
    "Solo recibes órdenes del administrador. "
    "Puedes controlar el bot enviando comandos IRC en crudo: cuando necesites ejecutar uno, "
    "escribe una línea que empiece exactamente por 'IRC: ' seguida del comando "
    "(ejemplos: 'IRC: JOIN #canal', 'IRC: NICK NuevoNick', 'IRC: KICK #canal usuario :motivo', "
    "'IRC: PRIVMSG #canal :mensaje'). "
    "Puedes mezclar texto normal con líneas IRC: en la misma respuesta. "
    "Responde siempre de forma concisa y en el mismo idioma que el administrador."
)

# { nick: {"state": "awaiting_password" | "active", "history": [...]} }
_pm_sessions: dict = {}


def close_pm_session(nick: str) -> bool:
    """Cierra la sesión del nick. Devuelve True si existía."""
    return _pm_sessions.pop(nick, None) is not None


def handle_pm(nick: str, texto: str):
    """
    Gestiona un mensaje privado al bot.
    - Primera vez que escribe: responde solo 'Contraseña'.
    - Si hay sesión awaiting_password: valida la contraseña.
    - Si hay sesión activa: envía a OpenAI y devuelve la respuesta.
    Devuelve str, list[str] o None.
    """
    if nick not in _pm_sessions:
        if nick.lower() != _ADMIN_NICK.lower():
            return None  # ignorar silenciosamente a cualquiera que no sea el admin
        if not _IA_PASSWORD or not _GROQ_KEY:
            return "La IA no está configurada (faltan variables de entorno)."
        _pm_sessions[nick] = {"state": "awaiting_password", "history": []}
        return "Contraseña"

    s = _pm_sessions[nick]

    if s["state"] == "awaiting_password":
        if texto.strip() == _IA_PASSWORD:
            s["state"] = "active"
            s["history"] = [{"role": "system", "content": _SYSTEM_PROMPT}]
            return "Sesión iniciada. Escribe tu consulta."
        else:
            del _pm_sessions[nick]
            return "Contraseña incorrecta."

    if s["state"] == "active":
        return _query_groq(s, texto)

    return None


def _query_groq(session: dict, texto: str):
    try:
        from groq import Groq
        client = Groq(api_key=_GROQ_KEY)

        session["history"].append({"role": "user", "content": texto})

        # Limitar historial: system + últimos _MAX_HISTORY mensajes
        system   = session["history"][0]
        tail     = session["history"][1:][-_MAX_HISTORY:]
        messages = [system] + tail

        response = client.chat.completions.create(
            model=_IA_MODEL,
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )

        reply = response.choices[0].message.content.strip()
        session["history"].append({"role": "assistant", "content": reply})

        lines = [l for l in reply.splitlines() if l.strip()]
        return lines if lines else ["(sin respuesta)"]

    except Exception as e:
        return f"Error al consultar la IA: {e}"
