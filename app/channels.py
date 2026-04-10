import json
from pathlib import Path

_cache        = None
_debug_cfg    = None
_channel_list = None
_welcome_map  = {}

def _load():
    global _cache, _debug_cfg, _channel_list, _welcome_map
    ruta = Path(__file__).parent / "channels.json"
    with open(ruta, encoding="utf-8") as f:
        data = json.load(f)

    _cache        = {}
    _channel_list = []
    _welcome_map  = {}
    for entry in data:
        name = entry["channel"]
        cmds = set(entry["commands"])
        if name == "debug":
            _debug_cfg = entry
        else:
            _cache[name]       = cmds
            _channel_list.append(name)
        if "welcome" in entry:
            _welcome_map[name] = entry["welcome"]

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

def get_welcome(channel, nick):
    """Devuelve el mensaje de bienvenida del canal con %NICK% sustituido, o None si no hay."""
    if _cache is None:
        _load()
    msg = _welcome_map.get(channel)
    if msg is None:
        return None
    return msg.replace("%NICK%", nick)
