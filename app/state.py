import sys
import threading
import time

class _StateModule:
    """
    Módulo-proxy que expone active_game y game_data como thread-local,
    de forma que cada canal (hilo) tenga su propio estado de juego.
    start_time es global (uptime del bot).
    """
    def __init__(self):
        self.__name__    = __name__
        self.__package__ = __package__
        self.__file__    = __file__
        self.__spec__    = None
        self.start_time  = time.time()
        self._local      = threading.local()

    @property
    def active_game(self):
        return getattr(self._local, 'active_game', None)

    @active_game.setter
    def active_game(self, val):
        self._local.active_game = val

    @property
    def game_data(self):
        return getattr(self._local, 'game_data', {})

    @game_data.setter
    def game_data(self, val):
        self._local.game_data = val

    @property
    def scores(self):
        if not hasattr(self._local, 'scores'):
            self._local.scores = {}
        return self._local.scores

sys.modules[__name__] = _StateModule()
