#!/usr/bin/env python3
"""
afinar_samples.py

Lleva cada sample (una nota por archivo) a la afinacion exacta de la nota mas
cercana (temperamento igual, A4 = 440 Hz por defecto). Cambia el tono de verdad
en el audio, remuestreando (igual que subir o bajar la velocidad de un sampler),
asi que la duracion cambia un poco (menos de 3 % para correcciones de hasta 50 cents).

Uso:
  python afinar_samples.py carpeta_entrada carpeta_salida
  python afinar_samples.py sample.wav carpeta_salida
  python afinar_samples.py carpeta_entrada carpeta_salida --solo-reportar

Dependencias:
  pip install numpy scipy soundfile librosa
"""
import argparse
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

EXTS = {".wav", ".flac", ".aif", ".aiff"}
HOP = 256
FRAME = 4096
REJECT_CENTS = 300  # descarta errores de octava del detector de tono
NOTAS = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]


def nombre_nota(midi):
    return f"{NOTAS[midi % 12]}{midi // 12 - 1}"


def _mediana_pyin(mono, sr, fmin, fmax, resolution):
    f0, _, _ = librosa.pyin(
        mono,
        fmin=fmin,
        fmax=fmax,
        sr=sr,
        frame_length=FRAME,
        hop_length=HOP,
        resolution=resolution,
    )
    rms = librosa.feature.rms(y=mono, frame_length=FRAME, hop_length=HOP)[0]
    n = min(len(f0), len(rms))
    f0, rms = f0[:n].copy(), rms[:n]

    # solo cuadros con energia razonable (ignora colas y ruido)
    f0[rms < rms.max() * 10 ** (-25 / 20)] = np.nan
    if np.count_nonzero(~np.isnan(f0)) < 10:
        return None

    med = np.nanmedian(f0)
    with np.errstate(invalid="ignore"):
        cents = 1200 * np.log2(f0 / med)
        f0[np.abs(cents) > REJECT_CENTS] = np.nan
    ok = ~np.isnan(f0)
    if ok.sum() < 10:
        return None
    return float(np.median(f0[ok]))


def tono_del_sample(mono, sr):
    """Frecuencia mediana (Hz) de la parte sonora del sample, o None.
    Pasada 1: rango amplio, resolucion de 10 cents.
    Pasada 2: +-2 semitonos alrededor del resultado, resolucion de 1 cent."""
    grueso = _mediana_pyin(
        mono, sr, librosa.note_to_hz("C2"), librosa.note_to_hz("C7"), 0.1
    )
    if grueso is None:
        return None
    fino = _mediana_pyin(
        mono, sr, grueso * 2 ** (-2 / 12), grueso * 2 ** (2 / 12), 0.01
    )
    return fino if fino is not None else grueso


def procesar(ruta, salida, a):
    info = sf.info(str(ruta))
    x, sr = sf.read(str(ruta), always_2d=True)
    x = x.astype(np.float64)
    print(f"\n{ruta.name}  ({sr} Hz, {x.shape[1]} canal(es), {len(x) / sr:.2f} s)")

    f0 = tono_del_sample(x.mean(axis=1), sr)
    if f0 is None:
        print("  no se detecto un tono estable, se omite")
        return

    midi_exacto = 69 + 12 * np.log2(f0 / a.a4)
    midi = int(round(midi_exacto))
    cents = 100 * (midi_exacto - midi)
    objetivo = a.a4 * 2 ** ((midi - 69) / 12)
    print(f"  detectado: {f0:.2f} Hz = {nombre_nota(midi)} {cents:+.1f} cents  (objetivo {objetivo:.2f} Hz)")

    if a.solo_reportar:
        return

    if abs(cents) < 0.5:
        print("  ya esta afinado, se copia sin cambios")
        y = x
    else:
        r = objetivo / f0  # >1 sube el tono, <1 lo baja
        y = librosa.resample(
            x.T, orig_sr=sr, target_sr=sr / r, res_type="soxr_hq", axis=-1
        ).T
        print(f"  correccion: {-cents:+.1f} cents, duracion {len(y) / len(x):.3f}x")

    # evita recorte por el remuestreo
    pico = np.max(np.abs(y))
    if pico > 0.999:
        y = y * (0.999 / pico)

    subtype = info.subtype if sf.check_format("WAV", info.subtype) else "PCM_24"
    destino = salida / (ruta.stem + ".wav")
    sf.write(str(destino), y, sr, subtype=subtype)
    print(f"  -> {destino}")


def main():
    p = argparse.ArgumentParser(description="Afina samples a la nota exacta mas cercana.")
    p.add_argument("entrada", help="archivo o carpeta con samples")
    p.add_argument("salida", help="carpeta de salida")
    p.add_argument("--a4", type=float, default=440.0, help="frecuencia de La4 en Hz (por defecto 440)")
    p.add_argument("--solo-reportar", action="store_true", help="solo muestra nota y desviacion, no escribe archivos")
    a = p.parse_args()

    entrada = Path(a.entrada)
    salida = Path(a.salida)
    if not a.solo_reportar:
        salida.mkdir(parents=True, exist_ok=True)

    if entrada.is_file():
        archivos = [entrada]
    else:
        archivos = sorted(f for f in entrada.iterdir() if f.suffix.lower() in EXTS)
    if not archivos:
        sys.exit("No se encontraron archivos de audio.")

    for f in archivos:
        try:
            procesar(f, salida, a)
        except Exception as e:  # sigue con el siguiente archivo
            print(f"  ERROR en {f.name}: {e}")


if __name__ == "__main__":
    main()
