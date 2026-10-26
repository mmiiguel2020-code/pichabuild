#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pichabuild.oir — tocar un SF2 por los altavoces con FluidSynth.

Se usa desde la ventana (pestana "Escuchar") y desde el terminal.
"""
import os
import struct
import subprocess
import tempfile

NOM = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
       "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
NOMBRES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def a_midi(s):
    """'C4' -> 60 · '60' -> 60 · 'A#3' -> 58."""
    s = str(s).strip()
    if s.lstrip("-").isdigit():
        return int(s)
    n, octava = s[:-1], int(s[-2:]) if s[-2] == "-" else int(s[-1])
    if s[-2] == "-":
        n = s[:-2]
    return NOM[n] + 12 * (octava + 1)


def _n20(b):
    b = b[:20]
    return b + b"\0" * (20 - len(b))


def presets(ruta):
    """Lista de (nombre, banco, programa) del SF2."""
    with open(ruta, "rb") as f:
        d = f.read()
    pos = 12
    phdr = None
    while pos + 8 <= len(d):
        cid = d[pos:pos + 4]
        sz = struct.unpack("<I", d[pos + 4:pos + 8])[0]
        if cid == b"LIST" and d[pos + 8:pos + 12] == b"pdta":
            p = pos + 12
            while p + 8 <= pos + 8 + sz:
                sc = d[p:p + 4]
                ssz = struct.unpack("<I", d[p + 4:p + 8])[0]
                if sc == b"phdr":
                    phdr = d[p + 8:p + 8 + ssz]
                p += 8 + ssz + (ssz & 1)
        pos += 8 + sz + (sz & 1)
    if not phdr:
        return []
    out = []
    for k in range(len(phdr) // 38 - 1):
        o = k * 38
        nom = phdr[o:o + 20].split(b"\0")[0].decode("latin1", "replace").strip()
        prog, banco = struct.unpack("<HH", phdr[o + 20:o + 24])
        out.append((nom, banco, prog))
    return out


def _vlq(n):
    o = [n & 0x7F]
    n >>= 7
    while n:
        o.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(o))


def crear_midi(programa, nota="escala", dur_ms=400):
    """MIDI en memoria. nota='escala' toca Do4-Do5."""
    t = _vlq(0) + bytes([0xC0, programa & 0x7F])
    if str(nota) == "escala":
        for m in (60, 62, 64, 65, 67, 69, 71, 72):
            t += _vlq(0) + bytes([0x90, m, 100]) + _vlq(dur_ms) + \
                 bytes([0x80, m, 0]) + _vlq(40)
    else:
        m = a_midi(nota)
        t += _vlq(0) + bytes([0x90, m, 100]) + _vlq(max(200, dur_ms * 3)) + \
             bytes([0x80, m, 0]) + _vlq(40)
    # UN solo delta antes del fin de pista. Dos deltas seguidos y FluidSynth
    # responde "Unexpected end of file" y no renderiza nada.
    t += bytes([0xFF, 0x2F, 0x00])
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480) + \
           b"MTrk" + struct.pack(">I", len(t)) + t


def tocar(ruta_sf2, programa=0, nota="escala", ganancia=1.5):
    """Toca y espera. Devuelve (ok, salida)."""
    fd, mid = tempfile.mkstemp(suffix=".mid")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(crear_midi(programa, nota))
        cmd = ["fluidsynth", "-a", "pipewire", "-m", "alsa_seq", "-i",
               "-g", str(ganancia), ruta_sf2, mid]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                           stdin=subprocess.DEVNULL)
        err = "\n".join(l for l in r.stderr.splitlines()
                        if "error" in l.lower() and "preset" not in l.lower())
        return (r.returncode == 0 and not err), err
    finally:
        try:
            os.unlink(mid)
        except OSError:
            pass


def renderizar(ruta_sf2, salida_wav, programa=0, nota="escala", ganancia=1.5):
    """Renderiza a un WAV en vez de a los altavoces (para comprobar sin oido)."""
    fd, mid = tempfile.mkstemp(suffix=".mid")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(crear_midi(programa, nota))
        cmd = ["fluidsynth", "-a", "file", "-F", salida_wav, "-m", "alsa_seq",
               "-i", "-g", str(ganancia), ruta_sf2, mid]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                           stdin=subprocess.DEVNULL)
        return os.path.exists(salida_wav), r.stderr
    finally:
        try:
            os.unlink(mid)
        except OSError:
            pass
