# PICHABUILD — la cultura apilada

## Qué es

Una caja que crece **hacia arriba**, un escalón por vez, sin repetir errores.

```
┌──────────────────────────────────────────────────────────┐
│  4   app: afinar de oído       (escribe SOLO cents)      │
├──────────────────────────────────────────────────────────┤
│  3   app: oír una nota         (solo lectura)            │
├──────────────────────────────────────────────────────────┤
│  2   verificar                 (dice qué está mal)       │
├──────────────────────────────────────────────────────────┤
│  1   leer un SF2               (samples, zonas, presets) │
└──────────────────────────────────────────────────────────┘
```

**Cada escalón usa el de abajo y no lo modifica.**

------------------------------------------------------------------------------
## El monopolio del bucle (Directriz 1)

| Quién | Qué puede hacer con el bucle |
|---|---|
| **Polyphone** | todo. Es el único que lo escribe bien. |
| **pichabuild** | **leerlo y respetarlo**. Nada más. |

Si algún día alguien intenta añadir "recalcular loop" a pichabuild:
**está prohibido por la Directriz 1.** No se discute.

------------------------------------------------------------------------------
## Qué escribe y qué no

```
pichabuild 1.0
  LEE        todo el SF2
  ESCRIBE    nada todavía
  OYE        una nota por su zona

pichabuild 1.1
  ESCRIBE    cents (fineTune) de una zona   ← lo único
  NO toca    samples · loops · keyRange · rootKey · presets
```

**Afinar de oído** = cambiar `fineTune` (generador 52) de la zona y volver a
oír. El audio no se toca, así que **el loop sigue intacto**. Esto es lo que
hace que la Directriz 1 sea compatible con el afinador.

------------------------------------------------------------------------------
## Las piezas

```
pichabuild/
  src/pichabuild/
    core.py        leer · verificar · escribir  (sin audio)
    app.py         la ventana (PySide6)
  docs/
    DIRECTRICES.md   las reglas que no se discuten
    ARQUITECTURA.md  esto
  tests/
```

## El escalón 1 en concreto

`core.leer()` devuelve un modelo con lo que de verdad hay:

```python
Banco(
  nombre
  presets  = [(nombre, banco, programa, [zonas])]
  zonas    = [(preset, teclas, vel, root, sample, modo_loop)]
  muestras = [(nombre, frames, rate, loop_ini, loop_fin)]
  avisos   = ["zona sin keyRange", "zona sin rootKey", ...]
)
```

**Y `verificar()` es lo más valioso del paquete**: dice si un SF2 está
usable antes de gastar una hora construyendo algo encima.
