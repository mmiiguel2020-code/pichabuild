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

from PySide6.QtCore import Qt, Signal, QObject, QProcess

from .base_sf2 import armar_desde_wavs, leer_loop, nota_de_nombre
from . import oir as oirmod
from .revisar import revisar, revisar_carpeta
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


# Teclado QWERTY -> semitonos sobre la nota base (como FL Studio / Ableton)
TECLAS = {
    Qt.Key_A: 0,  Qt.Key_W: 1,  Qt.Key_S: 2,  Qt.Key_E: 3,
    Qt.Key_D: 4,  Qt.Key_F: 5,  Qt.Key_T: 6,  Qt.Key_G: 7,
    Qt.Key_Y: 8,  Qt.Key_H: 9,  Qt.Key_U: 10, Qt.Key_J: 11,
    Qt.Key_K: 12,
}
# fila de abajo, una octava menos
TECLAS_BAJAS = {
    Qt.Key_Z: 0,  Qt.Key_2: 1,  Qt.Key_X: 2,  Qt.Key_3: 3,
    Qt.Key_C: 4,  Qt.Key_V: 5,  Qt.Key_B: 6,  Qt.Key_N: 7,
    Qt.Key_M: 8,  Qt.Key_Comma: 9, Qt.Key_Period: 10, Qt.Key_Slash: 11,
}
TODAS = {**TECLAS, **TECLAS_BAJAS}


class Puente(QObject):
    linea = Signal(str)
    fin = Signal(bool, str)


