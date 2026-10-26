# pichabuilder — historial

## 1.0.0 — 26 de octubre de 2026

Primera versión que hace el ciclo completo y está probada de punta a punta.

### Lo que hace

```
SECCION 1   carpeta de WAV  ->  afinadas y nombradas
            (o a REBUCLEO si hubo que remuestrear o no traen loop)

SECCION 2   carpeta de WAV aprobados  ->  SF2 de 5 registros
            Clarinete · Fagot · Bandoneon · Violin · Master
```

### Lo que entró

- **Ventana de dos secciones** (`app2.py`, PySide6). Lanzador en el Escritorio.
- **Afinar**: del repo `afinador` (librosa pyin, residual medio 0,34 cent).
- **Nombrar**: `nota.py` decide la nota buscando en todo el rango con picos
  reales; si duda, pregunta y **recuerda** la respuesta.
- **Armar**: `base_sf2.py` hace el SF2 base desde los WAV (audio y loop
  intactos, verificado bit a bit) y luego los 5 registros.
- **Revisor** (`revisar.py`): avisa antes de armar si faltan `keyRange`,
  `rootKey` o `smpl`. Se niega a construir lo que saldría mal.
- **Cents independientes por registro** (Directriz 10): Bandoneón, Violín y
  Master con su propio musette; la L del Master de 0 a −20.
- **Envolvente** ajustable: ataque y cola, con los valores del motor por
  defecto (25 / 80 ms).

### Arreglos importantes

- **Lotes**: los nombres ya no se pisan (`D3.wav`, `D3_2.wav`, …); el temporal
  va a `/tmp`; nunca sobreescribe.
- **WAV de 24 bits**: `leer_pcm` lee 8, 16, 24 y 32 bits. Antes reventaba con
  `buffer size must be a multiple of element size`.
- **EOI del chunk `inst`**: apunta a N (zonas), no a N+1. Con N+1 el lector se
  sale del array (`IndexError`).

### Probado

```
29 pruebas, 29 pasan
61 WAV en lote (24 bits) -> 61 de 61, sin pérdidas
APROBADAS (14 WAV) -> 5registros.sf2, zonas 14/14/28/28/42, verificación OK
audio del SF2 base idéntico bit a bit al WAV (14/14)
```

### Las 10 directrices

En `docs/DIRECTRICES.md`. Cada una costó una sesión aprenderla a la mala.

### Lo que NO hace

- No pone bucles: los pone Polyphone (Directriz 1).
- No inventa notas: mide, y si duda pregunta.
- No es un sampler en tiempo real: es para editar.
