import json
from pathlib import Path

_cache       = None
_debug_cfg   = None
_channel_list = None

def _load():
    global _cache, _debug_cfg, _channel_list
    ruta = Path(__file__).parent / "channels.json"
    with open(ruta, encoding="utf-8") as f:
        data = json.load(f)

    _cache        = {}
    _channel_list = []
    for entry in data:
        name = entry["channel"]
        cmds = set(entry["commands"])
        if name == "debug":
            _debug_cfg = entry
        else:
            _cache[name]        = cmds
            _channel_list.append(name)

def get_channels():
    """Lista de canales IRC reales (excluye 'debug')."""
    if _channel_list is None:
        _load()
    return _channel_list

def get_debug_config():
    """Configuración del canal debug, o None si no existe."""
    if _cache is None:
        _load()
    return _debug_cfg

def allowed_for(channel):
    """
    Devuelve el set de comandos permitidos en el canal.
    Set vacío significa que todos los comandos están permitidos.
    """
    if _cache is None:
        _load()
    return _cache.get(channel, set())

def is_allowed(channel, cmd):
    allowed = allowed_for(channel)
    return not allowed or cmd in allowed
