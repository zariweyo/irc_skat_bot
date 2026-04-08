DESCRIPTION = "Finaliza cualquier juego o actividad en curso."

def run(args, nick):
    import state
    if not state.active_game:
        return f"{nick}: no hay ningún juego activo en este momento."

    juego = state.active_game
    state.active_game = None
    state.game_data = {}
    return f"{nick} ha finalizado el juego de {juego}."
