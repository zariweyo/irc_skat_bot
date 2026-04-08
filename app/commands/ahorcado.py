import json
import random
from pathlib import Path

DESCRIPTION = "Inicia una partida del ahorcado. Adivina la palabra letra a letra."

MAX_ERRORES = 6

GALLOWS = [
    # 0 errores
    ["  +---+",
     "  |   |",
     "      |",
     "      |",
     "      |",
     "      |",
     "========="],
    # 1 error — cabeza
    ["  +---+",
     "  |   |",
     "  O   |",
     "      |",
     "      |",
     "      |",
     "========="],
    # 2 errores — torso
    ["  +---+",
     "  |   |",
     "  O   |",
     "  |   |",
     "      |",
     "      |",
     "========="],
    # 3 errores — brazo izq
    ["  +---+",
     "  |   |",
     "  O   |",
     " /|   |",
     "      |",
     "      |",
     "========="],
    # 4 errores — ambos brazos
    ["  +---+",
     "  |   |",
     "  O   |",
     r" /|\  |",
     "      |",
     "      |",
     "========="],
    # 5 errores — pierna izq
    ["  +---+",
     "  |   |",
     "  O   |",
     r" /|\  |",
     " /    |",
     "      |",
     "========="],
    # 6 errores — muerto
    ["  +---+",
     "  |   |",
     "  O   |",
     r" /|\  |",
     r" / \  |",
     "      |",
     "========="],
]

def _cargar_palabras():
    ruta = Path(__file__).parent.parent / "datos" / "palabras_ahorcado.json"
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)["palabras"]

def _tablero(nick_iniciador=None):
    import state
    d = state.game_data
    errores = len(d["falladas"])
    gallows = GALLOWS[errores]

    palabra = d["palabra"]
    adivinadas = d["adivinadas"]
    tablero_palabra = " ".join(l if l in adivinadas else "_" for l in palabra)
    falladas_str = " ".join(sorted(d["falladas"])).upper() if d["falladas"] else "-"

    lineas = list(gallows)
    lineas.append(f"Palabra:  {tablero_palabra}")
    lineas.append(f"Falladas: {falladas_str}  ({errores}/{MAX_ERRORES})")
    if nick_iniciador:
        lineas.insert(0, f"{nick_iniciador} ha iniciado el ahorcado!")
    return lineas

def run(args, nick):
    import state
    if state.active_game:
        return f"{nick}: ya hay un juego activo ({state.active_game}). Usa 'steve fin' para terminarlo."

    palabras = _cargar_palabras()
    palabra = random.choice(palabras).lower()

    state.active_game = "ahorcado"
    state.game_data = {
        "palabra":    palabra,
        "adivinadas": set(),
        "falladas":   set(),
        "iniciador":  nick,
    }

    return _tablero(nick_iniciador=nick)

def handle_input(texto, nick):
    import state
    d = state.game_data
    texto = texto.strip().lower()
    palabra = d["palabra"]

    # Intento de palabra completa
    if len(texto) > 1:
        if texto == palabra:
            d["adivinadas"] = set(palabra)
            state.active_game = None
            state.game_data = {}
            return list(GALLOWS[len(d["falladas"])]) + [
                f"Palabra:  {' '.join(palabra)}",
                f"CORRECTO! {nick} ha adivinado la palabra: {palabra.upper()}!",
            ]
        else:
            d["falladas"].update(c for c in texto if c not in d["adivinadas"] and c not in d["falladas"])
            lineas = _tablero()
            if len(d["falladas"]) >= MAX_ERRORES:
                lineas.append(f"GAME OVER! La palabra era: {palabra.upper()}")
                state.active_game = None
                state.game_data = {}
            else:
                lineas.append(f"{nick}: '{texto.upper()}' no es la palabra.")
            return lineas

    # Letra suelta
    if not texto.isalpha() or len(texto) != 1:
        return None  # ignorar

    letra = texto

    if letra in d["adivinadas"] or letra in d["falladas"]:
        return f"{nick}: la letra '{letra.upper()}' ya fue usada."

    if letra in palabra:
        d["adivinadas"].add(letra)
        lineas = _tablero()
        if all(c in d["adivinadas"] for c in palabra):
            lineas.append(f"GANASTEIS! La palabra era: {palabra.upper()} - felicidades {nick}!")
            state.active_game = None
            state.game_data = {}
        else:
            lineas.append(f"{nick}: '{letra.upper()}' ACIERTO!")
    else:
        d["falladas"].add(letra)
        lineas = _tablero()
        if len(d["falladas"]) >= MAX_ERRORES:
            lineas.append(f"GAME OVER! La palabra era: {palabra.upper()}")
            state.active_game = None
            state.game_data = {}
        else:
            lineas.append(f"{nick}: '{letra.upper()}' fallo.")

    return lineas
