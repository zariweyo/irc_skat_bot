# IA_CONTEXT — IRC Bot SteveMacuin

Guía de contexto completa para continuar el desarrollo en nuevas sesiones.

> **IMPORTANTE:** Cualquier commit nuevo en la aplicación (nuevos comandos, modificaciones de arquitectura, nuevos canales, cambios en el despliegue, etc.) debe reflejarse en este fichero junto con el commit. Este documento es la fuente de verdad para retomar el desarrollo en futuras sesiones.

---

## Descripción general

Bot IRC escrito en Python puro para el servidor **irc.chathispano** (red ChatHispano).
Se conecta por **SSL/TLS** (puerto 6697) sin verificación de certificado (el certificado del servidor no coincide con el hostname).
El nick del bot es **SteveMacuin**. Los usuarios interactúan escribiendo `steve <comando>` en el canal.

Está desplegado en **Fly.io** (app: `irc-skat-bot`, región: `ams`, 256 MB RAM, 1 CPU compartida).

---

## Estructura de ficheros

```
irc_bot/
├── Dockerfile
├── fly.toml
├── requirements.txt
└── app/
    ├── bot.py              # Núcleo: conexión SSL, loop principal, routing, PM worker
    ├── bus.py              # Bus de eventos interno (timers → workers via queue)
    ├── channels.py         # Carga channels.json, filtra comandos, welcome, initial
    ├── channels.json       # Configuración de canales (comandos, welcome, initial)
    ├── db.py               # SQLite: init, add_points, get_top, get_player_total
    ├── ia.py               # Sesiones IA por query privado (OpenAI API)
    ├── state.py            # Estado thread-local por canal (active_game, game_data, scores)
    ├── debug.py            # Simulador IRC local sin conexión al servidor
    ├── healthcheck.py      # HTTP server en puerto 9180 para Fly.io health checks
    ├── version.txt         # Versión del bot (usada por metrica)
    ├── datos/
    │   ├── palabras_ahorcado.json
    │   └── diccionario.txt
    └── commands/
        ├── __init__.py     # Registry de comandos: dispatch(), handle_input()
        ├── help.py
        ├── dado.py
        ├── fin.py
        ├── metrica.py
        ├── ahorcado.py
        └── detector.py
```

---

## Arquitectura

### Conexión (`bot.py`)

- Se conecta con `ssl.create_default_context()`, `check_hostname=False`, `verify_mode=CERT_NONE`.
- Tras conectar, espera mensaje `001` (registro OK) o `433` (nick en uso → añade número aleatorio).
- Hace JOIN a todos los canales de `channels.json` (excepto "debug").
- Al arrancar, envía un saludo genérico a cada canal.
- Cuando un usuario hace JOIN, envía el mensaje `welcome` del canal con `%NICK%` sustituido.
- Si el canal tiene `initial` configurado, inyecta ese comando en la queue del canal al arrancar.

### Reconexión automática (`bot.py`)

El punto de entrada `__main__` ejecuta `main()` en un bucle infinito:
- Cualquier excepción (error de socket, SSL, timeout de registro, conexión cerrada) → espera **60 segundos** y reintenta.
- `KeyboardInterrupt` → sale limpiamente.
- `main()` usa `try/finally` para garantizar que el socket se cierra y los workers paran siempre, tanto en error como en salida limpia.
- Detección de desconexión: si `sock.recv()` devuelve datos vacíos, lanza `ConnectionError` para forzar el retry.

### Threading

- Un hilo lector principal recibe toda la actividad IRC.
- Un hilo worker por canal, cada uno con su propia `queue.Queue`.
- El lector principal enruta cada `PRIVMSG` al worker del canal correspondiente.
- `state.py` usa `threading.local()` para que cada canal tenga su propio `active_game` y `game_data`.
- Los workers también procesan **eventos internos** (tipo `dict`) inyectados en su queue, usados por timers y comandos iniciales.

### Sesiones IA por query privado (`ia.py`)

