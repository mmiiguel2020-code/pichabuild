"""Pruebas de pichabuild.core — sin tocar nada real."""
import os
import struct
import sys
import tempfile
import wave

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pichabuild.core import (nombre_limpio, nombre_nota, tiene_loop)


def test_nombre_nota():
    assert nombre_nota(60) == "C4"
    assert nombre_nota(69) == "A4"
    assert nombre_nota(56) == "G#3"
    assert nombre_nota(21) == "A0"


def test_nombre_limpio_nunca_lleva_ajuste():
    # Directriz: el nombre dice la nota, NUNCA un ajuste
    assert nombre_limpio(56) == "G#3.wav"
    assert nombre_limpio(56, 2) == "G#3_2.wav"
    for n in (nombre_limpio(56), nombre_limpio(60, 3)):
        for malo in ("+", "-", "?", " "):
            assert malo not in n.replace(".wav", "").replace("_", "")


def _wav(ruta, smpl=True, nloops=1):
    sr = 44100
    x = (np.sin(2 * np.pi * 440 * np.arange(sr) / sr) * 8000).astype("<i2")
    fmt = struct.pack("<HHIIHH", 1, 1, sr, sr * 2, 2, 16)
    cuerpo = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if smpl:
        s = struct.pack("<9I", 0, 0, 20833, 69, 0, 0, 0, nloops, 0)
        if nloops:
            s += struct.pack("<6I", 0, 0, 1000, 2000, 0, 0)
        cuerpo += b"smpl" + struct.pack("<I", len(s)) + s
    cuerpo += b"data" + struct.pack("<I", len(x.tobytes())) + x.tobytes()
    open(ruta, "wb").write(b"RIFF" + struct.pack("<I", 4 + len(cuerpo)) + b"WAVE" + cuerpo)


def test_tiene_loop_si():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.wav")
        _wav(p, smpl=True, nloops=1)
        ok, det = tiene_loop(p)
        assert ok is True
        assert "numSampleLoops=1" in det


def test_tiene_loop_sin_chunk():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "b.wav")
        _wav(p, smpl=False)
        ok, det = tiene_loop(p)
        assert ok is False
        assert "smpl" in det


def test_tiene_loop_cero_loops():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "c.wav")
        _wav(p, smpl=True, nloops=0)
        ok, det = tiene_loop(p)
        assert ok is False
