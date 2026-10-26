# Interiordades del afinador

Cómo funciona por dentro, y por qué está hecho así.

## 1. Por qué remuestrear y no estirar

Hay dos maneras de cambiar el tono de un sample:

**Remuestrear** — cambias la velocidad de reproducción. El tono y la duración
cambian juntos. Si subes 50 cents (3 %), dura un 3 % menos.

**Estirar (time-stretch)** — cambias el tono manteniendo la duración, con un
algoritmo que repite y recorta granos. La duración se conserva, pero **mete
artefactos**: pre-ecos, modulación, y en las muestras cortas de acordeón se oye.

Se eligió **remuestrear** porque:
- no añade artefactos
- es lo que hace un sampler de verdad al afinar
- el cambio de duración (≤ 3 %) es irrelevante en muestras de 2 s

## 2. Por qué pyin en dos pasadas

`librosa.pyin` es **probabilístico** (basado en HMM) y devuelve un `f0` por
cuadro, con huecos (`NaN`) donde no encuentra periodicidad.

El problema en las muestras de acordeón: los graves tienen **armónicos más
fuertes que el fundamental**. Con una sola pasada del rango completo (C2–C7),
`pyin` a veces se pasa una octava.

Solución: **dos pasadas**.

```
pasada 1:  C2 a C7          resolución 0.1 (10 cents)   -> resultado grueso
pasada 2:  grueso ± 2 semitonos   resolución 0.01 (1 cent)  -> resultado fino
```

La segunda pasada entra **sabiendo ya** en qué octava está, así que no puede
saltar.

## 3. Por qué se descartan cuadros

```python
f0[rms < rms.max() * 10**(-25/20)] = np.nan
```

Los samples tienen **cola** (el sonido baja hasta desaparecer) y **silencio**
alrededor. Si se mide ahí, `pyin` devuelve ruido y la mediana se corrompe.

Se descarta todo cuadro que esté **25 dB por debajo del RMS máximo**. Eso deja
solo la parte sonora y estable.

## 4. Por qué se rechazan 300 cents

```python
cents = 1200 * np.log2(f0 / med)
f0[np.abs(cents) > 300] = np.nan
```

Un `f0` a más de 300 cents (3 semitonos) de la mediana es físicamente imposible
en una muestra sostenida: es un **error de octava** del detector (1200, 1900 o
2400 cents exactos). Se descarta el cuadro y se recalcula sin él.

## 5. Por qué la mediana y no la media

La media la mueven los valores extremos. En un sample con un ataque y un
vibrato, cuatro o cinco cuadros de ataque arrastran la media.

La **mediana** es el valor central del reparto: aguanta hasta que el 50 % de los
cuadros estén mal, en vez de que unos pocos la estropeen.

## 6. Qué redondea a "nota exacta"

```python
midi_exacto = 69 + 12*log2(f0 / 440)     # 69 = La4
midi        = round(midi_exacto)          # la nota más cercana
cents       = 100*(midi_exacto - midi)    # el desvío que queda
objetivo    = 440 * 2**((midi-69)/12)     # la frecuencia de esa nota
```

El **redondeo elige la nota**, así que una muestra puede corregirse hasta
±50 cents. Si la corrección fuera mayor, sería que la muestra **no es la nota
que se cree** — y eso hay que mirarlo a mano, no arreglarlo remuestreando.

## 7. El control de pico

```python
if pico > 0.999:
    y = y * (0.999 / pico)
```

El remuestreo con splines puede **sobrepasar** el pico original y saturar.
Solo se toca si de verdad pasa de 0.999; si no, **no se cambia el nivel**. Es
importante no normalizar por sistema: cambiaría el balance entre muestras.

## 8. El `--solo-reportar`

Antes de afinar 59 archivos conviene saber **qué va a hacer**:

```bash
afinador entrada /tmp/x --solo-reportar
```

Mide todo y no escribe nada. Si las notas que reporta son coherentes, se corre
sin la opción.

## 9. Lo que este programa NO hace

- No quita ni respeta **bucles**. Si el WAV tiene chunk `smpl`, el remuestreo
  lo invalida (los puntos se refieren a las muestras viejas), pero `soundfile`
  no lo escribe de vuelta. Para conservar bucles hay que recalcularlos aparte.
- No **separa notas** de un archivo con varias.
- No **elige** la nota: la deriva de la frecuencia medida.
- No respeta **capas de velocidad**: cada archivo es independiente.

## 10. Historial

```
1.0.0   primer empaquetado. Script original de Miguel, usado sobre
        sambucles (59 muestras): residual máximo 1,00 cent.
```
