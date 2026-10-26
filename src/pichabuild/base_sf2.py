#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pichabuild.base_sf2 — de una CARPETA DE WAV a un SF2 con instrumento.

La seccion 2 recibe las muestras APROBADAS (WAV con su loop y su nota en el
nombre), no un SF2. Esto arma el SF2 base:

   C4.wav  ->  muestra "C4", zona keyRange 60-60, rootKey 60, modo loop

Directriz 1: el AUDIO y el LOOP se copian tal cual del WAV. No se remuestrea
ni se recalcula nada. Solo se anade la estructura.
"""
import os
import re
import struct

import numpy as np

from .core import leer_pcm

NOTAS = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
         "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

# generadores SF2
G_KEYRANGE, G_VELRANGE = 43, 44
G_INSTRUMENTO, G_SAMPLEID, G_SAMPLEMODES, G_ROOT = 41, 53, 54, 58


def nota_de_nombre(nombre):
    """'C4.wav' -> 60 · 'G#3_2.wav' -> 56 · 'A#6.wav' -> 94. None si no cuadra."""
    base = os.path.splitext(os.path.basename(nombre))[0]
    m = re.match(r"^([A-G][#b]?)(-?\d+)(?:_(\d+))?$", base)
    if not m:
        return None
    n, octava = m.group(1), int(m.group(2))
    semis = NOTAS[n[0]]
    if len(n) > 1:
        semis += 1 if n[1] == "#" else -1
    midi = semis + 12 * (octava + 1)
    return midi if 0 <= midi <= 127 else None


def leer_loop(ruta):
    """(inicio, fin) del loop en frames, o None. Solo LEE, no interpreta."""
    with open(ruta, "rb") as f:
        d = f.read()
    pos = 12
    while pos + 8 <= len(d):
        cid = d[pos:pos + 4]
        sz = struct.unpack("<I", d[pos + 4:pos + 8])[0]
        if cid == b"smpl":
            off = pos + 8
            if sz < 36:
                return None
            nloops = struct.unpack("<I", d[off + 28:off + 32])[0]
            if nloops < 1 or sz < 36 + 24:
                return None
            # primer struct sampleloop: cue, type, start, end, fraction, count
            start, end = struct.unpack("<II", d[off + 44:off + 52])
            return (int(start), int(end)) if end > start else None
        pos += 8 + sz + (sz & 1)
    return None


def _n20(s):
    b = s.encode("latin1", "replace")[:19]
    return b + b"\0" * (20 - len(b))


def _chunk(cid, data):
    return cid + struct.pack("<I", len(data)) + data + (b"\0" if len(data) & 1 else b"")


def _lista(tipo, *ch):
    c = b"".join(ch)
    return b"LIST" + struct.pack("<I", len(tipo) + len(c)) + tipo + c


def _gen(op, amt):
    return struct.pack("<HH", op, amt & 0xFFFF)


def _rango(op, lo, hi):
    return struct.pack("<HH", op, (lo & 0xFF) | ((hi & 0xFF) << 8))


def armar_desde_wavs(carpeta, salida, log=print):
    """Crea un SF2 con 1 instrumento y 1 zona por WAV. Devuelve (ok, informe)."""
    archivos = sorted(f for f in os.listdir(carpeta) if f.lower().endswith(".wav"))
    if not archivos:
        return False, {"error": "no hay WAV en la carpeta"}

    pcm_trozos, shdr, zonas, informe = [], [], [], []
    pos = 0
    for f in archivos:
        ruta = os.path.join(carpeta, f)
        midi = nota_de_nombre(f)
        if midi is None:
            informe.append({"archivo": f, "estado": "SIN NOTA EN EL NOMBRE"})
            log(f"  {f}: sin nota en el nombre, se salta")
            continue
        x, sr = leer_pcm(ruta)
        lp = leer_loop(ruta)
        if lp is None:
            informe.append({"archivo": f, "estado": "SIN LOOP"})
            log(f"  {f}: sin loop, se salta")
            continue
        li, lf = lp
        if lf > len(x):
            informes = informe.append({"archivo": f, "estado": f"LOOP FUERA ({lf}>{len(x)})"})
            log(f"  {f}: loop fuera del audio, se salta")
            continue

        datos = np.clip(x * 32767.0, -32768, 32767).astype("<i2")
        pcm_trozos.append(datos.tobytes())
        shdr.append(struct.pack("<20sIIIIIBbHH", _n20(os.path.splitext(f)[0]),
                                pos, pos + len(datos),
                                pos + li, pos + lf, int(sr), midi, 0, 0, 1))
        pos += len(datos) + 46
        pcm_trozos.append(b"\0" * (46 * 2))       # separacion entre muestras

        zi = len(zonas)
        zonas.append([_rango(G_KEYRANGE, midi, midi), _rango(G_VELRANGE, 0, 127),
                      _gen(G_ROOT, midi), _gen(G_SAMPLEMODES, 1), _gen(G_SAMPLEID, zi)])
        informe.append({"archivo": f, "nota": midi, "sr": int(sr),
                        "frames": len(x), "loop": (li, lf), "estado": "OK"})

    if not zonas:
        return False, {"error": "ningun WAV utilizable", "detalle": informe}

    shdr.append(struct.pack("<20sIIIIIBbHH", _n20("EOS"), 0, 0, 0, 0, 0, 0, 0, 0, 0))
    igen = [g for z in zonas for g in z] + [b"\0" * 4]
    # ibag lleva N entradas (una por zona) + 1 terminal.
    # El EOI apunta a N, NO a N+1: el lector recorre ibag[bi] e ibag[bi+1],
    # y para la ultima zona necesita ibag[N], que es el terminal.
    ibag = [struct.pack("<HH", i * 5, 0) for i in range(len(zonas))]
    inst = (struct.pack("<20sH", _n20("muestras"), 0) +
            struct.pack("<20sH", _n20("EOI"), len(ibag)))
    ibag.append(struct.pack("<HH", len(zonas) * 5, 0))
    phdr = (struct.pack("<20sHHHIII", _n20("muestras"), 0, 0, 0, 0, 0, 0) +
            struct.pack("<20sHHHIII", _n20("EOP"), 0, 0, 1, 0, 0, 0))
    pbag = struct.pack("<HH", 0, 0) + struct.pack("<HH", 1, 0)
    pgen = struct.pack("<HH", G_INSTRUMENTO, 0) + b"\0" * 4
    pmod = b"\0" * 20

    info = _lista(b"INFO", _chunk(b"ifil", struct.pack("<HH", 2, 1)),
                  _chunk(b"isng", b"EMU8000\0"), _chunk(b"INAM", b"pichabuild\0"),
                  _chunk(b"ISFT", b"pichabuild\0"))
    sdta = _lista(b"sdta", _chunk(b"smpl", b"".join(pcm_trozos)))
    pdta = _lista(b"pdta",
                  _chunk(b"phdr", phdr), _chunk(b"pbag", pbag), _chunk(b"pmod", pmod),
                  _chunk(b"pgen", pgen), _chunk(b"inst", inst),
                  _chunk(b"ibag", b"".join(ibag)), _chunk(b"imod", b"\0" * 10),
                  _chunk(b"igen", b"".join(igen)), _chunk(b"shdr", b"".join(shdr)))
    cuerpo = b"sfbk" + info + sdta + pdta
    with open(salida, "wb") as fh:
        fh.write(b"RIFF" + struct.pack("<I", len(cuerpo)) + cuerpo)
    return True, {"zonas": len(zonas), "detalle": informe}
