"""Pruebas del interprete de respuestas y de los nombres."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pichabuild.core import nombre_nota
from pichabuild.pregunta import _interpretar


def test_interpretar_midi():
    assert _interpretar("60") == 60
    assert _interpretar(" 69 ") == 69
    assert _interpretar("0") == 0
    assert _interpretar("127") == 127
    assert _interpretar("200") is None


def test_interpretar_notas():
    assert _interpretar("C4") == 60
    assert _interpretar("A4") == 69
    assert _interpretar("G#3") == 56
    assert _interpretar("A#2") == 46
    assert _interpretar("Bb2") == 46
    assert _interpretar("C-1") == 0
    assert _interpretar("c4") == 60


def test_interpretar_basura():
    for s in ("", "xx", "H4", "C", "C4x", "??"):
        assert _interpretar(s) is None, s


def test_ida_y_vuelta():
    for m in range(24, 97):
        assert _interpretar(nombre_nota(m)) == m