Cuando un usuario abre un **query (mensaje privado)** al bot:
1. El bot responde únicamente `Contraseña`.
2. Si el usuario envía la contraseña correcta → sesión activa con ChatGPT (OpenAI API).
3. Si la contraseña es incorrecta → sesión cancelada.
4. Los mensajes siguientes en el PM se envían a OpenAI y la respuesta vuelve al query.
5. Si el usuario hace QUIT del servidor IRC → la sesión se cierra automáticamente.

**Variables de entorno:**
- `IA_PASSWORD` — contraseña de acceso
- `GROQ_API_KEY` — clave API de Groq
- `IA_MODEL` — modelo (por defecto: `llama-3.3-70b-versatile`)
- `IA_ADMIN_NICK` — único nick autorizado (por defecto: `Iggy`)

**Diseño:**
- Solo el nick `IA_ADMIN_NICK` (por defecto `Iggy`) puede abrir sesión; el resto se ignora silenciosamente.
- Comparación de nick case-insensitive.
- `_pm_sessions = { nick: {"state": "awaiting_password"|"active", "history": [...]} }`
- Historial limitado a `_MAX_HISTORY = 20` mensajes para evitar token blowup.
- `bot.py` arranca un hilo `pm_worker` (queue dedicada) para no bloquear el loop lector.
- El loop principal detecta `PRIVMSG <botnick>` → encola en `pm_queue`.
- El loop principal detecta `QUIT` → encola `{"quit": nick}` → cierra sesión.
- No es un comando de canal; no aparece en `steve help`.
- La IA puede emitir comandos IRC en crudo: líneas que empiecen por `IRC: ` se envían directamente al servidor (JOIN, NICK, KICK, MODE, PRIVMSG, etc.). El `pm_worker` las distingue del texto normal.

### Bus de eventos (`bus.py`)

Permite que threads externos (timers, arranque del bot) inyecten eventos en la queue de un canal:
- `bus.register(channel, queue)` — llamado desde `bot.py` al crear los workers.
- `bus.emit(channel, event_dict)` — inyecta un evento en la queue del canal.

El worker detecta que el item de la queue es un `dict` y lo procesa según su contenido:
- `{"cmd": "ahorcado", "args": []}` → llama a `commands.dispatch()`
- `{"msg": "__timeout__", "nick": ""}` → llama a `commands.handle_input()`

### Sistema de comandos (`commands/__init__.py`)

- Auto-descubre módulos en `commands/` que tengan `run()` y `DESCRIPTION`.
- Invocación: `steve <cmd> [args...]`
- Si hay un juego activo (`state.active_game`), el texto libre se pasa a `handle_input()` del juego.
- Los comandos pueden devolver `str` o `list[str]` (el bot envía cada elemento como PRIVMSG separado).

### Filtrado por canal (`channels.py`)

- `channels.json` define qué comandos están permitidos en cada canal (lista vacía = todos).
- `is_allowed(channel, cmd)` → bool
- `get_welcome(channel, nick)` → str con `%NICK%` reemplazado, o None
- `allowed_for(channel)` → set de comandos permitidos
- `get_initial(channel)` → nombre del comando a lanzar automáticamente al arrancar, o None

### Base de datos (`db.py`)

SQLite persistente. Ruta configurada por variable de entorno `DB_PATH`:
- **Local:** `./data/irc_bot.db` (valor por defecto)
- **Contenedor:** `/data/irc_bot.db` (volumen externo de Fly.io, `ENV DB_PATH=/data/irc_bot.db`)

Tabla `score_events`:
| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Autoincremental |
| `nick` | TEXT | Nick del jugador |
| `channel` | TEXT | Canal donde se ganaron los puntos |
| `game` | TEXT | Juego que otorgó los puntos |
| `points` | INTEGER | Puntos ganados |
| `earned_at` | TEXT | Timestamp (datetime UTC) |

Usa WAL mode para soportar accesos concurrentes (un worker por canal).

Funciones públicas:
- `init_db()` — crea tablas si no existen. Llamado al arrancar `bot.py` y `debug.py`.
- `add_points(nick, channel, game, points)` — inserta evento de puntos.
- `get_top(channel=None, limit=10)` — ranking global o por canal.
- `get_player_total(nick, channel=None)` — puntos acumulados de un jugador.

