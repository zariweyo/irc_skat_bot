DESCRIPTION = "Muestra los comandos disponibles"

def run(args, nick):
    import commands
    registry = commands.get_commands()

    lines = [f"{nick}: comandos disponibles ->"]
    for name in sorted(registry):
        lines.append(f"  steve {name} — {registry[name].DESCRIPTION}")
    return lines
