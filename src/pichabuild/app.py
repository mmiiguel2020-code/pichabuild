#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pichabuild.app — la ventana de la etapa 1.

Elegir carpeta · ver las muestras mientras se procesan · contestar las dudas
· ver donde acabo cada una. Usa el mismo motor que el comando (etapa1.py).

Directriz 8: si el afinador duda, aqui se pregunta, con las candidatas y un
boton para oir la muestra.
"""
import os
import sys
import threading

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog,
                               QHBoxLayout, QLabel, QMainWindow, QProgressBar,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget, QHeaderView)

from .core import nombre_nota
from .etapa1 import REBUCLEO, procesar_carpeta

APROBADAS = os.path.expanduser("~/Escritorio/APROBADAS")
# carpeta de entrada por defecto (se puede cambiar con el boton)
ENTRADA_DEFECTO = os.path.expanduser("~/Escritorio/entr build")



def _cents_respecto(ruta, midi, f0=None):
    """Cents de la muestra respecto de esa nota.

    Si conocemos el fundamental medido, es una resta exacta:
        1200 * log2(f0 / nota)
    Asi no depende de que el detector vuelva a medir.
    """
    import numpy as np
    if f0:
        obj = 440.0 * 2 ** ((midi - 69) / 12.0)
        return 1200.0 * np.log2(f0 / obj)
    try:
        from .nota import _cents_de
        return _cents_de(ruta, midi)
    except Exception:
        return None


def _mas_cercano(ruta, resultado):
    """Indice de la candidata con MENOS cents de diferencia (la mas probable)."""
    mejor, mejor_abs = 0, 1e9
    for i, (m, _) in enumerate((resultado.get("candidatas") or [])[:6]):
        c = _cents_respecto(ruta, m, resultado.get("fundamental_hz"))
        if c is not None and abs(c) < mejor_abs:
            mejor, mejor_abs = i, abs(c)
    return mejor


class Pregunta:
    """Una duda: la ventana la muestra y espera a que el usuario conteste."""

    def __init__(self, archivo, resultado, ruta):
        self.archivo = archivo
        self.resultado = resultado
        self.ruta = ruta
        self.respuesta = None       # MIDI elegido, o -1 saltar
        self.evento = threading.Event()


class Puente(QObject):
    """Senales del hilo de trabajo hacia la ventana."""
    fila = Signal(dict)
    duda = Signal(object)
    fin = Signal(dict)


class Ventana(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("pichabuild · etapa 1: afinación y nombre")
        self.resize(980, 640)
        self.entrada = ENTRADA_DEFECTO
        self.puente = Puente()
        self.puente.fila.connect(self.add_fila)
        self.puente.duda.connect(self.mostrar_duda)
        self.puente.fin.connect(self.terminado)
        self.duda_actual = None
        self._build()

    # ---------------------------------------------------------------- ui --
    def _build(self):
        w = QWidget()
        self.setCentralWidget(w)
        v = QVBoxLayout(w)

        t = QLabel("<b>pichabuild</b> — etapa 1: rectificar afinación y nombre")
        v.addWidget(t)

        h = QHBoxLayout()
        self.btn_ent = QPushButton("Elegir carpeta de WAV…")
        self.btn_ent.clicked.connect(self.elegir_entrada)
        self.lbl_ent = QLabel(ENTRADA_DEFECTO)
        h.addWidget(self.btn_ent)
        h.addWidget(self.lbl_ent, 1)
        v.addLayout(h)

        h2 = QHBoxLayout()
        self.btn_sal = QPushButton("Destino de aprobadas…")
        self.btn_sal.clicked.connect(self.elegir_salida)
        self.lbl_sal = QLabel(APROBADAS)
        h2.addWidget(self.btn_sal)
        h2.addWidget(self.lbl_sal, 1)
        v.addLayout(h2)

        hb = QHBoxLayout()
        self.btn_ir = QPushButton("▶ Procesar")
        self.btn_ir.setEnabled(False)
        self.btn_ir.clicked.connect(self.arrancar)
        hb.addWidget(self.btn_ir)
        self.barra = QProgressBar()
        self.barra.setFormat("%v / %m")
        hb.addWidget(self.barra, 1)
        v.addLayout(hb)

        # panel de duda
        self.panel = QWidget()
        pv = QVBoxLayout(self.panel)
        self.lbl_duda = QLabel("")
        self.lbl_duda.setWordWrap(True)
        pv.addWidget(self.lbl_duda)
        hd = QHBoxLayout()
        self.combo = QComboBox()
        self.btn_oir = QPushButton("♪ Oír")
        self.btn_oir.clicked.connect(self.oir_duda)
        self.btn_ok = QPushButton("Aceptar")
        self.btn_ok.clicked.connect(lambda: self.contestar(False))
        self.btn_salt = QPushButton("Saltar")
        self.btn_salt.clicked.connect(lambda: self.contestar(True))
        hd.addWidget(self.combo, 1)
        hd.addWidget(self.btn_oir)
        hd.addWidget(self.btn_ok)
        hd.addWidget(self.btn_salt)
        pv.addLayout(hd)
        self.panel.setVisible(False)
        v.addWidget(self.panel)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(
            ["archivo", "nota", "cents", "loop", "destino"])
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        v.addWidget(self.tabla, 1)

        self.lbl_fin = QLabel("")
        v.addWidget(self.lbl_fin)

        # arrancar con la carpeta de entrada por defecto, si tiene WAV
        self._usar_entrada(ENTRADA_DEFECTO)

    # ------------------------------------------------------------ acciones --
    def _usar_entrada(self, d):
        """Fija la carpeta de entrada y prepara la barra."""
        self.entrada = d
        self.lbl_ent.setText(d)
        if not os.path.isdir(d):
            self.barra.setMaximum(0)
            self.btn_ir.setEnabled(False)
            self.lbl_ent.setText(f"{d}   (no existe)")
            return
        n = len([f for f in os.listdir(d) if f.lower().endswith(".wav")])
        self.barra.setMaximum(n)
        self.barra.setValue(0)
        self.btn_ir.setEnabled(n > 0)
        if n == 0:
            self.lbl_ent.setText(f"{d}   (sin WAV)")

    def elegir_entrada(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta con WAV",
                                             ENTRADA_DEFECTO)
        if d:
            self._usar_entrada(d)

    def elegir_salida(self):
        d = QFileDialog.getExistingDirectory(self, "Destino de aprobadas")
        if d:
            self.lbl_sal.setText(d)

    def arrancar(self):
        self.tabla.setRowCount(0)
        self.lbl_fin.setText("")
        self.btn_ir.setEnabled(False)
        self.barra.setValue(0)
        salida = self.lbl_sal.text()
        threading.Thread(target=self._trabajo, args=(self.entrada, salida),
                         daemon=True).start()

    def _trabajo(self, entrada, salida):
        from .pregunta import _cargar_respuestas
        respuestas = _cargar_respuestas()
        archivos = sorted(f for f in os.listdir(entrada) if f.lower().endswith(".wav"))
        import pichabuild.etapa1 as e1
        from .nota import decidir_nota
        from .core import UMBRAL_CENTS, nombre_limpio, tiene_loop
        import shutil, tempfile, wave
        import numpy as np
        from .etapa1 import _resample, _escribir_wav

        resumen = {"aprobadas": 0, "rebucleo": 0, "saltadas": 0, "errores": 0}
        for f in archivos:
            ruta = os.path.join(entrada, f)
            fila = {"archivo": f}
            try:
                r = decidir_nota(ruta)
                if r["duda"]:
                    if f in respuestas:
                        midi, cents = respuestas[f], 0.0
                    else:
                        p = Pregunta(f, r, ruta)
                        self.duda_actual = p
                        self.puente.duda.emit(p)
                        p.evento.wait()
                        if p.respuesta is None or p.respuesta == -1:
                            fila.update(estado="SALTADA")
                            resumen["saltadas"] += 1
                            self.puente.fila.emit(fila)
                            continue
                        midi, cents = p.respuesta, 0.0
                else:
                    midi, cents = r["midi"], r["cents"]
                fila.update(nota=nombre_nota(midi), cents=round(float(cents), 1))

                afinada = abs(cents) >= UMBRAL_CENTS
                if afinada:
                    with wave.open(ruta, "rb") as w:
                        sr, ch = w.getframerate(), w.getnchannels()
                        raw = w.readframes(w.getnframes())
                    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
                    if ch > 1:
                        x = x.reshape(-1, ch).mean(axis=1)
                    y = _resample(x, sr, 2 ** (-cents / 1200.0))
                    destino = tempfile.mktemp(suffix=".wav", dir=salida)
                    _escribir_wav(destino, y, sr)
                else:
                    destino = ruta

                nuevo = nombre_limpio(midi)
                tiene, det = tiene_loop(destino)
                fila["loop"] = det
                if afinada or not tiene:
                    shutil.copy2(destino, os.path.join(REBUCLEO, nuevo))
                    fila["destino"] = "REBUCLEO"
                    resumen["rebucleo"] += 1
                else:
                    shutil.copy2(destino, os.path.join(salida, nuevo))
                    fila["destino"] = "APROBADAS"
                    resumen["aprobadas"] += 1
                if destino != ruta:
                    os.unlink(destino)
            except Exception as ex:
                fila.update(estado="ERROR", motivo=str(ex))
                resumen["errores"] += 1
            self.puente.fila.emit(fila)
        self.puente.fin.emit(resumen)

    # ------------------------------------------------------------- dudas --
    def mostrar_duda(self, p):
        """Muestra la duda CON el cents de cada candidata, para poder decidir."""
        self.panel.setVisible(True)
        self.combo.clear()
        r = p.resultado
        f0 = r.get("fundamental_hz")
        linea = f"<b>DUDA:</b> {p.archivo}"
        if f0:
            linea += f"<br>fundamental medida: <b>{f0:.2f} Hz</b>"
        linea += f"<br>motivo: {r.get('motivo')}"
        self.lbl_duda.setText(linea)

        # cada candidata, con el cents REAL de la muestra respecto de ella
        for m, peso in (r.get("candidatas") or [])[:6]:
            cents = _cents_respecto(p.ruta, m, f0)
            txt = f"{nombre_nota(m)}  (MIDI {m})"
            if cents is not None:
                txt += f"   -> la muestra esta {cents:+.1f} cents"
            txt += f"   [peso {peso:.2f}]"
            self.combo.addItem(txt, m)

        if self.combo.count():
            self.combo.setCurrentIndex(_mas_cercano(p.ruta, r))
        self.duda_actual = p

    def oir_duda(self):
        p = self.duda_actual
        if not p:
            return
        import subprocess
        for cmd in (["pw-play", p.ruta], ["paplay", p.ruta], ["aplay", "-q", p.ruta]):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return
            except Exception:
                continue

    def contestar(self, saltar):
        p = self.duda_actual
        if not p:
            return
        p.respuesta = -1 if saltar else self.combo.currentData()
        self.panel.setVisible(False)
        self.duda_actual = None
        p.evento.set()

    # -------------------------------------------------------------- filas --
    def add_fila(self, fila):
        n = self.tabla.rowCount()
        self.tabla.insertRow(n)
        vals = [fila.get("archivo", ""), fila.get("nota", ""),
                f"{fila['cents']:+.1f}" if fila.get("cents") is not None else "",
                fila.get("loop", ""), fila.get("estado") or fila.get("destino", "")]
        for c, v in enumerate(vals):
            it = QTableWidgetItem(str(v))
            self.tabla.setItem(n, c, it)
        self.tabla.scrollToBottom()
        self.barra.setValue(n + 1)

    def terminado(self, resumen):
        self.lbl_fin.setText(
            f"aprobadas {resumen['aprobadas']} · rebucleo {resumen['rebucleo']} · "
            f"saltadas {resumen['saltadas']} · errores {resumen['errores']}")
        self.btn_ir.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    w = Ventana()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
