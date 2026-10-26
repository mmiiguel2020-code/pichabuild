"""Pruebas de LOTE: que no se pierda ningún archivo al procesar muchos."""
import os
import shutil
import struct
import sys
import tempfile
import wave

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pichabuild.etapa1 as e1
from pichabuild.core import nombre_limpio


def _wav_con_nota(ruta, hz, sr=44100, dur=0.4, con_loop=True):
    n = int(sr * dur)
    t = np.arange(n) / sr
    x = np.sin(2 * np.pi * hz * t) * 0.5
    datos = (x * 32767).astype("<i2").tobytes()
    fmt = struct.pack("<HHIIHH", 1, 1, sr, sr * 2, 2, 16)
    cuerpo = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if con_loop:
        s = struct.pack("<9I", 0, 0, 20833, 69, 0, 0, 0, 1, 0) + \
            struct.pack("<6I", 0, 0, 1000, 2000, 0, 0)
        cuerpo += b"smpl" + struct.pack("<I", len(s)) + s
    cuerpo += b"data" + struct.pack("<I", len(datos)) + datos
    open(ruta, "wb").write(b"RIFF" + struct.pack("<I", 4 + len(cuerpo)) + b"WAVE" + cuerpo)


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    ent = tmp_path / "entrada"
    sal = tmp_path / "salida"
    reb = tmp_path / "rebucleo"
    ent.mkdir(); sal.mkdir(); reb.mkdir()
    monkeypatch.setattr(e1, "REBUCLEO", str(reb))
    return ent, sal, reb


def test_lote_no_pierde_archivos(entorno, monkeypatch):
    """Ocho archivos que caen en pocas notas: NO se pueden pisar."""
    ent, sal, reb = entorno
    # la misma nota (440) ocho veces -> antes quedaba UN archivo
    for i in range(8):
        _wav_con_nota(ent / f"a{i}.wav", 440.0, con_loop=False)
    monkeypatch.setattr(e1, "decidir_nota",
                        lambda r: {"midi": 69, "cents": 0.0, "duda": False,
                                   "motivo": "", "candidatas": []})
    inf = e1.procesar_carpeta(str(ent), str(sal), log=lambda s: None, preguntar_dudas=False)
    destinos = list(reb.glob("*.wav")) + list(sal.glob("*.wav"))
    assert len(destinos) == 8, f"se perdieron archivos: {len(destinos)} de 8"
    nombres = sorted(p.name for p in destinos)
    assert nombres == sorted([f"A4_{i}.wav" if i > 1 else "A4.wav" for i in range(1, 9)])


def test_temporal_no_ensucia_la_salida(entorno, monkeypatch):
    """El temporal NO puede quedar en la carpeta de salida."""
    ent, sal, reb = entorno
    _wav_con_nota(ent / "uno.wav", 440.0)
    monkeypatch.setattr(e1, "decidir_nota",
                        lambda r: {"midi": 69, "cents": 25.0, "duda": False,
                                   "motivo": "", "candidatas": []})
    e1.procesar_carpeta(str(ent), str(sal), log=lambda s: None, preguntar_dudas=False)
    sobrantes = [p.name for p in sal.iterdir() if p.suffix == ".wav"]
    # los .wav que haya tienen que ser resultados, no temporales
    for n in sobrantes:
        assert not n.startswith("tmp"), f"temporal en la salida: {n}"


def test_nunca_sobreescribe(entorno, monkeypatch):
    """Si el destino ya existe, se numera en vez de pisar."""
    ent, sal, reb = entorno
    (reb / "A4.wav").write_bytes(b"YA ESTABA")
    _wav_con_nota(ent / "uno.wav", 440.0, con_loop=False)
    monkeypatch.setattr(e1, "decidir_nota",
                        lambda r: {"midi": 69, "cents": 0.0, "duda": False,
                                   "motivo": "", "candidatas": []})
    e1.procesar_carpeta(str(ent), str(sal), log=lambda s: None, preguntar_dudas=False)
    assert (reb / "A4.wav").read_bytes() == b"YA ESTABA", "piso un archivo existente"
    assert (reb / "A4_2.wav").exists()


# --- los tres anchos de muestra: 16, 24 y 32 bits -------------------------
def _wav_ancho(ruta, hz, ancho, sr=44100, dur=0.3, con_loop=True):
    n = int(sr * dur)
    t = np.arange(n) / sr
    x = np.sin(2 * np.pi * hz * t) * 0.5
    if ancho == 2:
        datos = (x * 32767).astype("<i2").tobytes()
    elif ancho == 3:
        v = (x * 8388607).astype(np.int32)
        b = np.empty((len(v), 3), dtype=np.uint8)
        b[:, 0] = v & 0xFF
        b[:, 1] = (v >> 8) & 0xFF
        b[:, 2] = (v >> 16) & 0xFF
        datos = b.tobytes()
    elif ancho == 4:
        datos = (x * 2147483647).astype("<i4").tobytes()
    fmt = struct.pack("<HHIIHH", 1, 1, sr, sr * ancho, ancho, ancho * 8)
    cuerpo = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if con_loop:
        s = struct.pack("<9I", 0, 0, 20833, 69, 0, 0, 0, 1, 0) + \
            struct.pack("<6I", 0, 0, 1000, 2000, 0, 0)
        cuerpo += b"smpl" + struct.pack("<I", len(s)) + s
    cuerpo += b"data" + struct.pack("<I", len(datos)) + datos
    open(ruta, "wb").write(b"RIFF" + struct.pack("<I", 4 + len(cuerpo)) + b"WAVE" + cuerpo)


@pytest.mark.parametrize("ancho", [2, 3, 4])
def test_los_tres_anchos_de_muestra(entorno, monkeypatch, ancho):
    """16, 24 y 32 bits tienen que procesarse igual. Los de 24 reventaban."""
    ent, sal, reb = entorno
    _wav_ancho(ent / f"a{ancho}.wav", 440.0, ancho, con_loop=False)
    monkeypatch.setattr(e1, "decidir_nota",
                        lambda r: {"midi": 69, "cents": 0.0, "duda": False,
                                   "motivo": "", "candidatas": []})
    inf = e1.procesar_carpeta(str(ent), str(sal), log=lambda s: None,
                              preguntar_dudas=False)
    assert inf[0].get("estado") != "ERROR", f"ancho {ancho*8} bits fallo: {inf[0].get('motivo')}"
    assert len(list(reb.glob('*.wav'))) + len(list(sal.glob('*.wav'))) == 1
