"""
Modo debug: simula el canal IRC en la terminal sin conectar al servidor.
Uso: python debug.py [--nick TuNick]
"""
import sys
import os

# Para que los imports de commands/ y state funcionen igual que en bot.py
sys.path.insert(0, os.path.dirname(__file__))

import commands
import state
import db

db.init_db()

DEFAULT_NICK = "Tester"
DEBUG_CHANNEL = "debug"

def responder(respuesta):
    if respuesta is None:
        return
    if isinstance(respuesta, list):
        for linea in respuesta:
            print(f"  [SteveMacuin]: {linea}")
    else:
        print(f"  [SteveMacuin]: {respuesta}")

def main():
    nick = DEFAULT_NICK
    if "--nick" in sys.argv:
        idx = sys.argv.index("--nick")
        if idx + 1 < len(sys.argv):
            nick = sys.argv[idx + 1]

    print(f"=== Modo debug IRC (nick: {nick}) ===")
    print("Escribe mensajes como si estuvieras en el canal.")
    print("Escribe 'salir' para terminar.\n")

    while True:
        try:
            texto = input(f"[{nick}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo.")
            break

        if texto.lower() == "salir":
            break
        if not texto:
            continue

        try:
            state.current_channel = DEBUG_CHANNEL
            partes = texto.split()
            if len(partes) >= 2 and partes[0].lower() == "steve":
                cmd = partes[1].lower()
                args = partes[2:]
                respuesta = commands.dispatch(cmd, args, nick)
            elif state.active_game:
                respuesta = commands.handle_input(texto, nick)
            else:
                respuesta = None

            responder(respuesta)

        except Exception as e:
            import traceback
            print(f"  ERR: {type(e).__name__}: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()
