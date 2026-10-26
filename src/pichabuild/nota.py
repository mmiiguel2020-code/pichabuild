#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pichabuild.nota — decidir QUE nota es una muestra, en todo el rango.

Directriz 8: se busca en todo el teclado; si hay duda, se pregunta a Miguel.

METODO (v3, 25 oct 2026)
------------------------
v1  sumaba bandas anchas -> todo parecia cualquier nota.
v2  buscaba picos, pero elegia como fundamental un ARMONICO alto (F5 cuando
    el fundamental era D3 a 143 Hz).
v3  la clave: **el fundamental es el pico MAS GRAVE que explica al resto.**

  1. Picos reales del espectro.
  2. Para cada pico f se pregunta: ¿los picos de arriba son multiplos ENTEROS
     de f (2f, 3f, 4f...)? Se le da un peso por cuantos casan.
  3. Se ordenan las frecuencias: el fundamental es la **mas grave** cuya
     puntuacion este cerca de la mejor. No se puede "subir" a un armonico
     si debajo hay uno que ya explica todo.
  4. La nota MIDI sale de esa frecuencia; el cents, de banda anclada.
  5. Si dos frecuencias muy distintas empatan -> duda.
"""
import wave

import numpy as np

NOMBRES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MIDI_MIN, MIDI_MAX = 21, 96
TOL_CENTS = 45          # para casar un pico con un armonico
REL_PICO = 0.02


def _leer(ruta):
    from .core import leer_pcm
    return leer_pcm(ruta)


def _espectro(x, sr):
    c = len(x) // 2
    w = min(int(0.5 * sr), c)
    seg = x[c - w:c + w] if c > w else x
    if len(seg) < 2048:
        seg = x
    seg = (seg - seg.mean()) * np.hanning(len(seg))
    nfft = 1 << 19
    e = np.abs(np.fft.rfft(seg, n=nfft))
    f = np.fft.rfftfreq(nfft, 1.0 / sr)
    return e, f


def _picos(e, f, rel=REL_PICO):
    mx = e.max()
    if mx <= 0:
        return np.array([]), np.array([])
    m = e >= rel * mx
    idx, i, n = [], 0, len(e)
    while i < n:
        if not m[i]:
            i += 1
            continue
        j = i
        while j < n and m[j]:
            j += 1
        idx.append(i + int(np.argmax(e[i:j])))
        i = j
    idx = np.array(idx, dtype=int)
    return f[idx], e[idx]


def _casa(pf, pe, hz, tol=TOL_CENTS):
    if len(pf) == 0:
        return 0.0
    lo, hi = hz * 2 ** (-tol / 1200), hz * 2 ** (tol / 1200)
    m = (pf >= lo) & (pf <= hi)
    return float(pe[m].max()) if m.any() else 0.0


def _puntuacion(f0, pf, pe):
    """Cuantos armonicos de f0 casan con picos reales, y cuanta energia suman."""
    e1 = _casa(pf, pe, f0)
    if e1 <= 0:
        return 0.0, 0, 0.0
    n_arm, suma = 0, 0.0
    for k in range(2, 9):
        if f0 * k >= pf[-1] if len(pf) else True:
            break
        e = _casa(pf, pe, f0 * k)
        if e > 0:
            n_arm += 1
            suma += e
    return suma + e1, n_arm, e1


def decidir_nota(ruta, a4=440.0):
    x, sr = _leer(ruta)
    if len(x) < 1024:
        return {"midi": None, "duda": True, "motivo": "muestra demasiado corta",
                "candidatas": []}

    e, f = _espectro(x, sr)
    pf, pe = _picos(e, f)
    if len(pf) < 2:
        return {"midi": None, "duda": True, "motivo": "sin picos suficientes",
                "candidatas": []}

    # --- puntuar CADA pico como posible fundamental ---
    cands = []
    for i in range(len(pf)):
        f0 = pf[i]
        if f0 < 30 or f0 > sr / 2.5:
            continue
        p, n_arm, e1 = _puntuacion(f0, pf, pe)
        if p <= 0:
            continue
        cands.append((float(f0), p, n_arm))
    if not cands:
        return {"midi": None, "duda": True, "motivo": "sin candidatos",
                "candidatas": []}

    cands.sort(key=lambda c: -c[1])
    mejor_p = cands[0][1]

    # --- REGLA CLAVE: el fundamental es el MAS GRAVE que explica casi todo ---
    # (si un armonico alto tambien "explica" todo, vale mas el de abajo)
    graves = [c for c in cands if c[1] >= 0.80 * mejor_p]
    graves.sort(key=lambda c: c[0])
    f0 = graves[0][0]

    midi_f = 69 + 12 * np.log2(f0 / a4)
    midi = int(round(midi_f))
    cents_midi = 100 * (midi_f - midi)

    cands_top = [(int(round(69 + 12 * np.log2(c[0] / a4))), round(c[1] / mejor_p, 3))
                 for c in cands[:5]]

    if not (MIDI_MIN <= midi <= MIDI_MAX):
        return {"midi": None, "duda": True,
                "motivo": f"fundamental {f0:.1f} Hz fuera de rango",
                "candidatas": cands_top}

    # --- duda: dos notas MIDI distintas con puntuacion parecida ---
    notas = {}
    for c in cands:
        m = int(round(69 + 12 * np.log2(c[0] / a4)))
        notas[m] = max(notas.get(m, 0.0), c[1])
    orden = sorted(notas.items(), key=lambda kv: -kv[1])
    if len(orden) > 1 and orden[1][1] > 0.75 * orden[0][1] and orden[1][0] != orden[0][0]:
        return {"midi": None, "duda": True,
                "motivo": (f"empatan {orden[0][0]} ({NOMBRES[orden[0][0]%12]}{orden[0][0]//12-1}) "
                           f"y {orden[1][0]} ({NOMBRES[orden[1][0]%12]}{orden[1][0]//12-1})"),
                "candidatas": cands_top}

    if abs(cents_midi) > 60:
        return {"midi": midi, "duda": True,
                "motivo": f"{cents_midi:+.1f} cents, demasiado lejos",
                "candidatas": cands_top}

    cents = _cents_de(ruta, midi, a4)
    if cents is None:
        cents = cents_midi
    return {"midi": midi, "cents": float(cents), "duda": False, "motivo": "",
            "fundamental_hz": round(f0, 2), "candidatas": cands_top}


def _cents_de(ruta, midi, a4=440.0):
    x, sr = _leer(ruta)
    obj = a4 * 2 ** ((midi - 69) / 12.0)
    c = len(x) // 2
    w = min(int(0.15 * sr), c)
    seg = x[c - w:c + w] if c > w else x
    s = (seg - seg.mean()) * np.hanning(len(seg))
    ac = np.correlate(s, s, mode="full")[len(s) - 1:]
    if ac[0] <= 0:
        return None
    ac /= ac[0]
    lo = max(2, int(sr / (obj * 2 ** (2 / 12))))
    hi = min(int(sr / (obj * 2 ** (-2 / 12))), len(ac) - 2)
    if hi <= lo:
        return None
    i = lo + int(np.argmax(ac[lo:hi]))
    if 0 < i < len(ac) - 1:
        a, b, c2 = ac[i - 1], ac[i], ac[i + 1]
        den = a - 2 * b + c2
        i = i + (0.5 * (a - c2) / den if abs(den) > 1e-12 else 0)
    return 1200.0 * np.log2((sr / i) / obj)
