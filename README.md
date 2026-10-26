# pichabuilder 1.0

**`pichabuild` v1.0.0** — una caja que se apila, un escalón por vez. Todo lo
que costó aprender, junto y en un solo sitio.

**Tres cosas: afinar · nombrar · armar.**

## Las tres piezas

```
┌──────────────────────────────────────────────────────────────┐
│  CONSTRUIR   SF2 de muestras -> SF2 de 5 registros           │
│              scripts/hacer_5registros.sh  ENTRADA.sf2        │
├──────────────────────────────────────────────────────────────┤
│  NOMBRAR     la nota de cada muestra, en el nombre           │
│              F2.wav  G#3.wav  A#6_2.wav                      │
├──────────────────────────────────────────────────────────────┤
│  AFINAR      al cent más cercano, remuestreando              │
│              pichabuild.afinador  (del repo `afinador`)      │
└──────────────────────────────────────────────────────────────┘
```

## Uso rápido

### Construir los 5 registros

```bash
hacer_5registros  mi_banco.sf2
#  o:  ~/pichabuild/scripts/hacer_5registros.sh  mi_banco.sf2
```

Necesita un SF2 **con instrumento y zonas**. Sale un SF2 con:

```
prog 0 Clarinete · 1 Fagot · 2 Piccolo · 3 Violin · 4 Master
```

Ver **[docs/CONSTRUIR.md](docs/CONSTRUIR.md)** — incluida la config que
funciona, la que no, y por qué.

### Afinar y nombrar

```bash
# afinar una carpeta (remuestrea; la duración cambia ~3 %)
PYTHONPATH=~/pichabuild/src ~/pichedison/.venv/bin/python \
    ~/pichabuild/src/pichabuild/afinador/motor.py ENTRADA SALIDA

# decidir qué nota es cada muestra (o dudar, y preguntar)
PYTHONPATH=~/pichabuild/src python -m pichabuild CARPETA
```

## Las directrices

**Están en [docs/DIRECTRICES.md](docs/DIRECTRICES.md) y no se discuten.**
Ocho reglas, cada una costó una sesión entera:

1. **el bucle no se toca** (solo Polyphone lo escribe)
2. no hay archivos intermedios que toquen audio
3. antes de culpar al código, mira el archivo
4. el oído de Miguel manda
5. el musette no se corrige
6. el afinador es el juez
7. el bucle solo se mira, no se escribe
8. busca en todo el rango; si duda, pregunta

## Lo que hay dentro

```
src/pichabuild/
  core.py        nombres, leer WAV, comprobar loop, cents
  nota.py        decidir la nota en todo el rango / dudar
  pregunta.py    preguntar y recordar las respuestas
  etapa1.py      afinar + nombrar + repartir
  app.py         ventana PySide6 (etapa 1)
  afinador/      motor de afinación (del repo `afinador`)
  construir/     armar los 5 registros

scripts/hacer_5registros.sh    la construcción en un comando
docs/                          directrices, arquitectura, cómo construir
tests/                         12 pruebas
```

## Pruebas

```bash
~/pichedison/.venv/bin/python -m pytest ~/pichabuild/tests -q
```

## Probado (y funcionando)

```
viir.sf2        -> 5 presets, zonas 56/56/56/112/224   OK   (25 oct 2026)
gabbanelli.sf2  -> chido sf2.sf2                        OK   (24 oct 2026)
virgenes        61 wav -> afinados y nombrados (57 notas)
```

## Origen

- El motor de afinación viene de **[afinador](https://github.com/mmiiguel2020-code/afinador)**.
- El motor de construcción es `construir_sf2_acordeon.py` (45 KB, probado).
- Las directrices nacen de **[pichardeon-3.0](https://github.com/mmiiguel2020-code/pichardeon-3.0)**.

## Licencia

MIT.
