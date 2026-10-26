#!/usr/bin/env python3
"""pichabuild — ETAPA 1: rectificar afinacion y nombre.

Uso:
    pichabuild ENTRADA [SALIDA]

  ENTRADA  carpeta con WAV (los exportados de Polyphone traen el loop)
  SALIDA   donde van las aprobadas (por defecto ~/Escritorio/APROBADAS)

Lo que pasa por el afinador va SIEMPRE a ~/Escritorio/REBUCLEO/
porque el remuestreo le cambia el largo.
"""
import argparse
import json
import os
import sys

from .etapa1 import procesar_carpeta


def main():
    ap = argparse.ArgumentParser(description="pichabuild etapa 1: afinacion y nombre")
    ap.add_argument("entrada", help="carpeta con WAV")
    ap.add_argument("salida", nargs="?",
                    default=os.path.expanduser("~/Escritorio/APROBADAS"),
                    help="carpeta de las aprobadas")
    a = ap.parse_args()

    if not os.path.isdir(a.entrada):
        sys.exit(f"no existe la carpeta: {a.entrada}")

    print(f"pichabuild 0.1 · etapa 1 (afinacion y nombre)")
    print(f"  entrada : {a.entrada}")
    print(f"  salida  : {a.salida}")
    print(f"  rebucleo: {os.path.expanduser('~/Escritorio/REBUCLEO')}")
    print()
    informe = procesar_carpeta(a.entrada, a.salida)

    aprob = sum(1 for f in informe if f.get("destino") == a.salida)
    reb = sum(1 for f in informe if f.get("destino") == "REBUCLEO")
    err = sum(1 for f in informe if f.get("estado") == "ERROR")
    dud = sum(1 for f in informe if f.get("estado") == "DUDOSA")
    print()
    print(f"  aprobadas : {aprob}")
    print(f"  a rebucleo: {reb}")
    print(f"  dudosas   : {dud}")
    print(f"  errores   : {err}")

    dest = os.path.join(a.salida, "informe.json")
    os.makedirs(a.salida, exist_ok=True)
    json.dump(informe, open(dest, "w"), indent=1, ensure_ascii=False)
    print(f"  informe   : {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
