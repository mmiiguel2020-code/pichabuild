# Los cents por registro

> Corregido por Miguel el 26 oct 2026. **Sustituye a la tabla vieja** de
> `HISTORIA_CONDENSADA_DEL_PROYECTO.md:42,123`.

## La tabla buena

```
registro   voces              cents
---------  -----------------  --------------------------------
Clarinete  M                   0
Fagot      L                   0        (Bassoon)
Bandoneon  L + M+              L 0  ·  M+  0 … +20
Violin     M + M+              M 0  ·  M+  0 … +20
Master     L + M + M+          L 0 … −20  ·  M 0  ·  M+ 0 … +20
```

**La novedad es la L del Master**: puede ir de **0 a −20 cents**. Las demás
voces L van a 0 fijo.

## Cómo queda cada voz

| voz | qué es | cents ajustable |
|---|---|---|
| **L** | lengüeta de 16' (−12 semitonos) | solo en **Master** (0 … −20) |
| **M** | lengüeta de 8' | no (0 fijo) |
| **M+** | segunda lengüeta de 8' (musette) | sí, **0 … +20** |

## Lo que esto NO cambia

- El musette **no se corrige** (Directriz 5): se elige al armar, y una vez
  elegido vale para todo el banco.
- El motor va **en 0**: la muestra ya trae el carácter.

## Rango de valores en la app

```
Voz L   (solo Master)   −20 …  0     por defecto  ~0
Voz M+                  +0  … +20    por defecto  ~+15
Voz M                   0 fijo
```

**Independientes**: cada registro tiene su propio valor de M+ (y Master el
suyo de L). Se consigue multiplicando la voz en la config que se le pasa al
motor -- `M2_band`, `M2_violin`, `M2_master` -- sin tocar el motor: el motor
ya toma `afinacion_cents` de `cfg["voces"][vn]`, una por voz.

*Debe coincidir con el motor `construir_sf2_acordeon.py`: `afinacion_cents`
se escribe como `fineTune` de la zona, ±100 cents por semitono.*
