"""Pruebas del revisor: que avise de lo que rompe el mapeo."""
import os
import struct
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pichabuild.revisar import revisar


def _sf2(ruta, zonas, n_muestras=None, con_instrumento=True):
    """SF2 minimo: zonas = lista de dicts {keys:(lo,hi) o None, root:int|None}."""
    n_muestras = n_muestras if n_muestras is not None else max(1, len(zonas))
    def _n20(s):
        b = s.encode("latin1")[:19]
        return b + b"\0" * (20 - len(b))
    def _chunk(cid, data):
        return cid + struct.pack("<I", len(data)) + data + (b"\0" if len(data) & 1 else b"")
    def _lista(t, *ch):
        c = b"".join(ch)
        return b"LIST" + struct.pack("<I", len(t) + len(c)) + t + c

    smpl, shdr = b"", []
    pos = 0
    for k in range(n_muestras):
        seg = b"\0" * 200
        shdr.append(struct.pack("<20sIIIIIBbHH", _n20(f"m{k}"), pos, pos + 100,
                                pos + 20, pos + 90, 44100, 60, 0, 0, 1))
        smpl += seg
        pos += 100

    igen, ibag = [], []
    for z in zonas:
        ibag.append(struct.pack("<HH", len(igen), 0))
        if z.get("keys") is not None:
            lo, hi = z["keys"]
            igen.append(struct.pack("<HH", 43, (lo & 0xFF) | ((hi & 0xFF) << 8)))
        if z.get("root") is not None:
            igen.append(struct.pack("<HH", 58, z["root"] & 0xFFFF))
        igen.append(struct.pack("<HH", 53, z.get("sid", 0)))
    ibag.append(struct.pack("<HH", len(igen), 0))
    igen.append(b"\0" * 4)

    if con_instrumento:
        inst = struct.pack("<20sH", _n20("i"), 0) + struct.pack("<20sH", _n20("EOI"), len(ibag))
    else:
        inst = struct.pack("<20sH", _n20("EOI"), 0)

    phdr = struct.pack("<20sHHHIII", _n20("p"), 0, 0, 0, 0, 0, 0) + \
           struct.pack("<20sHHHIII", _n20("EOP"), 0, 0, 1, 0, 0, 0)
    cuerpo = b"sfbk" + _lista(b"INFO") + _lista(b"sdta", _chunk(b"smpl", smpl)) + _lista(
        b"pdta", _chunk(b"phdr", phdr), _chunk(b"pbag", b"\0" * 4),
        _chunk(b"pmod", b"\0" * 10), _chunk(b"pgen", b"\0" * 4),
        _chunk(b"inst", inst), _chunk(b"ibag", b"".join(ibag)),
        _chunk(b"imod", b"\0" * 10), _chunk(b"igen", b"".join(igen)),
        _chunk(b"shdr", b"".join(shdr) + struct.pack(
            "<20sIIIIIBbHH", _n20("EOS"), 0, 0, 0, 0, 0, 0, 0, 0, 0)))
    open(ruta, "wb").write(b"RIFF" + struct.pack("<I", len(cuerpo)) + cuerpo)


def test_sin_instrumento_es_error(tmp_path):
    p = tmp_path / "a.sf2"
    _sf2(p, [{"keys": (60, 60), "root": 60}], con_instrumento=False)
    ok, av, dat = revisar(str(p))
    assert ok is False
    assert any("instrumento" in t for _, t in av)


def test_zonas_sin_keyrange_es_error(tmp_path):
    """El fallo clasico: todas sin keyRange -> colapsa a una zona."""
    p = tmp_path / "b.sf2"
    _sf2(p, [{"keys": None, "root": 60}] * 8)
    ok, av, dat = revisar(str(p))
    assert ok is False
    assert any("keyRange" in t and "colapsa" in t for _, t in av)


def test_zona_que_cubre_todo_avisa(tmp_path):
    """Una zona 0-127 se come a las demas."""
    p = tmp_path / "c.sf2"
    _sf2(p, [{"keys": (0, 127), "root": 60}] + [{"keys": (60 + i, 60 + i), "root": 60 + i}
                                                for i in range(4)])
    ok, av, dat = revisar(str(p))
    assert any("0-127" in t for _, t in av), av


def test_sin_rootkey_avisa(tmp_path):
    p = tmp_path / "d.sf2"
    _sf2(p, [{"keys": (60 + i, 60 + i), "root": None} for i in range(5)])
    ok, av, dat = revisar(str(p))
    assert dat["con_rootkey"] == 0
    assert any("rootKey" in t for _, t in av)


def test_sf2_bien_formado_no_avisa(tmp_path):
    p = tmp_path / "e.sf2"
    _sf2(p, [{"keys": (60 + i, 60 + i), "root": 60 + i} for i in range(5)])
    ok, av, dat = revisar(str(p))
    assert ok is True
    assert av == [], av


def test_mayoria_sin_keyrange_es_error(tmp_path):
    """Una zona con tecla y doce sin: eso colapsa, tiene que ser ERROR."""
    p = tmp_path / "f.sf2"
    zonas = [{"keys": (60, 60), "root": 60}] + [{"keys": None, "root": None}] * 12
    _sf2(p, zonas, n_muestras=13)
    ok, av, dat = revisar(str(p))
    assert ok is False
    assert any(t == "ERROR" and "keyRange" in x for t, x in av), av