def QSpinBoxWithRange(lo, hi, val):
    from PySide6.QtWidgets import QSpinBox
    sp = QSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(val)
    return sp


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
        tabs.addTab(self._tab_oir(), "3 · Escuchar")
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
        self.e_ent_sf2 = self._fila("Carpeta de WAV aprobados",
                                    os.path.expanduser("~/Escritorio/APROBADAS"), f)
        self.e_sal_sf2 = self._fila("Carpeta de salida", SALIDA_SF2, f)
        h = QHBoxLayout()
        self.btn_revisar = QPushButton("Revisar las muestras antes de armar")
        self.btn_revisar.clicked.connect(self.revisar_entrada)
        h.addWidget(self.btn_revisar)
        h.addStretch(1)
        f.addLayout(h)
        v.addWidget(g)

        self.lbl_diag = QLabel("")
        self.lbl_diag.setWordWrap(True)
        self.lbl_diag.setTextFormat(Qt.RichText)
        v.addWidget(self.lbl_diag)

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

    # ---- seccion 3: escuchar -------------------------------------------
    def _tab_oir(self):
        w = QWidget()
        v = QVBoxLayout(w)

        g = QGroupBox("Banco de sonidos")
        f = QVBoxLayout(g)
        self.e_sf2_oir = self._fila("SF2", os.path.expanduser("~/Escritorio/chido sf2.sf2"), f)
        hb = QHBoxLayout()
        self.btn_cargar = QPushButton("Cargar presets")
        self.btn_cargar.clicked.connect(self.cargar_presets)
        hb.addWidget(self.btn_cargar)
        hb.addWidget(QLabel("preset:"))
        self.combo_preset = QComboBox()
        self.combo_preset.setMinimumWidth(240)
        self.combo_preset.currentIndexChanged.connect(
            lambda _: self._mandar_programa() if getattr(self, "proc", None) else None)
        hb.addWidget(self.combo_preset, 1)
        f.addLayout(hb)
        v.addWidget(g)

        g2 = QGroupBox("Tocar")
        f2 = QVBoxLayout(g2)
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("nota"))
        self.e_nota = QLineEdit("A4")
        self.e_nota.setMaximumWidth(90)
        h2.addWidget(self.e_nota)
        self.btn_nota = QPushButton("♪  Tocar esa nota")
        self.btn_nota.clicked.connect(lambda: self.tocar("nota"))
        h2.addWidget(self.btn_nota)
        self.btn_escala = QPushButton("♪♪  Escala (Do4–Do5)")
        self.btn_escala.clicked.connect(lambda: self.tocar("escala"))
        h2.addWidget(self.btn_escala)
        h2.addStretch(1)
        f2.addLayout(h2)

        h3 = QHBoxLayout()
        h3.addWidget(QLabel("octava rápida:"))
        for m in ("C3", "C4", "C5", "C6"):
            b = QPushButton(m)
            b.setFixedWidth(52)
            b.clicked.connect(lambda _=False, x=m: self.tocar_nota_directa(x))
            h3.addWidget(b)
        h3.addStretch(1)
        f2.addLayout(h3)
        v.addWidget(g2)

        g3 = QGroupBox("Teclado QWERTY")
        f3 = QVBoxLayout(g3)
        h3 = QHBoxLayout()
        self.btn_teclado = QPushButton("▶  Activar teclado")
        self.btn_teclado.setCheckable(True)
        self.btn_teclado.clicked.connect(self.alternar_teclado)
        h3.addWidget(self.btn_teclado)
        h3.addWidget(QLabel("octava base:"))
        self.sp_octava = QSpinBoxWithRange(1, 7, 4)
        h3.addWidget(self.sp_octava)
        h3.addStretch(1)
        f3.addLayout(h3)
        f3.addWidget(QLabel(
            "A W S E D F T G Y H U J K  =  Do Re Mi Fa Sol La Si (fila del medio)\n"
            "Z X C V B N M , . /        =  una octava menos\n"
            "Cambia la octava con el control de arriba."))
        v.addWidget(g3)

        self.lbl_oir = QLabel("")
        self.lbl_oir.setWordWrap(True)
        v.addWidget(self.lbl_oir, 1)
        self.setFocusPolicy(Qt.StrongFocus)
        return w

    # ---- teclado QWERTY en vivo ---------------------------------------
    def alternar_teclado(self, activo):
        if activo:
            ruta = self.e_sf2_oir.text()
            if not os.path.isfile(ruta):
                self.lbl_oir.setText("no existe ese SF2")
                self.btn_teclado.setChecked(False)
                return
            if self.combo_preset.count() == 0:
                self.cargar_presets()
            self._arrancar_synth(ruta)
            if self.proc is None or self.proc.state() != QProcess.Running:
                self.lbl_oir.setText("no pude arrancar FluidSynth")
                self.btn_teclado.setChecked(False)
                return
            self._mandar_programa()
            self.btn_teclado.setText("■  Teclado activo  (pulsa para parar)")
            self.setFocus()
            self.lbl_oir.setText("teclado activo: pulsa A S D F…")
        else:
            self._parar_synth()
            self.btn_teclado.setText("▶  Activar teclado")
            self.lbl_oir.setText("teclado parado")

    def _arrancar_synth(self, ruta):
        self._parar_synth()
        pr = QProcess(self)
        pr.setProgram("fluidsynth")
        pr.setArguments(["-a", "pipewire", "-m", "alsa_seq",
                         "-g", "1.5", ruta])
        pr.start()
        if not pr.waitForStarted(4000):
            self.proc = None
            return
        self.proc = pr

    def _parar_synth(self):
        pr = getattr(self, "proc", None)
        if pr is None:
            return
        try:
            pr.write(b"quit\n")
            pr.waitForFinished(800)
        except Exception:
            pass
        try:
            pr.kill()
        except Exception:
            pass
        self.proc = None

    def _mandar(self, texto):
        pr = getattr(self, "proc", None)
        if pr is not None and pr.state() == QProcess.Running:
            pr.write((texto + "\n").encode())

    def _mandar_programa(self):
        prog = self.combo_preset.currentData() or 0
        self._mandar(f"prog 0 {int(prog)}")

    def keyPressEvent(self, ev):
        if (self.btn_teclado.isChecked() and not ev.isAutoRepeat()
                and ev.key() in TODAS):
            base = 12 * (self.sp_octava.value() + 1)
            semi = TODAS[ev.key()]
            if ev.key() in TECLAS_BAJAS:
                semi -= 12
            nota = base + semi
            if 0 <= nota <= 127:
                self._mandar(f"noteon 0 {nota} 100")
                ev.accept()
                return
        super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if (self.btn_teclado.isChecked() and not ev.isAutoRepeat()
                and ev.key() in TODAS):
            base = 12 * (self.sp_octava.value() + 1)
            semi = TODAS[ev.key()]
            if ev.key() in TECLAS_BAJAS:
                semi -= 12
            nota = base + semi
            if 0 <= nota <= 127:
                self._mandar(f"noteoff 0 {nota}")
                ev.accept()
                return
        super().keyReleaseEvent(ev)

    def cargar_presets(self):
        ruta = self.e_sf2_oir.text()
        if not os.path.isfile(ruta):
            self.lbl_oir.setText("no existe ese SF2")
            return
        try:
            lista = oirmod.presets(ruta)
        except Exception as e:
            self.lbl_oir.setText(f"no pude leer los presets: {e}")
            return
        self.combo_preset.clear()
        for nom, banco, prog in lista:
            self.combo_preset.addItem(f"{prog} · {nom}  (banco {banco})", prog)
        self.lbl_oir.setText(f"{len(lista)} presets cargados de "
                             f"{os.path.basename(ruta)}")

    def tocar(self, que):
        nota = self.e_nota.text().strip() or "A4"
        self.tocar_nota_directa("escala" if que == "escala" else nota)

    def tocar_nota_directa(self, nota):
        ruta = self.e_sf2_oir.text()
        if not os.path.isfile(ruta):
            self.lbl_oir.setText("no existe ese SF2")
            return
        prog = self.combo_preset.currentData()
        if prog is None:
            self.cargar_presets()
            prog = self.combo_preset.currentData() or 0
        self.lbl_oir.setText(f"sonando: {os.path.basename(ruta)} · "
                             f"programa {prog} · {nota}")
        QApplication.processEvents()
        ok, err = oirmod.tocar(ruta, int(prog), nota)
        self.lbl_oir.setText(
            f"{'♪' if ok else 'ERROR'} {os.path.basename(ruta)} · "
            f"programa {prog} · {nota}" + ("" if ok else f"\n{err}"))

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
        if not os.path.isdir(ent):
            self.log2.setText("no existe la carpeta de muestras")
            return
        ok, avisos, datos = revisar_carpeta(ent)
        self.revisar_entrada()
        if not ok:
            self.log2.setText("no se puede armar: mira los ERRORES de arriba")
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
                # 1. de la carpeta de WAV a un SF2 con instrumento
                base_sf2 = os.path.join(sal, "base.sf2")
                okb, info = armar_desde_wavs(ent, base_sf2, log=lambda s: None)
                if not okb:
                    self.puente.fin.emit(False, f"no pude armar el SF2 base: {info}")
                    return
                # 2. el SF2 base -> los 5 registros
                cmd = [PY, MOTOR, "construir", "--sf2", base_sf2, "--config", ruta_cfg,
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

    def revisar_entrada(self):
        """Dice que le falta a la carpeta de muestras ANTES de armar."""
        ent = self.e_ent_sf2.text()
        if not os.path.isdir(ent):
            self.lbl_diag.setText("<b>no existe la carpeta</b>")
            return False
        ok, avisos, datos = revisar_carpeta(ent)
        lineas = [
            f"<b>{os.path.basename(ent.rstrip(os.sep))}</b> — "
            f"{datos['wavs']} WAV · {datos['con_nota']} con nota en el nombre · "
            f"{datos['con_loop']} con loop · teclas "
            f"{datos.get('rango', '—')}"
        ]
        for tipo, txt in avisos:
            color = "#b00000" if tipo == "ERROR" else "#a05000"
            lineas.append(f'<span style="color:{color}"><b>{tipo}:</b> {txt}</span>')
        if not avisos:
            lineas.append('<span style="color:#006000"><b>OK:</b> '
                          'listo para armar</span>')
        self.lbl_diag.setText("<br>".join(lineas))
        return ok

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

    def closeEvent(self, ev):
        self._parar_synth()
        super().closeEvent(ev)

    def _fin(self, ok, msg):
        self._bloquear(False)
        self._log_afinar.setText(("" if ok else "ERROR: ") + msg)
        self.log2.setText(("" if ok else "ERROR: ") + msg)


def main():
    app = QApplication(sys.argv)
    app.aboutToQuit.connect(lambda: None)
    w = Ventana()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
