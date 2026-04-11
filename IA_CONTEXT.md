# IA_CONTEXT — IRC Bot SteveMacuin

Guía de contexto completa para continuar el desarrollo en nuevas sesiones.

> **IMPORTANTE:** Cualquier cambio en la aplicación (nuevos comandos, modificaciones de arquitectura, nuevos canales, cambios en el despliegue, etc.) debe reflejarse en este fichero antes de cerrar la sesión. Este documento es la fuente de verdad para retomar el desarrollo en futuras sesiones.

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
    ├── bot.py              # Núcleo: conexión SSL, loop principal, routing
    ├── channels.py         # Carga channels.json, filtra comandos por canal, welcome
    ├── channels.json       # Configuración de canales (comandos permitidos, welcome)
    ├── state.py            # Estado thread-local por canal (active_game, game_data, scores)
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

### Threading

- Un hilo lector principal recibe toda la actividad IRC.
- Un hilo worker por canal, cada uno con su propia `queue.Queue`.
- El lector principal enruta cada `PRIVMSG` al worker del canal correspondiente.
- `state.py` usa `threading.local()` para que cada canal tenga su propio `active_game` y `game_data`.

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

---

## Canales configurados

| Canal | Comandos permitidos | Notas |
|---|---|---|
| `debug` | help, ahorcado, fin | Solo para pruebas, no se conecta |
| `#skateros` | todos | Canal general, sin restricción |
| `#ahorcado` | help, ahorcado, fin | Canal dedicado al juego |
| `#mentiras` | help, detector, fin | Canal dedicado al detector |

Para añadir un canal: editar `channels.json` con `channel`, `commands` y `welcome`.

---

## Comandos implementados

### `help`
Lista los comandos disponibles en el canal actual.

### `dado [caras]`
Tira un dado. Por defecto 6 caras. Uso: `steve dado 20`

### `fin`
Termina cualquier juego activo en el canal. Limpia `state.active_game` y `state.game_data`.

### `metrica`
Muestra uptime, RAM, CPU y versión. Usa `psutil`. Lee `version.txt`.

### `ahorcado`
Juego del ahorcado multijugador. Palabras desde `datos/palabras_ahorcado.json`.
- Múltiples jugadores simultáneos, cada uno con sus propios fallos (máx 6).
- Se puede adivinar letra a letra o la palabra completa.
- Lleva puntuación en `state.scores` (persiste durante la sesión).
- Estado: `active_game = "ahorcado"`, `game_data` contiene palabra, adivinadas, falladas, jugadores.

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

## Despliegue

- **Plataforma:** Fly.io
- **Dockerfile:** `python:3.12-slim`, instala `requirements.txt`, ejecuta `python -u bot.py`
- **Healthcheck:** HTTP server en puerto 9180, responde `{"success":"ok"}` a cualquier GET. Fly.io lo usa para saber que el proceso está vivo.
- **Configuración Fly:** `fly.toml` — `auto_stop_machines = 'off'`, `min_machines_running = 1` (siempre activo).

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
- Para añadir un juego: crear fichero en `commands/`, añadir el comando a los canales que corresponda en `channels.json`.
