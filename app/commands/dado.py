import random

DESCRIPTION = "Tira un dado. Uso: steve dado [caras] (por defecto 6)"

def run(args, nick):
    caras = 6
    if args:
        try:
            caras = int(args[0])
            if caras < 2:
                return f"{nick}: el dado debe tener al menos 2 caras."
        except ValueError:
            return f"{nick}: '{args[0]}' no es un número válido."

    resultado = random.randint(1, caras)
    return f"{nick} tira un d{caras} y saca... {resultado}!"
