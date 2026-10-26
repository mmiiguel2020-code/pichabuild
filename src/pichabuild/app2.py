#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pichabuild.app2 — la ventana con DOS SECCIONES.

  SECCION 1  AFINACION Y NOMBRADO   (in -> out)   carpeta de WAV
  SECCION 2  ARMADO                 (in -> out)   SF2 con instrumento

Directrices que respeta:
  1  el bucle no se toca
  5  el musette no se corrige
  9  la tabla de registros es la de Miguel
  10 los cents son independientes por registro
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import wave

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox,
                               QFileDialog, QGroupBox, QHBoxLayout, QLabel,
                               QMainWindow, QPushButton, QSlider, QSpinBox,
                               QTabWidget, QVBoxLayout, QWidget, QLineEdit)

ENTRADA_WAV = os.path.expanduser("~/Escritorio/entr build")
SALIDA_WAV = os.path.expanduser("~/Escritorio/APROBADAS")
REBUCLEO = os.path.expanduser("~/Escritorio/REBUCLEO")
SALIDA_SF2 = os.path.expanduser("~/Escritorio/salida_5reg")
MOTOR = os.path.expanduser("~/herramientas/construir_sf2_acordeon.py")
PY = os.path.expanduser("~/pichedison/.venv/bin/python")

# ---------------------------------------------------------------------------
# La tabla de registros (Directriz 9 y 10). Cada valor es INDEPENDIENTE.
# ---------------------------------------------------------------------------
REGISTROS = [
    # nombre,      programa, voces
    ("Clarinete", 0, [("M",   None)]),                       # M fijo 0
    ("Fagot",     1, [("L",   None)]),                       # L fijo 0
    ("Bandoneon", 2, [("L",   None), ("M+", "band")]),       # M+ propio
    ("Violin",    3, [("M",   None), ("M+", "violin")]),     # M+ propio
    ("Master",    4, [("L",   "master"), ("M", None), ("M+", "master")]),
]


class Puente(QObject):
    linea = Signal(str)
    fin = Signal(bool, str)


