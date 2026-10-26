"""Pruebas de la escucha: notas, MIDI y lectura de presets."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pichabuild.oir import a_midi, crear_midi, presets


def test_a_midi():
    assert a_midi("C4") == 60
    assert a_midi("A4") == 69
    assert a_midi("A#3") == 58
    assert a_midi("C-1") == 0
    assert a_midi("60") == 60


def test_crear_midi_una_nota():
    d = crear_midi(0, "C4")
    assert d[:4] == b"MThd"
    assert b"MTrk" in d
    # una sola nota encendida
    assert d.count(b"\x90") == 1


def test_crear_midi_escala():
    d = crear_midi(0, "escala")
    assert d.count(b"\x90") == 8


def test_sin_doble_delta_al_final():
    """El fin de pista lleva UN delta. Dos dan 'Unexpected end of file'."""
    d = crear_midi(0, "C4")
    # los ultimos 4 bytes tienen que ser: delta(=0x28), FF, 2F, 00
    assert d[-4:] == b"\xff\x2f\x00"[-3:] or d[-4] == 0x28, d[-6:].hex()
    assert d[-3:] == b"\xff\x2f\x00"


def test_presets_del_chido():
    p = os.path.expanduser("~/Escritorio/chido sf2.sf2")
    if not os.path.exists(p):
        return
    lista = presets(p)
    assert len(lista) == 5
    nombres = [n for n, _, _ in lista]
    assert "Clarinete" in nombres and "Master" in nombres
