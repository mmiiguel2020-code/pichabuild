# DIRECTRICES DE PICHABUILD

> Reglas que no se discuten. Cada una costó una sesión entera (o más)
> aprenderla a la mala. No se pueden saltar "porque esta vez es distinto".

------------------------------------------------------------------------------
## DIRECTRIZ 1 — EL BUCLE NO SE TOCA

**El bucle lo hace Polyphone. Nadie más.**

Aprendido a la mala: se intentó escribir SF2 con bucles a mano, se verificó
que Polyphone no escribe loops al importar SFZ, y se acabó perdiendo
trabajo. El bucle es del archivo fuente y **se respeta tal cual**.

Consecuencias obligatorias para cualquier herramienta de pichabuild:

- **Nunca** recalcular, mover, "mejorar", cuantizar ni reconstruir un loop.
- **Nunca** remuestrear una muestra con loop: cambiaría el largo y el loop
  dejaría de caer donde caía.
- Si hay que afinar una muestra que tiene loop, **se afina el SF2 (cents,
  fineTune, coarseTune), NO el audio**.
- Si una función no puede cumplir esto, **no se hace**. Punto.

------------------------------------------------------------------------------
## DIRECTRIZ 2 — NO HAY ARCHIVOS INTERMEDIOS QUE TOCAR AUDIO

Se parchea en memoria y se escribe una vez. Un SF2 intermedio se corrompe,
se propaga, y después no hay quien lo desenredecauce. Ya pasó.

------------------------------------------------------------------------------
## DIRECTRIZ 3 — ANTES DE CULPAR AL CÓDIGO, MIRA EL ARCHIVO

Se perdió una sesión culpando al parser de un "colapso de zonas" que en
realidad era que el SF2 fuente **no traía keyRange ni rootKey**.

------------------------------------------------------------------------------
## DIRECTRIZ 4 — EL OÍDO DE MIGUEL MANDA

Cuando dijo que algo suena mal, suena mal. Cuando eligió el gabbanelli,
ganó el gabbanelli (`chido sf2.sf2`).

------------------------------------------------------------------------------
## CÓMO SE APILA (esto es la cultura)

Cada herramienta nueva **se construye encima** de lo ya verificado:

```
  base      abrir un SF2, leer zonas, verificar         (sin tocar nada)
   + 1      oír una nota                                 (solo lectura)
   + 2      afinar de oído                              (escribe SOLO cents)
   + 3      ...
```

Ningún escalón nuevo puede romper uno de abajo. Si lo rompe, se quita.

------------------------------------------------------------------------------
## DIRECTRIZ 5 — EL MUSETTE NO SE CORRIGE

El musette va **fijo, en la muestra**: `fineTune = +15` en las tomas que
llevan vibración, `0` en las que no.

Las variaciones por octava **son del instrumento y harmonizan solas**
(medido en el repo: ~16 cents a C4, ~10 cents a C5). Ninguna herramienta de
pichabuild las ajusta ni avisa de ellas. Si se "arreglan", se estropea.

Y **el motor no suma nada**: el firmware trabaja con musette = 0. La muestra
ya llega lista para tocarse.

------------------------------------------------------------------------------
## EL FLUJO (nivel 1)

```
   entra carpeta de WAV
        │
        ▼
   ┌─────────────────────────────────────────┐
   │ 1  meter las notas (decir cual es cada) │
   │ 2  afinarlas (remuestreo)               │
   │ 3  renombrarlas  NOTA+OCTAVA_pn.wav     │
   │ 4  mandar a  ~/Escritorio/REBUCLEO/     │
   └─────────────────────────────────────────┘
        │
        ├── ¿necesitaba afinación o cambio de nota?
        │        SÍ  →  el rebucleo se hace a mano en Polyphone
        │        NO  →  pasa al NIVEL 2 de pichabuild
        ▼
   NIVEL 2: estructura (zonas, keyRange, rootKey, presets)
```

**Renombrar y afinar no tocan el loop.** Remuestrear sí cambia el largo:
por eso lo que se remuestrea **va a REBUCLEO**, y lo que no lo necesita
sigue derecho al nivel 2 con su loop intacto.

La carpeta siempre es la misma:  `~/Escritorio/REBUCLEO/`

------------------------------------------------------------------------------
## DIRECTRIZ 6 — EL AFINADOR ES EL JUEZ

Miguel: "el afinador tiene la decision. es afinador, su funcion es detectar
notas, yo no puedo afinar ni detectar de oido."

O sea:
-  La nota de cada muestra **la decide el afinador**. No se le pregunta a
  Miguel nota por nota: seria trabajo de esclavo y no sabe hacerlo.
-  El afinador **detecta y afina**. Es su oficio.
-  PERO el afinador **tiene que ser bueno**: no puede equivocarse de octava,
  porque entonces afinar con precision hacia una nota equivocada sigue siendo
  un error (el que costo la sesion del 23 de octubre).

Como se cumple eso sin tropezar otra vez:

  1.  Medir con **banda anclada** (±2 semitonos alrededor de lo esperado),
      que es lo que evita los saltos de octava.
  2.  Cuando el resultado **no es seguro** (dos octavas empatadas, confianza
      baja, muestra muy corta): NO se afina. Se marca DUDOSA y se aparta.
  3.  La app **dice que nota cree que es y con que confianza**, para que
      quede escrito en el informe.

Verificar siempre despues: remuestrear, volver a medir, y comprobar que la
nota quedo donde el afinador dijo.

------------------------------------------------------------------------------
## DIRECTRIZ 7 — EL BUCLE SOLO SE MIRA, NO SE ESCRIBE (ETAPA 1)

En esta etapa **el bucle no se lee, no se escala y no se recalcula**.
Se supone que llega bien. Pero **se comprueba que exista** antes de aprobar
la muestra:

```
muestra afinada
   │
   ├── ¿trae chunk 'smpl' con un loop válido?   (solo preguntar SÍ/NO)
   │        SÍ  →  aprobada  →  pasa al nivel 2
   │        NO  →  a  ~/Escritorio/REBUCLEO/    (a mano en Polyphone)
   │
   └── toda muestra que PASE por el afinador va a REBUCLEO de todas formas,
       porque el remuestreo le cambia el largo.
```

Sin leer el loop: no hay forma de estropearlo. Solo se pregunta si existe.

Cuidado con lo que cuenta como "tiene loop":
  · el chunk `smpl` con `numSampleLoops > 0`
  · los dos valores de loop NO los interpretamos ni los validamos aquí

Y ojo: un WAV generado con Python (`soundfile`) **no lleva `smpl`**, así que
saldría como "sin loop" aunque el audio tuviera uno. Los buenos son los
exportados de Polyphone.

------------------------------------------------------------------------------
## DIRECTRIZ 8 — LA NOTA SE BUSCA EN TODO EL RANGO

Miguel: "lo buscas en todo el rango con la banda ancha, si dudas, me preguntas."

  1.  El afinador busca la nota **en todo el teclado** (banda ancha), no anclado
      a un C4 ni al MIDIUnityNote del WAV (que en los archivos que tenemos
      viene desalineado y miente).
  2.  Si encuentra **una nota clara**: esa es. Se afina a ella.
  3.  Si **duda** (dos octavas empatadas, confianza baja, muestra muy corta):
      NO adivina. **Se pregunta a Miguel.**

Esa es la unica excepcion a la Directriz 6: el afinador decide siempre...
salvo cuando no esta seguro, y entonces pregunta.
