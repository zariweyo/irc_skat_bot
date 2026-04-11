import json
import random
import threading
from pathlib import Path

DESCRIPTION = "Inicia una partida del ahorcado multijugador. Adivina la palabra letra a letra."

MAX_ERRORES   = 6
TIMEOUT_SECS  = 60

_timers: dict[str, threading.Timer] = {}  # channel -> Timer activo

def cancel_timer(channel: str) -> None:
    t = _timers.pop(channel, None)
    if t:
        t.cancel()

def _on_timeout(channel: str) -> None:
    import bus
    _timers.pop(channel, None)
    bus.emit(channel, {"msg": "__timeout__", "nick": ""})

def _on_restart(channel: str) -> None:
    import bus
    _timers.pop(channel, None)
    bus.emit(channel, {"cmd": "ahorcado", "args": []})

def _schedule_restart(channel: str, delay: int = 10) -> None:
    cancel_timer(channel)
    t = threading.Timer(delay, _on_restart, args=(channel,))
    t.daemon = True
    t.start()
    _timers[channel] = t

def _reset_timer(channel: str) -> None:
    cancel_timer(channel)
    t = threading.Timer(TIMEOUT_SECS, _on_timeout, args=(channel,))
    t.daemon = True
    t.start()
    _timers[channel] = t

# ── mIRC format / color codes ────────────────────────────────────────────────
RESET  = "\x0f"
BOLD   = "\x02"
GREEN  = "\x0309"   # lime green
RED    = "\x0304"   # red
YELLOW = "\x0308"   # yellow
GRAY   = "\x0315"   # light gray
DGRAY  = "\x0314"   # dark gray
CYAN   = "\x0311"   # cyan

def _c(text, color, bold=False):
    b = BOLD if bold else ""
    return f"{color}{b}{text}{RESET}"

def _word_display(palabra, adivinadas):
    parts = []
    for l in palabra:
        if l in adivinadas:
            parts.append(_c(l.upper(), GREEN, bold=True))
        else:
            parts.append(_c("_", GRAY))
    return " ".join(parts)

def _falladas_display(falladas):
    if not falladas:
        return _c("-", GRAY)
    return " ".join(_c(l.upper(), RED, bold=True) for l in sorted(falladas))

def _linea_jugador(nick, fallos):
    vidas = MAX_ERRORES - fallos
    if fallos >= MAX_ERRORES:
        return f"{_c(nick, CYAN, bold=True)}: {_c('GAME OVER', RED, bold=True)}"
    hearts = _c("♥" * vidas, GREEN) + _c("✗" * fallos, RED)
    return f"{_c(nick, CYAN, bold=True)}: {hearts} ({fallos}/{MAX_ERRORES})"

def _tablero(nick_iniciador=None):
    import state
    d = state.game_data

    palabra    = d["palabra"]
    adivinadas = d["adivinadas"]

    lineas = []
    if nick_iniciador:
        lineas.append(f"{_c(nick_iniciador, CYAN, bold=True)} ha iniciado el ahorcado!")

    lineas.append(f"Palabra:  {_word_display(palabra, adivinadas)}")
    lineas.append(f"Falladas: {_falladas_display(d['falladas'])}")

    for nick, datos in d["jugadores"].items():
        lineas.append(_linea_jugador(nick, datos["fallos"]))

    return lineas

def _letras_desconocidas(d):
    return len(set(c for c in d["palabra"] if c not in d["adivinadas"]))

def _sumar_puntos(nick, puntos):
    import state
    import db
    state.scores[nick] = state.scores.get(nick, 0) + puntos
    db.add_points(nick, state.current_channel, "ahorcado", puntos)

def _score_line():
    import state
    if not state.scores:
        return None
    partes = [
        f"{_c(nick, CYAN, bold=True)}: {_c(str(pts) + 'pts', YELLOW, bold=True)}"
        for nick, pts in sorted(state.scores.items(), key=lambda x: -x[1])
    ]
    return _c("Score: ", YELLOW, bold=True) + " | ".join(partes)

def _todos_eliminados(d):
    jugadores = d["jugadores"]
    return bool(jugadores) and all(j["fallos"] >= MAX_ERRORES for j in jugadores.values())

def _cargar_palabras():
    ruta = Path(__file__).parent.parent / "datos" / "palabras_ahorcado.json"
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)["palabras"]

def _puntos_globales(channel):
    import db
    top = db.get_top(channel=channel, limit=10)
    if not top:
        return _c("Aún no hay puntos registrados.", GRAY)
    medallas = ["1°", "2°", "3°"]
    lineas = [_c("Ranking global del ahorcado:", YELLOW, bold=True)]
    for i, row in enumerate(top):
        pos    = medallas[i] if i < len(medallas) else f"{i+1}°"
        lineas.append(f"{pos} {_c(row['nick'], CYAN, bold=True)}: {_c(str(row['total']) + ' pts', YELLOW)}")
    return lineas

def run(args, nick):
    import state
    if args and args[0].lower() == "puntos":
        return _puntos_globales(state.current_channel)

    if state.active_game:
        return f"{nick}: ya hay un juego activo ({state.active_game}). Usa 'steve fin' para terminarlo."

    palabras = _cargar_palabras()
    palabra  = random.choice(palabras).lower()

    state.active_game = "ahorcado"
    state.game_data   = {
        "palabra":    palabra,
        "adivinadas": set(),
        "falladas":   set(),
        "iniciador":  nick,
        "jugadores":  {},
    }

    _reset_timer(state.current_channel)
    return _tablero(nick_iniciador=nick)

