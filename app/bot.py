import socket
import threading
import queue
import time
import random
import sys
import traceback
import commands
import state
import healthcheck

healthcheck.start()

# Configuración
SERVER   = "irc.chathispano.org"
PORT     = 6667
NICK     = "SteveMacuin"
USER     = "steve"
REALNAME = "Steve McQueen"
CHANNELS = ["#skateros", "#ahorcado"]          # Añade canales aquí

_sock_lock = threading.Lock()

def send(sock, msg):
    print(f">> {msg}")
    with _sock_lock:
        sock.sendall((msg + "\r\n").encode("utf-8"))

def connect():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER, PORT))
    sock.settimeout(5)
    print(f"Conectado a {SERVER}:{PORT}")
    send(sock, f"NICK {NICK}")
    send(sock, f"USER {USER} 0 * :{REALNAME}")
    return sock

def channel_worker(sock, channel, q, actual_nick):
    """Hilo dedicado a un canal. Lee mensajes de su queue y responde."""
    print(f"[{channel}] Worker iniciado.")
    while True:
        line = q.get()
        if line is None:   # señal de parada
            break

        try:
            nick    = line.split("!")[0].lstrip(":")
            mensaje = line.split(f"PRIVMSG {channel} :", 1)[-1].strip()

            if nick == actual_nick:
                continue

            print(f"  [{channel}] [{nick}]: {mensaje}")

            partes = mensaje.split()
            if len(partes) >= 2 and partes[0].lower() == "steve":
                cmd      = partes[1].lower()
                args     = partes[2:]
                respuesta = commands.dispatch(cmd, args, nick)
            elif state.active_game:
                respuesta = commands.handle_input(mensaje, nick)
            else:
                respuesta = None

            if respuesta:
                if isinstance(respuesta, list):
                    for linea in respuesta:
                        send(sock, f"PRIVMSG {channel} :{linea}")
                else:
                    send(sock, f"PRIVMSG {channel} :{respuesta}")

        except Exception as e:
            msg = f"ERR: {type(e).__name__}: {e}"
            print(msg)
            traceback.print_exc()
            try:
                send(sock, f"PRIVMSG {channel} :{msg}")
            except Exception:
                pass

def main():
    sock = connect()

    # Esperar bienvenida (001) o nick en uso (433)
    registered  = False
    actual_nick = NICK
    timeout_at  = time.time() + 15

    while not registered and time.time() < timeout_at:
        try:
            data = sock.recv(4096).decode("utf-8", errors="ignore")
        except socket.timeout:
            continue

        for line in data.split("\r\n"):
            if not line:
                continue
            print(f"<< {line}")

            if line.startswith("PING"):
                send(sock, line.replace("PING", "PONG"))

            if " 433 " in line:
                actual_nick = f"{NICK}{random.randint(100, 999)}"
                print(f"Nick en uso, probando: {actual_nick}")
                send(sock, f"NICK {actual_nick}")

            if " 001 " in line:
                actual_nick = line.split(" ")[2]
                registered  = True
                print(f"Nick asignado: {actual_nick}")

    if not registered:
        print("No se pudo registrar en el servidor.")
        sock.close()
        return

    # Unirse a todos los canales
    for channel in CHANNELS:
        send(sock, f"JOIN {channel}")

    time.sleep(1)

    # Lanzar un hilo trabajador por canal
    queues  = {ch: queue.Queue() for ch in CHANNELS}
    workers = []
    for channel in CHANNELS:
        t = threading.Thread(
            target=channel_worker,
            args=(sock, channel, queues[channel], actual_nick),
            daemon=True,
            name=f"worker-{channel}",
        )
        t.start()
        workers.append(t)
        send(sock, f"PRIVMSG {channel} :hola! soy {actual_nick}. Escribe 'steve help' para ver los comandos disponibles.")

    print(f"\nBot activo en {', '.join(CHANNELS)}. Ctrl+C para salir.\n")

    # Bucle lector principal: recibe todo y enruta por canal
    try:
        while True:
            try:
                data = sock.recv(4096).decode("utf-8", errors="ignore")
            except socket.timeout:
                continue

            for line in data.split("\r\n"):
                if not line:
                    continue

                if line.startswith("PING"):
                    send(sock, line.replace("PING", "PONG"))
                    continue

                line_upper = line.upper()
                for channel in CHANNELS:
                    if f"PRIVMSG {channel.upper()} :" in line_upper:
                        queues[channel].put(line)
                        break

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")

    # Parar workers
    for q in queues.values():
        q.put(None)

    send(sock, "QUIT :hasta luego!")
    sock.close()
    print("Desconectado.")

def _global_excepthook(exc_type, exc_value, exc_tb):
    msg = f"ERR: {exc_type.__name__}: {exc_value}"
    print(msg)
    traceback.print_exception(exc_type, exc_value, exc_tb)

sys.excepthook = _global_excepthook

if __name__ == "__main__":
    main()
