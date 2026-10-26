#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pichabuild.core — la base: leer, medir y preparar muestras.

ETAPA 1 (esta): rectificar AFINACION y NOMBRE. Nada mas.

Directrices que respeta (docs/DIRECTRICES.md):
  1  el bucle no se toca      -> aqui solo se MIRA si existe
  5  el musette no se corrige -> la afinacion es al 0; el +15 lo pone el SF2
  6  el afinador es el juez   -> la nota la decide la medicion, no el nombre
  7  el bucle solo se mira    -> se comprueba el chunk 'smpl', sin interpretarlo
"""
import os
import re
import struct
import wave

import numpy as np

NOMBRES_EN = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
UMBRAL_CENTS = 0.5          # por debajo de esto ya esta afinada: no se toca


# ---------------------------------------------------------------- nombres ----
def nombre_nota(midi):
    """60 -> 'C4'  (notacion inglesa, C4 = Do central)."""
    return f"{NOMBRES_EN[int(midi) % 12]}{int(midi) // 12 - 1}"


def nombre_limpio(midi, toma=None, ext=".wav"):
    """Nombre canonico:  C4.wav  ·  G#3_2.wav  ·  A4_1.wav

    Nunca lleva ajuste (+50, ?, -2): el nombre dice solo la nota que suena.
    """
    base = nombre_nota(midi)
    if toma is not None:
        base += f"_{int(toma)}"
    return base + ext


# ------------------------------------------------------------------ wav ----
def chunks_wav(ruta):
    """Lista de (id, offset_datos, tam). Sin interpretar nada."""
    d = open(ruta, "rb").read()
    if d[:4] != b"RIFF" or d[8:12] != b"WAVE":
        raise ValueError(f"no es WAV: {ruta}")
    pos, out = 12, []
    while pos + 8 <= len(d):
        cid = d[pos:pos + 4]
        sz = struct.unpack("<I", d[pos + 4:pos + 8])[0]
        out.append((cid, pos + 8, sz))
        pos += 8 + sz + (sz & 1)
    return out


def tiene_loop(ruta):
    """SÍ/NO: ¿el WAV trae un loop declarado?

    Directriz 7: se pregunta si existe; NO se interpretan ni validan los
    valores. Devuelve (tiene, detalle).
    """
    try:
        ch = dict((c, (o, s)) for c, o, s in chunks_wav(ruta))
    except Exception as e:
        return False, f"error leyendo: {e}"
    if b"smpl" not in ch:
        return False, "sin chunk 'smpl'"
    off, sz = ch[b"smpl"]
    d = open(ruta, "rb").read()
    if sz < 36:
        return False, "chunk 'smpl' demasiado corto"
    # estructura: 9 x uint32. numSampleLoops esta en el byte 28 (+8 por chunk).
    nloops = struct.unpack("<I", d[off + 28:off + 32])[0]
    return nloops > 0, f"numSampleLoops={nloops}"


# ---------------------------------------------------------------- audacia ----
def medir_cents(ruta, midi_esperado, a4=440.0):
    """Desviacion en cents de la muestra respecto de la nota esperada.

    Banda ANCLADA: busca solo +-2 semitonos alrededor de la nota esperada.
    Asi no salta de octava (Directriz 6). Usa autocorrelacion sobre 0.3 s
    del centro, que es estable.
    """
    with wave.open(ruta, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
        canales = w.getnchannels()
        ancho = w.getsampwidth()
    if ancho == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif ancho == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = (b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16))
        v = np.where(v >= 1 << 23, v - (1 << 24), v)
        x = v.astype(np.float64) / 8388608.0
    else:
        raise ValueError(f"ancho de muestra no soportado: {ancho}")
    if canales > 1:
        x = x.reshape(-1, canales).mean(axis=1)

    c = len(x) // 2
    w_ = min(int(0.15 * sr), c)
    seg = x[c - w_:c + w_]
    if len(seg) < 512:
        seg = x
    obj = a4 * 2 ** ((midi_esperado - 69) / 12.0)

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
        a, b2, c2 = ac[i - 1], ac[i], ac[i + 1]
        den = a - 2 * b2 + c2
        i = i + (0.5 * (a - c2) / den if abs(den) > 1e-12 else 0)
    f = sr / i
    return 1200.0 * np.log2(f / obj)
