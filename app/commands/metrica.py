import time
import psutil
import os
from pathlib import Path

DESCRIPTION = "Muestra uptime, RAM, CPU y versión del bot."

def run(args, nick):
    import state

    # Uptime
    segundos = int(time.time() - state.start_time)
    horas, resto = divmod(segundos, 3600)
    minutos, segs = divmod(resto, 60)
    uptime = f"{horas}h {minutos}m {segs}s"

    # RAM
    proc = psutil.Process(os.getpid())
    ram_mb = proc.memory_info().rss / 1024 / 1024

    # CPU (intervalo corto para % instantáneo)
    cpu = proc.cpu_percent(interval=0.5)

    # Versión
    version_file = Path(__file__).parent.parent / "version.txt"
    version = version_file.read_text().strip() if version_file.exists() else "desconocida"

    return [
        f"[metrica] uptime: {uptime} | RAM: {ram_mb:.1f} MB | CPU: {cpu:.1f}% | version: {version}"
    ]