def _handle_timeout(channel: str):
    import state
    d = state.game_data
    palabras     = _cargar_palabras()
    nueva_palabra = random.choice(palabras).lower()
    d["palabra"]    = nueva_palabra
    d["adivinadas"] = set()
    d["falladas"]   = set()
    for jugador in d["jugadores"].values():
        jugador["fallos"] = 0
    lineas = [_c("Tiempo sin actividad! Cambiando palabra...", YELLOW, bold=True)]
    lineas += _tablero()
    _reset_timer(channel)
    return lineas

def handle_input(texto, nick):
    import state
    import commands
    texto = texto.strip().lower()

    # ── Timeout interno ───────────────────────────────────────────────────────
    if texto == "__timeout__":
        return _handle_timeout(state.current_channel)

    # ── Reset timer por actividad del jugador ─────────────────────────────────
    _reset_timer(state.current_channel)

    # ── Alias de comandos durante la partida ──────────────────────────────────
    if texto == "puntos":
        return _puntos_globales(state.current_channel)
    if texto == "fin":
        return commands.dispatch("fin", [], nick)

    d       = state.game_data
    palabra = d["palabra"]

    # Ignorar mensajes con espacios o más largos que la palabra
    if " " in texto or len(texto) > len(palabra):
        return None

    # Registrar jugador si es nuevo
    if nick not in d["jugadores"]:
        d["jugadores"][nick] = {"fallos": 0}

    # Jugador eliminado: ignorar silenciosamente
    if d["jugadores"][nick]["fallos"] >= MAX_ERRORES:
        return None

    # ── Intento de palabra completa ───────────────────────────────────────────
    if len(texto) > 1:
        if texto == palabra:
            puntos = _letras_desconocidas(d) * 5
            _sumar_puntos(nick, puntos)
            lineas = [
                f"Palabra:  {_word_display(palabra, set(palabra))}",
                _c(f"CORRECTO! {nick} ha adivinado la palabra: {palabra.upper()}! +{puntos}pts", GREEN, bold=True),
            ]
            score = _score_line()
            if score:
                lineas.append(score)
            lineas.append(_c("Nueva partida en 10 segundos...", YELLOW))
            state.active_game = None
            state.game_data   = {}
            _schedule_restart(state.current_channel)
            return lineas
        else:
            d["jugadores"][nick]["fallos"] += 1
            fallos = d["jugadores"][nick]["fallos"]
            lineas = _tablero()
            if fallos >= MAX_ERRORES:
                lineas.append(_c(f"{nick}: '{texto.upper()}' no es la palabra. GAME OVER!", RED, bold=True))
            else:
                lineas.append(f"{_c(nick, CYAN)}: '{_c(texto.upper(), RED)}' no es la palabra. ({fallos}/{MAX_ERRORES})")
            if _todos_eliminados(d):
                lineas.append(_c(f"GAME OVER TOTAL! La palabra era: {palabra.upper()}", RED, bold=True))
                lineas.append(_c("Nueva partida en 10 segundos...", YELLOW))
                state.active_game = None
                state.game_data   = {}
                _schedule_restart(state.current_channel)
            return lineas

    # ── Letra suelta ──────────────────────────────────────────────────────────
    if not texto.isalpha() or len(texto) != 1:
        return None

    letra = texto

    if letra in d["adivinadas"]:
        return f"{nick}: la letra '{_c(letra.upper(), YELLOW)}' ya fue adivinada."

    if letra in d["falladas"]:
        return f"{nick}: la letra '{_c(letra.upper(), RED)}' ya fue usada."

    if letra in palabra:
        puntos = _letras_desconocidas(d) * 5
        d["adivinadas"].add(letra)
        lineas = _tablero()
        if all(c in d["adivinadas"] for c in palabra):
            _sumar_puntos(nick, puntos)
            lineas.append(_c(f"GANASTEIS! La palabra era: {palabra.upper()} - felicidades {nick}! +{puntos}pts", GREEN, bold=True))
            score = _score_line()
            if score:
                lineas.append(score)
            lineas.append(_c("Nueva partida en 10 segundos...", YELLOW))
            state.active_game = None
            state.game_data   = {}
            _schedule_restart(state.current_channel)
        else:
            lineas.append(f"{_c(nick, CYAN)}: '{_c(letra.upper(), GREEN, bold=True)}' ACIERTO!")
        return lineas
    else:
        d["falladas"].add(letra)
        d["jugadores"][nick]["fallos"] += 1
        fallos = d["jugadores"][nick]["fallos"]
        lineas = _tablero()
        if fallos >= MAX_ERRORES:
            lineas.append(_c(f"{nick}: '{letra.upper()}' fallo. GAME OVER para {nick}!", RED, bold=True))
        else:
            lineas.append(f"{_c(nick, CYAN)}: '{_c(letra.upper(), RED, bold=True)}' fallo. ({fallos}/{MAX_ERRORES})")
        if _todos_eliminados(d):
            lineas.append(_c(f"GAME OVER TOTAL! La palabra era: {palabra.upper()}", RED, bold=True))
            lineas.append(_c("Nueva partida en 10 segundos...", YELLOW))
            state.active_game = None
            state.game_data   = {}
            _schedule_restart(state.current_channel)
        return lineas