---

## Canales configurados

| Canal | Comandos permitidos | Initial | Notas |
|---|---|---|---|
| `debug` | help, ahorcado, fin | — | Solo para pruebas locales, no se conecta |
| `#skateros` | todos | — | Canal general, sin restricción |
| `#ahorcado` | help, ahorcado, fin | ahorcado | Juego arranca automáticamente al conectar |
| `#mentiras` | help, detector, fin | — | Canal dedicado al detector |

Para añadir un canal: editar `channels.json` con `channel`, `commands`, `welcome` e `initial` (opcional).

---

## Comandos implementados

### `help`
Lista los comandos disponibles en el canal actual.

### `dado [caras]`
Tira un dado. Por defecto 6 caras. Uso: `steve dado 20`

### `fin`
Termina cualquier juego activo en el canal. Limpia `state.active_game` y `state.game_data`. Si el juego activo es `ahorcado`, también cancela su timer de inactividad.

### `metrica`
Muestra uptime, RAM, CPU y versión. Usa `psutil`. Lee `version.txt`.

### `ahorcado`
Juego del ahorcado multijugador. Palabras desde `datos/palabras_ahorcado.json`.

- Múltiples jugadores simultáneos, cada uno con sus propios fallos (máx 6).
- Se puede adivinar letra a letra o la palabra completa.
- Lleva puntuación en `state.scores` (sesión) y persiste en DB (`score_events`).
- Estado: `active_game = "ahorcado"`, `game_data` contiene palabra, adivinadas, falladas, jugadores.

**Subcomando:** `steve ahorcado puntos` — muestra el ranking global del canal (top 10 desde DB).

**Alias durante la partida** (texto libre, sin `steve`):
- `puntos` → equivale a `steve ahorcado puntos`
- `fin` → equivale a `steve fin`

**Timeout de inactividad:**
- Si nadie escribe nada durante **60 segundos**, se cambia automáticamente a una nueva palabra.
- Los jugadores se mantienen pero sus fallos se reinician a 0.
- Implementado con `threading.Timer` + `bus.emit()` → evento dict en la queue del canal.

**Reinicio automático tras fin de partida:**
- Cuando la palabra es adivinada (win) o todos los jugadores son eliminados (game over total), el juego anuncia "Nueva partida en 10 segundos..." y arranca una nueva partida automáticamente.
- El ciclo es infinito hasta que alguien use `fin`.
- Implementado con `_schedule_restart(channel, delay=10)` → timer que emite `{"cmd": "ahorcado", "args": []}` al bus.
- `fin` cancela también el timer de restart (ambos tipos comparten `_timers[channel]`).

**Colores mIRC:**
- Letras adivinadas: verde bold
- Letras desconocidas: gris (`_`)
- Letras falladas: rojo bold
- Vidas por jugador: `♥♥♥✗✗✗` (♥ verde = vidas restantes, ✗ rojo = vidas consumidas)
- Mensajes de victoria: verde bold / Game over: rojo bold

### `detector`
Detector de mentiras. Uso: `steve detector <nick>` (se puede activar sobre uno mismo).

**Flujo:**
1. **Fase de control** (3 preguntas):
   - `¿Es verdad que tu nick es XXX?` → espera "sí/claro/correcto" o el nick
   - `¿De qué color es el caballo blanco de Santiago?` → espera "blanco" (trampa)
   - `¿Confirmas que participas voluntariamente?` → espera afirmación
   - Los tiempos de respuesta correctos se usan como **baseline de calibración**.
   - Si falla alguna → `warning = True` + mensaje de aviso (el juego continúa).

2. **Fase de monitoreo** (cada mensaje del target):
   - Score de sospecha calculado con: tiempo vs baseline, errores ortográficos, ilegibilidad, historial de veredictos, penalización por warning.
   - Ruido aleatorio simulado para que no sea determinista.
   - Veredicto: `[VERDAD]` o `[FALSO]`.

