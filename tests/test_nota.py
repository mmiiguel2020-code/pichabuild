"""Pruebas de pichabuild.nota — el afinador decide o duda, nunca adivina."""
import os
import struct
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pichabuild.nota import decidir_nota, _cents_de


def _tono(ruta, hz, sr=48000, dur=1.0, armonicos=((1, 1.0),)):
    n = int(sr * dur)
    t = np.arange(n) / sr
    x = np.zeros(n)
    for k, amp in armonicos:
        x += amp * np.sin(2 * np.pi * hz * k * t)
    x = x / np.max(np.abs(x)) * 0.7
    datos = (x * 32767).astype("<i2").tobytes()
    fmt = struct.pack("<HHIIHH", 1, 1, sr, sr * 2, 2, 16)
    cuerpo = (b"fmt " + struct.pack("<I", len(fmt)) + fmt +
              b"data" + struct.pack("<I", len(datos)) + datos)
    open(ruta, "wb").write(b"RIFF" + struct.pack("<I", 4 + len(cuerpo)) + b"WAVE" + cuerpo)


def test_nota_clara_fundamental_fuerte():
    """Un 440 Hz limpio (mucho fundamental) debe salir A4 sin duda."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.wav")
        _tono(p, 440.0)
        r = decidir_nota(p)
        assert r["duda"] is False, r
        assert r["midi"] == 69, r
        assert abs(r["cents"]) < 5


def test_cents_de_banda_anclada():
    """Mide el cents de un desvio conocido, con la banda anclada."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "b.wav")
        hz = 440.0 * 2 ** (25 / 1200.0)
        _tono(p, hz)
        c = _cents_de(p, 69)
        assert c is not None
        assert abs(c - 25.0) < 3.0, c


def test_muestra_cortisima_duda():
    """Menos de 1024 muestras: no se atreve, pregunta."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "c.wav")
        _tono(p, 440.0, dur=0.005)   # 240 muestras
        r = decidir_nota(p)
        assert r["duda"] is True
