#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pichabuild.pregunta — cuando el afinador duda, pregunta a Miguel.

Directriz 8: si duda, no adivina. Se pregunta.
Directriz 6: el afinador decide... salvo cuando no esta seguro.

La pregunta se hace por fichero, con las candidatas y su peso, para que se
pueda contestar en un segundo.
"""
import json
import os
import subprocess

from .core import nombre_nota
from .nota import decidir_nota

# donde se guardan las respuestas, para no preguntar dos veces lo mismo
RESPUESTAS = os.path.expanduser("~/pichabuild/respuestas.json")


def _cargar_respuestas():
    if os.path.exists(RESPUESTAS):
        try:
            return json.load(open(RESPUESTAS))
        except Exception:
            return {}
    return {}


def _guardar_respuestas(r):
    os.makedirs(os.path.dirname(RESPUESTAS), exist_ok=True)
    json.dump(r, open(RESPUESTAS, "w"), indent=1, ensure_ascii=False)


def _reproducir(ruta):
    """Deja sonar la muestra para poder juzgar de oido."""
    for cmd in (["pw-play", ruta], ["paplay", ruta], ["aplay", "-q", ruta]):
        try:
            subprocess.run(cmd, check=True, timeout=30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue
    return False


def preguntar(ruta, resultado, respuestas, entrada=True):
    """Pregunta la nota de un archivo. Devuelve el midi elegido (o None).

    resultado = lo que devolvio decidir_nota()
    """
    nombre = os.path.basename(ruta)
    if nombre in respuestas:
        return respuestas[nombre]

    cands = resultado.get("candidatas") or []
    print()
    print(f"  ── DUDA: {nombre}")
    print(f"     motivo: {resultado.get('motivo')}")
    if cands:
        print("     candidatas:")
        for m, peso in cands[:5]:
            print(f"        [{m:3d}] {nombre_nota(m):5s}   peso {peso:.2f}")
    print()
    print("     teclea el MIDI (o la nota, p.ej. C4) y Enter.")
    print("     [s] sonar la muestra   [x] saltar esta   [q] terminar")
    while True:
        try:
            r = input(f"     {nombre} > ").strip()
        except EOFError:
            return None
        if r.lower() == "q":
            raise KeyboardInterrupt
        if r.lower() == "x":
            return -1
        if r.lower() == "s":
            _reproducir(ruta)
            continue
        m = _interpretar(r)
        if m is not None:
            respuestas[nombre] = m
            _guardar_respuestas(respuestas)
            return m
        print("     no entendido. MIDI 0-127 o nota tipo C4 / F#3 / A#2.")


def _interpretar(r):
    r = r.strip()
    if not r:
        return None
    if r.lstrip("-").isdigit():
        v = int(r)
        return v if 0 <= v <= 127 else None
    letras = "CDEFGAB"
    s = r.replace("♯", "#").replace("♭", "b").replace(" ", "")
    if len(s) < 2:
        return None
    n = s[0].upper()
    if n not in letras:
        return None
    i = 1
    semis = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[n]
    if i < len(s) and s[i] in "#b":
        semis += 1 if s[i] == "#" else -1
        i += 1
    try:
        octava = int(s[i:])
    except ValueError:
        return None
    return semis + 12 * (octava + 1)


if __name__ == "__main__":
    import sys
    r = decidir_nota(sys.argv[1])
    print(r)
