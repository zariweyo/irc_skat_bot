import json
import random
from pathlib import Path

DESCRIPTION = "Inicia una partida del ahorcado multijugador. Adivina la palabra letra a letra."

MAX_ERRORES = 6

def _cargar_palabras():
    ruta = Path(__file__).parent.parent / "datos" / "palabras_ahorcado.json"
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)["palabras"]

def _linea_jugador(nick, fallos):
    xs = "X" * fallos if fallos > 0 else "-"
    sufijo = " GAME OVER" if fallos >= MAX_ERRORES else ""
    return f"{nick} ({fallos}/{MAX_ERRORES}): {xs}{sufijo}"

def _tablero(nick_iniciador=None):
    import state
    d = state.game_data

    palabra    = d["palabra"]
    adivinadas = d["adivinadas"]
    tablero_palabra = " ".join(l if l in adivinadas else "?" for l in palabra)
    falladas_str    = " ".join(sorted(d["falladas"])).upper() if d["falladas"] else "-"

    lineas = []
    if nick_iniciador:
        lineas.append(f"{nick_iniciador} ha iniciado el ahorcado!")
    lineas.append(f"Palabra:  {tablero_palabra}")
    lineas.append(f"Falladas: {falladas_str}")
    for nick, datos in d["jugadores"].items():
        lineas.append(_linea_jugador(nick, datos["fallos"]))
    return lineas

def _todos_eliminados(d):
    """True si hay al menos un jugador y todos han agotado sus fallos."""
    jugadores = d["jugadores"]
    return bool(jugadores) and all(j["fallos"] >= MAX_ERRORES for j in jugadores.values())

def run(args, nick):
    import state
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

    return _tablero(nick_iniciador=nick)

def handle_input(texto, nick):
    import state
    d      = state.game_data
    texto  = texto.strip().lower()
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

    # --- Intento de palabra completa ---
    if len(texto) > 1:
        if texto == palabra:
            state.active_game = None
            state.game_data   = {}
            return [
                f"Palabra:  {' '.join(palabra)}",
                f"CORRECTO! {nick} ha adivinado la palabra: {palabra.upper()}!",
            ]
        else:
            d["jugadores"][nick]["fallos"] += 1
            fallos = d["jugadores"][nick]["fallos"]
            lineas = _tablero()
            if fallos >= MAX_ERRORES:
                lineas.append(f"{nick}: '{texto.upper()}' no es la palabra. GAME OVER!")
            else:
                lineas.append(f"{nick}: '{texto.upper()}' no es la palabra. ({fallos}/{MAX_ERRORES})")
            if _todos_eliminados(d):
                lineas.append(f"GAME OVER TOTAL! La palabra era: {palabra.upper()}")
                state.active_game = None
                state.game_data   = {}
            return lineas

    # --- Letra suelta ---
    if not texto.isalpha() or len(texto) != 1:
        return None

    letra = texto

    if letra in d["adivinadas"]:
        return f"{nick}: la letra '{letra.upper()}' ya fue adivinada."

    if letra in d["falladas"]:
        return f"{nick}: la letra '{letra.upper()}' ya fue usada."

    if letra in palabra:
        d["adivinadas"].add(letra)
        lineas = _tablero()
        if all(c in d["adivinadas"] for c in palabra):
            lineas.append(f"GANASTEIS! La palabra era: {palabra.upper()} - felicidades {nick}!")
            state.active_game = None
            state.game_data   = {}
        else:
            lineas.append(f"{nick}: '{letra.upper()}' ACIERTO!")
        return lineas
    else:
        d["falladas"].add(letra)
        d["jugadores"][nick]["fallos"] += 1
        fallos = d["jugadores"][nick]["fallos"]
        lineas = _tablero()
        if fallos >= MAX_ERRORES:
            lineas.append(f"{nick}: '{letra.upper()}' fallo. GAME OVER para {nick}!")
        else:
            lineas.append(f"{nick}: '{letra.upper()}' fallo. ({fallos}/{MAX_ERRORES})")
        if _todos_eliminados(d):
            lineas.append(f"GAME OVER TOTAL! La palabra era: {palabra.upper()}")
            state.active_game = None
            state.game_data   = {}
        return lineas
