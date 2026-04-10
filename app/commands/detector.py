import time
import random
import re

DESCRIPTION = "Detector de mentiras. Uso: steve detector <nick>"

# ─── Preguntas de control ─────────────────────────────────────────────────────

CONTROL_QUESTIONS = [
    {
        "texto": "[CONTROL {n}/3] {nick}: ¿Es verdad que tu nick es {nick}?",
        "tipo":  "nick",
    },
    {
        "texto": "[CONTROL {n}/3] {nick}: ¿De qué color es el caballo blanco de Santiago?",
        "tipo":  "caballo",
    },
    {
        "texto": "[CONTROL {n}/3] {nick}: ¿Confirmas que participas voluntariamente en esta sesión?",
        "tipo":  "voluntario",
    },
]

def _fmt(q, nick, n):
    return q["texto"].format(n=n, nick=nick)

def _evaluar_control(tipo, respuesta, nick):
    r = respuesta.lower().strip()
    if tipo == "nick":
        return any(x in r for x in ("si", "sí", "yes", "claro", "correcto", "cierto", nick.lower()))
    if tipo == "caballo":
        return "blanco" in r or "white" in r
    if tipo == "voluntario":
        return any(x in r for x in ("si", "sí", "yes", "claro", "confirmo", "voluntariamente", "acepto"))
    return True

# ─── Análisis de veracidad ────────────────────────────────────────────────────

def _errores_ortograficos(texto):
    """Heurística: consonantes sin vocal, l33t, puntuación caótica."""
    score = 0
    for palabra in texto.split():
        if len(palabra) > 3 and not re.search(r'[aeiouáéíóúü]', palabra, re.I):
            score += 1
    if re.search(r'[0-9][a-zA-Z]|[a-zA-Z][0-9]', texto):
        score += 1
    if texto.count("...") > 2:
        score += 1
    return score

def _ilegibilidad(texto):
    """Detecta mensajes ilegibles o evasivos."""
    score = 0
    if len(texto.strip()) < 3:
        score += 3
    if texto.isupper() and len(texto) > 5:
        score += 1
    if len(set(texto.lower())) < 4 and len(texto) > 4:
        score += 2   # ej: "jajajajaja"
    if texto.count("?") > 2 or texto.count("!") > 3:
        score += 1
    palabras = texto.split()
    if 1 <= len(palabras) <= 2 and len(texto) < 10:
        score += 1   # respuesta evasiva muy corta
    return score

def _score_tiempo(segundos, baseline):
    """Puntuación de sospecha según tiempo de respuesta (0 = normal, >0 = sospechoso)."""
    if baseline is None:
        if segundos < 2:
            return 2   # reacción instantánea = sospechoso
        if segundos <= 20:
            return 0
        if segundos <= 50:
            return 1
        return 2
    ratio = segundos / max(baseline, 1)
    if ratio < 0.25:
        return 2    # mucho más rápido que en calibración
    if ratio < 0.55:
        return 1
    if ratio <= 2.2:
        return 0    # rango normal
    if ratio <= 4.0:
        return 1
    return 2        # tardó el triple que en calibración

def _decidir(d, texto, elapsed):
    """Devuelve 'verdad' o 'falso' según análisis combinado."""
    score = 0

    score += _score_tiempo(elapsed, d.get("baseline_tiempo"))
    score += min(_errores_ortograficos(texto), 3)
    score += min(_ilegibilidad(texto), 3)

    historial = d.get("historial", [])
    if len(historial) >= 3:
        falsos_recientes = sum(1 for h in historial[-3:] if h["veredicto"] == "falso")
        if falsos_recientes >= 2:
            score += 1   # patron sostenido de sospecha
        elif falsos_recientes == 0:
            score -= 1   # patron consistentemente limpio

    if d.get("warning"):
        score += 1   # penalización por fallar preguntas de control

    # Ruido simulado del "sensor"
    score += random.choice([-1, -1, 0, 0, 0, 0, 1])

    return "falso" if score >= 2 else "verdad"

# ─── Interfaz del comando ─────────────────────────────────────────────────────

def run(args, nick):
    import state
    if state.active_game:
        return f"{nick}: ya hay un juego activo ({state.active_game}). Usa 'steve fin' para terminarlo."

    if not args:
        return f"{nick}: uso: steve detector <nick>"

    target = args[0]
    state.active_game = "detector"
    state.game_data = {
        "target":           target,
        "activador":        nick,
        "fase":             "control",
        "ctrl_idx":         0,
        "ctrl_passes":      0,
        "ctrl_fails":       0,
        "warning":          False,
        "baseline_tiempos": [],
        "baseline_tiempo":  None,
        "ultimo_tiempo":    time.time(),
        "historial":        [],
    }

    primera = _fmt(CONTROL_QUESTIONS[0], target, 1)
    return [
        f"*** DETECTOR DE MENTIRAS ACTIVADO para {target} (por {nick}) ***",
        "Iniciando calibracion con 3 preguntas de control...",
        primera,
    ]

def handle_input(texto, nick):
    import state
    d      = state.game_data
    target = d.get("target", "")

    if nick.lower() != target.lower():
        return None

    ahora     = time.time()
    elapsed   = ahora - d["ultimo_tiempo"]
    d["ultimo_tiempo"] = ahora

    # ── Fase de control ───────────────────────────────────────────────────────
    if d["fase"] == "control":
        idx  = d["ctrl_idx"]
        q    = CONTROL_QUESTIONS[idx]
        paso = _evaluar_control(q["tipo"], texto, target)

        if paso:
            d["ctrl_passes"] += 1
            d["baseline_tiempos"].append(elapsed)
            estado_ctrl = "CORRECTO"
        else:
            d["ctrl_fails"] += 1
            estado_ctrl = "INCORRECTO"

        d["ctrl_idx"] += 1
        salida = [f"  >> Respuesta de control {idx+1}/3: {estado_ctrl}"]

        if d["ctrl_idx"] >= len(CONTROL_QUESTIONS):
            # Calcular baseline de tiempo
            if d["baseline_tiempos"]:
                d["baseline_tiempo"] = sum(d["baseline_tiempos"]) / len(d["baseline_tiempos"])

            if d["ctrl_fails"] > 0:
                d["warning"] = True
                salida.append(
                    f"[!] AVISO: {target} fallo {d['ctrl_fails']}/3 preguntas de control. "
                    "Las preguntas de control no garantizan la veracidad de este detector."
                )
            else:
                salida.append(f"Calibracion completada. {target} supero todas las pruebas de control.")

            d["fase"] = "monitoreo"
            salida.append(f"*** MONITOREO ACTIVO: analizando cada mensaje de {target} ***")
        else:
            siguiente = CONTROL_QUESTIONS[d["ctrl_idx"]]
            salida.append(_fmt(siguiente, target, d["ctrl_idx"] + 1))

        return salida

    # ── Fase de monitoreo ─────────────────────────────────────────────────────
    veredicto = _decidir(d, texto, elapsed)
    d["historial"].append({"texto": texto, "veredicto": veredicto, "tiempo": elapsed})

    if veredicto == "falso":
        return f"[FALSO] El detector indica que {target} esta mintiendo."
    else:
        return f"[VERDAD] El detector no detecta engano en {target}."
