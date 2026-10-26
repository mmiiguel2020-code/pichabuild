"""Pruebas del SF2 base: de carpeta de WAV a SF2 con instrumento.

Lo critico: el AUDIO y el LOOP tienen que salir intactos (Directriz 1).
"""
import os
import struct
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pichabuild.base_sf2 import armar_desde_wavs, leer_loop, nota_de_nombre
from pichabuild.revisar import revisar


def _wav(ruta, hz=440.0, sr=44100, dur=0.3, loop=(1000, 2000)):
    n = int(sr * dur)
    t = np.arange(n) / sr
    x = np.sin(2 * np.pi * hz * t) * 0.5
    datos = (x * 32767).astype("<i2").tobytes()
    fmt = struct.pack("<HHIIHH", 1, 1, sr, sr * 2, 2, 16)
    c = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if loop:
        s = struct.pack("<9I", 0, 0, 20833, 69, 0, 0, 0, 1, 0) + \
            struct.pack("<6I", 0, 0, loop[0], loop[1], 0, 0)
        c += b"smpl" + struct.pack("<I", len(s)) + s
    c += b"data" + struct.pack("<I", len(datos)) + datos
    open(ruta, "wb").write(b"RIFF" + struct.pack("<I", 4 + len(c)) + b"WAVE" + c)


def test_nota_de_nombre():
    assert nota_de_nombre("C4.wav") == 60
    assert nota_de_nombre("G#3.wav") == 56
    assert nota_de_nombre("A#6_2.wav") == 94
    assert nota_de_nombre("C-1.wav") == 0
    assert nota_de_nombre("mestra numero 8.wav") is None


def test_leer_loop():
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "a.wav")
    _wav(p, loop=(1000, 2000))
    assert leer_loop(p) == (1000, 2000)


def test_armar_y_audio_intacto(tmp_path):
    ent = tmp_path / "wavs"; ent.mkdir()
    for n in ("C4.wav", "G#3.wav", "A4.wav"):
        _wav(ent / n)
    dst = tmp_path / "base.sf2"
    ok, inf = armar_desde_wavs(str(ent), str(dst), log=lambda s: None)
    assert ok and inf["zonas"] == 3
    # el revisor tiene que decir que esta bien
    ok2, av, dat = revisar(str(dst))
    assert ok2 is True, av
    assert dat["con_keyrange"] == 3 and dat["con_rootkey"] == 3


def test_el_motor_puede_leerlo(tmp_path):
    """El SF2 base tiene que poder abrirlo construir_sf2_acordeon.py."""
    ent = tmp_path / "wavs"; ent.mkdir()
    for n in ("C4.wav", "E4.wav"):
        _wav(ent / n)
    dst = tmp_path / "base.sf2"
    armar_desde_wavs(str(ent), str(dst), log=lambda s: None)
    sys.path.insert(0, os.path.expanduser("~/herramientas"))
    from construir_sf2_acordeon import SF2Fuente, zonas_utiles
    src = SF2Fuente(str(dst))
    z = zonas_utiles(src, 0)
    assert len(z) == 2
    assert all(x["lokey"] == x["hikey"] for x in z)


def test_sin_loop_se_salta(tmp_path):
    ent = tmp_path / "wavs"; ent.mkdir()
    _wav(ent / "C4.wav", loop=None)
    _wav(ent / "E4.wav")
    ok, inf = armar_desde_wavs(str(ent), str(tmp_path / "b.sf2"), log=lambda s: None)
    assert ok and inf["zonas"] == 1
