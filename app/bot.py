import socket
import time
import commands
import state
import healthcheck

healthcheck.start()

# Configuración
SERVER = "irc.chathispano.org"
PORT = 6667
NICK = "SteveMacuin"
USER = "steve"
REALNAME = "Steve McQueen"
CHANNEL = "#skat"

def send(sock, msg):
    print(f">> {msg}")
    sock.sendall((msg + "\r\n").encode("utf-8"))

def connect():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER, PORT))
    sock.settimeout(5)
    print(f"Conectado a {SERVER}:{PORT}")

    send(sock, f"NICK {NICK}")
    send(sock, f"USER {USER} 0 * :{REALNAME}")

    return sock

def read_lines(sock):
    buffer = ""
    try:
        data = sock.recv(4096).decode("utf-8", errors="ignore")
        buffer += data
    except socket.timeout:
        pass

    lines = buffer.split("\r\n")
    return [l for l in lines if l]

def list_channels(sock):
    channels = []
    send(sock, "LIST")

    print("\n--- Esperando lista de canales ---\n")
    timeout_at = time.time() + 30  # máximo 30 segundos esperando

    while time.time() < timeout_at:
        try:
            data = sock.recv(4096).decode("utf-8", errors="ignore")
        except socket.timeout:
            continue

        for line in data.split("\r\n"):
            if not line:
                continue

            # Responder a PING para no ser desconectados
            if line.startswith("PING"):
                pong = line.replace("PING", "PONG")
                send(sock, pong)

            # 322 = RPL_LIST  ->  ":server 322 nick #canal usuarios :topic"
            if " 322 " in line:
                parts = line.split(" ")
                if len(parts) >= 5:
                    canal = parts[3]
                    usuarios = parts[4]
                    topic = " ".join(parts[5:]).lstrip(":")
                    channels.append((canal, usuarios, topic))
                    print(f"  {canal:<30} usuarios: {usuarios:<6} | {topic}")

                if len(channels) >= 10:
                    print(f"\nLímite de 10 canales alcanzado.")
                    return channels

            # 323 = RPL_LISTEND  ->  fin de la lista
            if " 323 " in line:
                print(f"\nTotal canales encontrados: {len(channels)}")
                return channels

    print("Tiempo de espera agotado.")
    return channels

def join_and_list_users(sock, canal):
    send(sock, f"JOIN {canal}")

    users = []
    print(f"\n--- Usuarios en {canal} ---\n")
    timeout_at = time.time() + 15

    while time.time() < timeout_at:
        try:
            data = sock.recv(4096).decode("utf-8", errors="ignore")
        except socket.timeout:
            continue

        for line in data.split("\r\n"):
            if not line:
                continue

            if line.startswith("PING"):
                send(sock, line.replace("PING", "PONG"))

            # 353 = RPL_NAMREPLY  ->  ":server 353 nick = #canal :user1 user2 ..."
            if " 353 " in line:
                partes = line.split(":")
                if len(partes) >= 3:
                    nuevos = partes[2].strip().split()
                    users.extend(nuevos)
                    for u in nuevos:
                        print(f"  {u}")

            # 366 = RPL_ENDOFNAMES  ->  fin de la lista de usuarios
            if " 366 " in line:
                print(f"\nTotal usuarios en {canal}: {len(users)}")
                return users

    print("Tiempo de espera agotado.")
    return users

def main():
    sock = connect()

    # Esperar bienvenida del servidor (mensajes 001-004)
    registered = False
    actual_nick = NICK
    timeout_at = time.time() + 15

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

            # 001 = RPL_WELCOME  ->  ":server 001 actual_nick :Welcome..."
            if " 001 " in line:
                actual_nick = line.split(" ")[2]
                registered = True
                print(f"\nNick asignado por el servidor: {actual_nick}")

    if not registered:
        print("No se pudo registrar en el servidor.")
        sock.close()
        return

    join_and_list_users(sock, CHANNEL)

    # Saludar con el nick real asignado
    time.sleep(1)
    send(sock, f"PRIVMSG {CHANNEL} :hola! soy {actual_nick}. Escribe 'steve help' para ver los comandos disponibles.")
    print(f"\nBot activo en {CHANNEL}. Ctrl+C para salir.\n")

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

                # formato: :nick!user@host PRIVMSG #canal :mensaje
                if f"PRIVMSG {CHANNEL} :" in line:
                    nick = line.split("!")[0].lstrip(":")
                    mensaje = line.split(f"PRIVMSG {CHANNEL} :")[-1].strip()

                    if nick == actual_nick:
                        continue

                    print(f"  [{nick}]: {mensaje}")

                    # Detectar comandos: "steve <cmd> [args...]"
                    partes = mensaje.split()
                    if len(partes) >= 2 and partes[0].lower() == "steve":
                        cmd = partes[1].lower()
                        args = partes[2:]
                        respuesta = commands.dispatch(cmd, args, nick)
                    elif state.active_game:
                        respuesta = commands.handle_input(mensaje, nick)
                    else:
                        respuesta = None

                    if respuesta:
                        if isinstance(respuesta, list):
                            for linea in respuesta:
                                send(sock, f"PRIVMSG {CHANNEL} :{linea}")
                        else:
                            send(sock, f"PRIVMSG {CHANNEL} :{respuesta}")

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")

    send(sock, "QUIT :hasta luego!")
    sock.close()
    print("Desconectado.")

if __name__ == "__main__":
    main()
