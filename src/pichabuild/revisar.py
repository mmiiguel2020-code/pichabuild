#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pichabuild.revisar — revisar un SF2 ANTES de armarlo.

Lo que se comprueba, y por que:

  1. ¿tiene instrumento?           sin instrumento no hay de donde sacar zonas
  2. ¿cuantas zonas y cuantas muestras?
  3. ¿cada zona tiene su keyRange? si no, todas caen en la misma tecla y el
     mapeo COLAPSA: todo suena con un solo sample (el clasico "zonas=1")
  4. ¿alguna zona cubre 0-127?     esa zona se come a todas las demas: suena
     el mismo sample en todo el teclado
  5. ¿cada zona tiene rootKey?     si no, hay que sacar la nota midiendo
"""
import struct


def _look(d, cid):
    i = d.find(cid)
    return (i, struct.unpack("<I", d[i + 4:i + 8])[0]) if i >= 0 else (None, 0)


def revisar(ruta):
    """Devuelve (ok, lista_de_avisos, datos)."""
    d = open(ruta, "rb").read()
    avisos, datos = [], {}

    _, s_shdr = _look(d, b"shdr")
    _, s_phdr = _look(d, b"phdr")
    _, s_inst = _look(d, b"inst")
    i_ibag, s_ibag = _look(d, b"ibag")
    i_igen, s_igen = _look(d, b"igen")

    n_muestras = max(0, s_shdr // 46 - 1)
    n_presets = max(0, s_phdr // 38 - 1)
    n_instr = max(0, s_inst // 22 - 1)
    n_zonas = max(0, s_ibag // 4 - 1)
    datos.update(muestras=n_muestras, presets=n_presets,
                 instrumentos=n_instr, zonas=n_zonas)

    # --- 1. instrumento ---
    if n_instr == 0:
        avisos.append(("ERROR", "no tiene instrumento: no hay de donde sacar las zonas"))
        return False, avisos, datos
    if n_muestras == 0:
        avisos.append(("ERROR", "no tiene muestras"))
        return False, avisos, datos
    if n_zonas == 0:
        avisos.append(("ERROR", "el instrumento no tiene zonas"))
        return False, avisos, datos

    # --- leer las zonas ---
    ib = [struct.unpack("<HH", d[i_ibag + 8 + k * 4:i_ibag + 12 + k * 4])
          for k in range(s_ibag // 4)]
    con_key, sin_key, con_root = 0, 0, 0
    ancha = []          # zonas que cubren demasiado
    for z in range(len(ib) - 1):
        g0, g1 = ib[z][0], ib[z + 1][0]
        pr = {}
        for g in range(g0, min(g1, s_igen // 4)):
            op, am = struct.unpack("<HH", d[i_igen + 8 + g * 4:i_igen + 12 + g * 4])
            pr[op] = am
        if 43 in pr:
            con_key += 1
            kr = pr[43]
            lo, hi = kr & 0xFF, kr >> 8
            if lo > hi:
                lo, hi = hi, lo
            if hi - lo > 36:            # mas de tres octavas
                ancha.append((z, lo, hi))
        else:
            sin_key += 1
        if 58 in pr:
            con_root += 1

    datos.update(con_keyrange=con_key, sin_keyrange=sin_key,
                 con_rootkey=con_root, zonas_anchas=len(ancha))

    # --- 3. keyRange ---
    if sin_key and sin_key >= n_zonas * 0.5:
        avisos.append(("ERROR",
            f"{sin_key} de {n_zonas} zonas NO tienen keyRange. Sin keyRange "
            f"todas caen en 0-127 y el mapeo colapsa: todo sonaria con un solo "
            f"sample (salida 'zonas=1'). Hay que asignar la tecla de cada zona "
            f"en Polyphone."))
    elif sin_key:
        avisos.append(("AVISO",
            f"{sin_key} de {n_zonas} zonas sin keyRange: esas caen en 0-127"))

    # --- 4. zona que se come el teclado ---
    if ancha:
        z0, lo, hi = ancha[0]
        avisos.append(("AVISO",
            f"{len(ancha)} zona(s) cubren mas de tres octavas "
            f"(la {z0}: {lo}-{hi}). Una zona asi se come a las demas: "
            f"sonaria el mismo sample en todo el teclado"))

    # --- 5. rootKey ---
    if con_root == 0:
        avisos.append(("AVISO",
            "ninguna zona tiene rootKey: la nota habra que sacarla midiendo "
            "(usar_root_medido)"))
    elif con_root < n_zonas:
        avisos.append(("AVISO",
            f"solo {con_root} de {n_zonas} zonas tienen rootKey"))

    ok = not any(n == "ERROR" for n, _ in avisos)
    return ok, avisos, datos