**Estado:** `active_game = "detector"`, `game_data` contiene target, activador, fase, historial, baseline_tiempo, warning.

---

## `state.py` — Estado thread-local

Cada canal (hilo worker) tiene sus propias variables:

| Variable | Tipo | Descripción |
|---|---|---|
| `active_game` | str o None | Nombre del juego activo ("ahorcado", "detector", ...) |
| `game_data` | dict | Datos del juego en curso |
| `scores` | dict | Puntuaciones nick→puntos (persiste en sesión) |
| `current_channel` | str | Canal actual (se setea antes de cada dispatch) |
| `start_time` | float | Timestamp de arranque del bot (global, para uptime) |

---

## `debug.py` — Modo test local

Simulador IRC en terminal. Uso: `python debug.py [--nick TuNick]`

- Llama a `db.init_db()` al arrancar → crea `./data/irc_bot.db` si no existe.
- Setea `state.current_channel = "debug"` antes de cada dispatch.
- Permite probar comandos (incluyendo `ahorcado puntos`, scoring en DB) sin conectarse al servidor.
- **Nota:** Los timers de inactividad del ahorcado no se disparan en debug (el bus no tiene queues registradas), pero el juego funciona con normalidad.

---

## Despliegue

- **Plataforma:** Fly.io
- **Dockerfile:** `python:3.12-slim`, instala `requirements.txt`, ejecuta `python -u bot.py`. Incluye `ENV DB_PATH=/data/irc_bot.db` y `RUN mkdir -p /data`.
- **Healthcheck:** HTTP server en puerto 9180, responde `{"success":"ok"}` a cualquier GET.
- **Configuración Fly:** `fly.toml` — `auto_stop_machines = 'off'`, `min_machines_running = 1` (siempre activo).
- **Volumen persistente:** montado en `/data` (fuente: `irc_bot_data`). Persiste la DB entre reinicios y redespliegues.

### Primer despliegue (crear volumen)
```
fly volumes create irc_bot_data --region ams --size 1
```

---

## Ideas de juegos pendientes de implementar

Ideas discutidas para juegos de relaciones/amor entre usuarios del canal:

- **Flechazo:** `steve flechazo @nick` — match bilateral si ambos se lanzan flecha en 5 min.
- **Compatibilidad:** `steve compatibilidad @nick` — % absurdo basado en los nicks, hora, etc.
- **Cita a ciegas:** `steve cita` — los usuarios se apuntan, el bot hace parejas y asigna temas.
- **Semáforo:** `steve semaforo` + `steve estado verde/amarillo/rojo` — estado romántico público.
- **Verdad o Reto amoroso:** preguntas personales por turnos, el canal vota si fue sincero.
- **El Gancho:** `steve gancho @nick1 @nick2` — celestino que presenta dos nicks, gana puntos si hacen match.
- **Radar:** `steve radar` — lista usuarios con su estado romántico autopuesto.
- **Encuadre:** el bot elige dos usuarios al azar y los "encuadra", reaccionan con acepto/jamás.

---

## Convenciones de desarrollo

- Cada comando es un fichero en `commands/` con `run(args, nick)` y `DESCRIPTION`.
- Si el comando es un juego que captura input libre, implementar también `handle_input(texto, nick)`.
- `run()` y `handle_input()` devuelven `str`, `list[str]`, o `None` (sin respuesta).
- El bot importa `state` dentro de las funciones (no en el módulo) para evitar problemas de circularidad.
- Los comandos no deben usar `send()` directamente; solo devolver la respuesta.
- Para timers u otros eventos asíncronos: usar `bus.emit()` para inyectar un evento dict en la queue del canal. El worker lo procesa con `cmd` (dispatch) o `msg` (handle_input).
- Para añadir un juego: crear fichero en `commands/`, añadir el comando a los canales que corresponda en `channels.json`. Si el juego usa timers, cancelarlos también en `fin.py`.
- Colores IRC: usar los códigos mIRC definidos en `ahorcado.py` como referencia (`\x03NN`, `\x02`, `\x0f`).
