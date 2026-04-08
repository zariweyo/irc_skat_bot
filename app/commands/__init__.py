import importlib
import pkgutil
from pathlib import Path

_registry = {}

def _load():
    pkg_dir = Path(__file__).parent
    for _, name, _ in pkgutil.iter_modules([str(pkg_dir)]):
        mod = importlib.import_module(f"commands.{name}")
        if hasattr(mod, "run") and hasattr(mod, "DESCRIPTION"):
            _registry[name] = mod

def get_commands():
    if not _registry:
        _load()
    return _registry

def dispatch(cmd, args, nick):
    registry = get_commands()

    if cmd not in registry:
        return f"{nick}: comando desconocido. Usa 'steve help' para ver los disponibles."

    return registry[cmd].run(args, nick)

def handle_input(texto, nick):
    """Pasa texto libre al juego activo, si lo hay."""
    import app.state as state
    if not state.active_game:
        return None
    registry = get_commands()
    mod = registry.get(state.active_game)
    if mod and hasattr(mod, "handle_input"):
        return mod.handle_input(texto, nick)
    return None