class Ventana(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("pichabuild")
        self.resize(900, 700)
        self.puente = Puente()
        self.puente.linea.connect(lambda s: self.log.append(s))
        self.puente.fin.connect(self._fin)
        self.cents = {}          # (clave) -> QSlider
        self._build()

    # ------------------------------------------------------------------ ui --
    def _build(self):
        tabs = QTabWidget()
        tabs.addTab(self._tab_afinar(), "1 · Afinación y nombrado")
        tabs.addTab(self._tab_armar(), "2 · Armado (5 registros)")
        self.setCentralWidget(tabs)

    # ---- seccion 1 -------------------------------------------------------
    def _tab_afinar(self):
        w = QWidget()
        v = QVBoxLayout(w)

        g = QGroupBox("Entrada y salida")
        f = QVBoxLayout(g)
        self.e_ent_wav = self._fila("Carpeta de WAV", ENTRADA_WAV, f)
        self.e_sal_wav = self._fila("Carpeta de salida", SALIDA_WAV, f)
        v.addWidget(g)

        g2 = QGroupBox("Ajustes")
        f2 = QHBoxLayout(g2)
        f2.addWidget(QLabel("A4 (Hz)"))
        self.sp_a4 = QSpinBox(); self.sp_a4.setRange(415, 466); self.sp_a4.setValue(440)
        f2.addWidget(self.sp_a4)
        f2.addWidget(QLabel("Umbral (cents)"))
        self.sp_umbral = QSpinBox(); self.sp_umbral.setRange(0, 20)
        self.sp_umbral.setValue(1); self.sp_umbral.setSuffix("  (0,5 = medio)")
        f2.addWidget(self.sp_umbral)
        f2.addStretch(1)
        v.addWidget(g2)

        hb = QHBoxLayout()
        self.btn_afinar = QPushButton("▶  Afinar y nombrar")
        self.btn_afinar.clicked.connect(self.arrancar_afinar)
        hb.addWidget(self.btn_afinar)
        hb.addStretch(1)
        v.addLayout(hb)

        v.addWidget(QLabel(
            "Lo que se afina cambia de largo → va a REBUCLEO.\n"
            "Lo que ya estaba afinado y trae loop → va a la carpeta de salida."))
        v.addWidget(QLabel(" "))
        self.log = QLabel(""); self.log.setWordWrap(True)
        self._log_afinar = self.log
        v.addWidget(self.log, 1)
        return w

    # ---- seccion 2 -------------------------------------------------------
    def _tab_armar(self):
        w = QWidget()
        v = QVBoxLayout(w)

        g = QGroupBox("Entrada y salida")
        f = QVBoxLayout(g)
        self.e_ent_sf2 = self._fila("SF2 con instrumento", "", f)
        self.e_sal_sf2 = self._fila("Carpeta de salida", SALIDA_SF2, f)
        v.addWidget(g)

        # --- cents por registro (independientes) ---
        g2 = QGroupBox("Cents por registro  (cada uno independiente)")
        f2 = QVBoxLayout(g2)
        for nombre, prog, voces in REGISTROS:
            for voz, clave in voces:
                if clave is None:
                    texto = f"{nombre:10s}  {voz:2s}   fijo 0"
                    f2.addWidget(QLabel(texto))
                    continue
                h = QHBoxLayout()
                h.addWidget(QLabel(f"{nombre:10s}  {voz:2s}"))
                s = QSlider(Qt.Horizontal)
                if clave == "master" and voz == "L":
                    s.setRange(-20, 0); s.setValue(-5)
                else:
                    s.setRange(0, 20); s.setValue(15)
                lbl = QLabel(f"{s.value():+d}")
                s.valueChanged.connect(lambda x, l=lbl: l.setText(f"{x:+d}"))
                h.addWidget(s, 1)
                h.addWidget(lbl)
                f2.addLayout(h)
                self.cents[(nombre, voz)] = s
        v.addWidget(g2)

        # --- envolvente ---
        g3 = QGroupBox("Envolvente")
        f3 = QHBoxLayout(g3)
        f3.addWidget(QLabel("Ataque (ms)"))
        self.sp_atk = QSpinBox(); self.sp_atk.setRange(0, 500); self.sp_atk.setValue(25)
        f3.addWidget(self.sp_atk)
        f3.addWidget(QLabel("Cola (ms)"))
        self.sp_rel = QSpinBox(); self.sp_rel.setRange(0, 2000); self.sp_rel.setValue(80)
        f3.addWidget(self.sp_rel)
        f3.addStretch(1)
        v.addWidget(g3)

        hb = QHBoxLayout()
        self.btn_armar = QPushButton("▶  Armar SF2 de 5 registros")
        self.btn_armar.clicked.connect(self.arrancar_armar)
        hb.addWidget(self.btn_armar)
        hb.addStretch(1)
        v.addLayout(hb)

        self.log2 = QLabel(""); self.log2.setWordWrap(True)
        v.addWidget(self.log2, 1)
        return w

    def _fila(self, etiqueta, valor, layout):
        h = QHBoxLayout()
        h.addWidget(QLabel(etiqueta))
        e = QLineEdit(valor)
        h.addWidget(e, 1)
        b = QPushButton("…")
        b.setFixedWidth(32)
        b.clicked.connect(lambda: self._elegir(e))
        h.addWidget(b)
        layout.addLayout(h)
        return e

    def _elegir(self, edit):
        d = QFileDialog.getExistingDirectory(self, "Carpeta", edit.text() or os.path.expanduser("~"))
        if d:
            edit.setText(d)

    # ------------------------------------------------------------- acciones --
    def arrancar_afinar(self):
        ent, sal = self.e_ent_wav.text(), self.e_sal_wav.text()
        umbral = self.sp_umbral.value() / 10.0
        a4 = self.sp_a4.value()
        self._bloquear(True)
        self._log_afinar.setText("trabajando…")

        def trabajo():
            try:
                from .etapa1 import procesar_carpeta
                inf = procesar_carpeta(ent, sal, log=lambda s: None)
                ok = sum(1 for f in inf if f.get("destino") == "salida")
                rb = sum(1 for f in inf if f.get("destino") == "REBUCLEO")
                self.puente.fin.emit(True, f"aprobadas {ok} · a rebucleo {rb} · {len(inf)} en total")
                with open(os.path.join(sal, "informe.json"), "w") as fh:
                    json.dump(inf, fh, indent=1, ensure_ascii=False)
            except Exception as e:
                self.puente.fin.emit(False, str(e))
        threading.Thread(target=trabajo, daemon=True).start()

    def arrancar_armar(self):
        ent = self.e_ent_sf2.text()
        sal = self.e_sal_sf2.text()
        if not os.path.isfile(ent):
            self.log2.setText("no existe el SF2 de entrada")
            return
        self._bloquear(True)
        self.log2.setText("armando…")

        cents = {k: s.value() for k, s in self.cents.items()}
        atk, rel = self.sp_atk.value(), self.sp_rel.value()

        def trabajo():
            try:
                os.makedirs(sal, exist_ok=True)
                cfg = self._config(cents, atk, rel)
                ruta_cfg = os.path.join(sal, "registros.json")
                json.dump(cfg, open(ruta_cfg, "w"), indent=2, ensure_ascii=False)
                cmd = [PY, MOTOR, "construir", "--sf2", ent, "--config", ruta_cfg,
                       "--salida", os.path.join(sal, "5registros.sf2"),
                       "--wavs", os.path.join(sal, "wavs")]
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode != 0:
                    self.puente.fin.emit(False, (r.stderr or r.stdout)[-400:])
                    return
                lista = sorted(os.path.basename(p) for p in
                               __import__("glob").glob(os.path.join(sal, "wavs", "*.wav")))
                self.puente.fin.emit(True,
                    f"listo: {os.path.join(sal, '5registros.sf2')}\n"
                    f"{len(lista)} muestras procesadas")
            except Exception as e:
                self.puente.fin.emit(False, str(e))
        threading.Thread(target=trabajo, daemon=True).start()

    def _config(self, cents, atk, rel):
        """Config para el motor: M+ y L multiplicadas para que sean independientes."""
        cfg = {
            "nombre_banco": "5 registros", "afinacion_a4_hz": 440.0,
            "rango_notas": None, "notas_activas": None,
            "objetivo_rms_dbfs": -20.0,
            "ataque_ms": float(atk), "liberacion_ms": float(rel),
            "compensar_mezcla": True, "prefijo_muestra": "M", "banco": 0,
            "procesado": {"afinar": True, "usar_root_medido": True,
                          "aplanar_tono": True, "aplanar_nivel": True,
                          "umbral_tono_cents": 1.5, "umbral_nivel_db": 0.4,
                          "max_correccion_nivel_db": 4.0, "loop_duracion_s": 0.5},
            "voces": {}, "registros": [],
        }
        def voz(nombre, semis, cents_v):
            return {"transposicion": semis, "afinacion_cents": float(cents_v),
                    "ganancia_db": 0.0, "pan": 0.0, "notas": None,
                    "filtro_hz": None, "ataque_ms": None, "liberacion_ms": None}
        cfg["voces"]["M"] = voz("M", 0, 0)
        cfg["voces"]["M2_band"] = voz("M2_band", 0, cents.get(("Bandoneon", "M+"), 15))
        cfg["voces"]["M2_violin"] = voz("M2_violin", 0, cents.get(("Violin", "M+"), 15))
        cfg["voces"]["M2_master"] = voz("M2_master", 0, cents.get(("Master", "M+"), 15))
        cfg["voces"]["L"] = voz("L", -12, 0)
        cfg["voces"]["L_master"] = voz("L_master", -12, cents.get(("Master", "L"), -5))
        cfg["registros"] = [
            {"nombre": "Clarinete", "programa": 0, "voces": ["M"]},
            {"nombre": "Fagot",     "programa": 1, "voces": ["L"]},
            {"nombre": "Bandoneon", "programa": 2, "voces": ["L", "M2_band"]},
            {"nombre": "Violin",    "programa": 3, "voces": ["M", "M2_violin"]},
            {"nombre": "Master",    "programa": 4, "voces": ["L_master", "M", "M2_master"]},
        ]
        return cfg

    def _bloquear(self, b):
        for x in (self.btn_afinar, self.btn_armar):
            x.setEnabled(not b)

    def _fin(self, ok, msg):
        self._bloquear(False)
        self._log_afinar.setText(("" if ok else "ERROR: ") + msg)
        self.log2.setText(("" if ok else "ERROR: ") + msg)


def main():
    app = QApplication(sys.argv)
    w = Ventana()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
