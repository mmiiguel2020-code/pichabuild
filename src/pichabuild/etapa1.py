#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pichabuild.etapa1 — rectificar AFINACION y NOMBRE de una carpeta de WAV.

Directrices:
  1/7  el bucle no se toca: solo se pregunta si existe
  5    el musette no se corrige: se afina al 0, el +15 lo pone el SF2
  6    el afinador es el juez
  8    busca en todo el rango; si duda, pregunta
"""
import os
import shutil
import sys
import tempfile
import wave

import numpy as np

try:
    import librosa
except ImportError:
    librosa = None

from .core import UMBRAL_CENTS, nombre_limpio, nombre_nota, tiene_loop
from .nota import decidir_nota
from .pregunta import _cargar_respuestas, preguntar

REBUCLEO = os.path.expanduser("~/Escritorio/REBUCLEO")


def _resample(x, sr, r):
    if librosa is not None:
        return librosa.resample(x.T, orig_sr=sr, target_sr=sr / r,
                                res_type="soxr_hq", axis=-1).T
    n = len(x)
    pos = np.arange(0, n, r)
    return np.interp(pos, np.arange(n), x)


def _escribir_wav(ruta, x, sr):
    y = np.clip(x, -1.0, 0.9999)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((y * 32767.0).astype("<i2").tobytes())


def procesar_carpeta(entrada, salida, log=print, preguntar_dudas=True):
    os.makedirs(salida, exist_ok=True)
    os.makedirs(REBUCLEO, exist_ok=True)
    respuestas = _cargar_respuestas()
    archivos = sorted(f for f in os.listdir(entrada) if f.lower().endswith(".wav"))
    informe = []

    for f in archivos:
        ruta = os.path.join(entrada, f)
        filas = {"archivo": f}
        try:
            # --- 1. decidir la nota (todo el rango; si duda, preguntar) ---
            r = decidir_nota(ruta)
            if r["duda"]:
                if not preguntar_dudas:
                    filas.update(estado="DUDOSA", motivo=r.get("motivo"))
                    informe.append(filas)
                    continue
                midi = preguntar(ruta, r, respuestas)
                if midi is None or midi == -1:
                    filas.update(estado="SALTADA", motivo=r.get("motivo"))
                    log(f"  {f}: saltada")
                    informe.append(filas)
                    continue
                filas["preguntada"] = True
                cents = 0.0
                if r.get("midi") == midi and r.get("cents") is not None:
                    cents = r["cents"]
            else:
                midi = r["midi"]
                cents = r["cents"]

            filas.update(nota=nombre_nota(midi), midi=int(midi),
                         cents=round(float(cents), 2))

            # --- 2. afinar si hace falta ---
            afinada = abs(cents) >= UMBRAL_CENTS
            if afinada:
                with wave.open(ruta, "rb") as w:
                    sr, ch = w.getframerate(), w.getnchannels()
                    raw = w.readframes(w.getnframes())
                x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
                if ch > 1:
                    x = x.reshape(-1, ch).mean(axis=1)
                rr = 2 ** (-cents / 1200.0)
                y = _resample(x, sr, rr)
                destino = tempfile.mktemp(suffix=".wav", dir=salida)
                _escribir_wav(destino, y, sr)
                filas.update(afinada=True, factor=round(float(rr), 6))
            else:
                destino = ruta
                filas["afinada"] = False

            # --- 3. nombre nuevo ---
            nuevo = nombre_limpio(midi)
            filas["nombre_nuevo"] = nuevo

            # --- 4. destino ---
            tiene, detalle = tiene_loop(destino)
            filas["loop"] = detalle
            if afinada or not tiene:
                filas["destino"] = "REBUCLEO"
                shutil.copy2(destino, os.path.join(REBUCLEO, nuevo))
            else:
                filas["destino"] = "salida"
                shutil.copy2(destino, os.path.join(salida, nuevo))
            if destino != ruta:
                os.unlink(destino)

            log(f"  {f}: {nombre_nota(midi)} {cents:+.1f}c "
                f"{'afinada' if afinada else 'ya estaba'} · {detalle} "
                f"-> {nuevo} [{filas['destino']}]")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            filas.update(estado="ERROR", motivo=str(e))
            log(f"  {f}: ERROR {e}")
        informe.append(filas)

    return informe
