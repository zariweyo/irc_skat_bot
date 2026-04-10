DESCRIPTION = "Muestra los comandos disponibles"

def run(args, nick):
    import commands
    import state
    import channels

    registry = commands.get_commands()
    allowed  = channels.allowed_for(state.current_channel)

    if allowed:
        names = sorted(n for n in registry if n in allowed)
    else:
        names = sorted(registry)

    lines = [f"{nick}: comandos disponibles ->"]
    for name in names:
        lines.append(f"  steve {name} — {registry[name].DESCRIPTION}")
    return lines
