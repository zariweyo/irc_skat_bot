"""
Bus de eventos interno: permite que threads externos (timers) inyecten
eventos en la queue de un canal, que el worker procesará en su propio hilo.
"""

_queues: dict = {}  # channel -> queue.Queue


def register(channel: str, q) -> None:
    _queues[channel] = q


def emit(channel: str, event: dict) -> None:
    q = _queues.get(channel)
    if q is not None:
        q.put(event)
