# Construir los 5 registros

## El comando

```bash
scripts/hacer_5registros.sh  ENTRADA.sf2  [CARPETA_SALIDA]
```

o, instalado:

```bash
hacer_5registros  ENTRADA.sf2
```

## La config que funciona

La unica que ha sonado bien (`chido sf2.sf2`, `acordeon_viir.sf2`):

```json
"procesado": {
  "afinar": true,
  "usar_root_medido": true,
  "aplanar_tono": true,
  "aplanar_nivel": true,
  "umbral_tono_cents": 1.5,
  "umbral_nivel_db": 0.4,
  "max_correccion_nivel_db": 4.0,
  "loop_duracion_s": 0.5
},
"objetivo_rms_dbfs": -20.0
```

**NO cambiar.** Todo lo probado en contra sono a distorsion o salio roto:

| lo que se probó | resultado |
|---|---|
| `afinar: false` | distorsión |
| `objetivo_rms_dbfs: -6.0` | satura |
| `EscritorSF2` alimentado a mano | distorsión |
| escribir phdr/ibag/igen a mano | siempre roto |

## Los 5 registros

```
prog 0  Clarinete  = M
prog 1  Fagot      = L          (−12)
prog 2  Piccolo    = H          (+12)
prog 3  Violin     = M + M2     (musette +15)
prog 4  Master     = L + M + M2 + H
```

## El requisito de la entrada

```
instrumento con zonas
zonas con sampleID y keyRange  (que NO sean todas 0-0)
muestras con su loop
```

Si falta el instrumento, el script **se planta antes de construir**.

## El detalle que costó una tarde

```
el PARSER   espera entero    lo | (hi << 8)
el ESCRITOR espera tupla     (lokey, hikey)
```

Confundirlos da `TypeError` o zonas vacías.

## Cóndición de éxito

```
cada preset debe decir zonas=56 o más
NUNCA zonas=1
```

`zonas=1` significa que las `keyRange` de la entrada están vacías:
el mapeo colapsa y todo suena al mismo sample.

## El motor

`hacer_5registros.sh` llama a `construir_sf2_acordeon.py` (45 KB, probado).
Se puede apuntar a otra copia con `PICHABUILD_MOTOR=/ruta/al/script.py`.

------------------------------------------------------------------------------
## LA SECCION 2 RECIBE UNA CARPETA DE WAV, NO UN SF2

Asi lo pidio Miguel: *"a la segunda etapa se entregan las muestras aprobadas,
no un sf2"*.

El camino es:

```
  carpeta de WAV aprobados  (con su loop y su nota en el nombre)
        │
        ▼  1. base_sf2.py
  SF2 con 1 instrumento y 1 zona por muestra
      keyRange = rootKey = la nota del nombre,  modo loop
        │
        ▼  2. construir_sf2_acordeon.py
  SF2 de 5 registros
```

**Lo que necesita cada WAV:**

```
nombre con la nota     C4.wav · G#3.wav · A#6_2.wav
chunk 'smpl'           el loop, que lo pone Polyphone
```

**Verificado:** el audio sale **bit a bit idéntico** al WAV (14/14 comparados
muestra por muestra). El loop se copia con sus mismos frames.

**El error que costo una tarde** (ya corregido): el `EOI` del chunk `inst`
tiene que apuntar a **N** (el numero de zonas), no a N+1. Si apunta a N+1,
el lector recorre `ibag[bi+1]` y se sale del array:
`IndexError: list index out of range`.
