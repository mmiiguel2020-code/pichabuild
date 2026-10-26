#!/bin/bash
# ============================================================================
#  hacer_5registros.sh  —  de un SF2 de muestras a un SF2 de 5 registros
# ============================================================================
#  LO QUE FUNCIONO (25 oct 2026, viir.sf2 y gabbanelli.sf2). No cambiar nada.
#
#  Uso:   ./hacer_5registros.sh  ENTRADA.sf2
#         ./hacer_5registros.sh  ENTRADA.sf2  CARPETA_SALIDA
#
#  REQUISITO en el SF2 de entrada (si falta, no funciona):
#     · instrumento con zonas
#     · cada zona con sampleID y keyRange (que NO sean todas 0-0)
#     · las muestras con su loop (lo pone Polyphone)
#
#  Si el SF2 viene SIN instrumento (solo muestras), este script se planta:
#  hay que abrirlo en Polyphone y guardarlo con su instrumento primero.
# ============================================================================
set -e

ENT="${1:?uso: $0 ENTRADA.sf2 [CARPETA_SALIDA]}"
SAL="${2:-}"

if [ ! -f "$ENT" ]; then echo "no existe: $ENT"; exit 1; fi
BASE=$(basename "$ENT" .sf2)
if [ -z "$SAL" ]; then
  SAL="$(dirname "$ENT")/5reg_$BASE"
fi
mkdir -p "$SAL"

HERR="${PICHABUILD_MOTOR:-$HOME/herramientas/construir_sf2_acordeon.py}"
PY="$HOME/pichedison/.venv/bin/python"

echo "entrada : $ENT"
echo "salida  : $SAL"
echo

# --- 0. comprobar que el SF2 sirve ANTES de gastar 10 minutos -------------
echo "== comprobando la entrada =="
"$PY" - "$ENT" <<'PYEOF' || exit 1
import struct, sys
d = open(sys.argv[1], 'rb').read()
def look(c):
    i = d.find(c)
    return (i, struct.unpack('<I', d[i+4:i+8])[0]) if i >= 0 else (None, 0)
_, s_inst = look(b'inst')
_, s_ibag = look(b'ibag')
_, s_igen = look(b'igen')
_, s_shdr = look(b'shdr')
ni = s_inst // 22 - 1 if s_inst else 0
nz = s_ibag // 4 - 1 if s_ibag else 0
nm = s_shdr // 46 - 1 if s_shdr else 0
print(f"  instrumentos {ni} · zonas {nz} · muestras {nm}")
if ni == 0:
    print("  FALLA: no tiene instrumento.")
    print("         Abrelo en Polyphone, guardalo, y vuelve a intentarlo.")
    sys.exit(1)
if nz == 0:
    print("  FALLA: el instrumento no tiene zonas.")
    sys.exit(1)
if nm == 0:
    print("  FALLA: no tiene muestras.")
    sys.exit(1)
print("  OK")
PYEOF

# --- 1. config: LA MISMA QUE FUNCIONO ------------------------------------
echo "== configurando los 5 registros =="
"$PY" "$HERR" plantilla --salida "$SAL/registros.json" >/dev/null
"$PY" - "$SAL/registros.json" <<'PYEOF'
import json, sys
p = sys.argv[1]
c = json.load(open(p))
c["nombre_banco"] = "5 registros"
c["afinacion_a4_hz"] = 440.0
# procesado: EXACTAMENTE lo que funciono (chido sf2.sf2)
c["procesado"] = {"afinar": True, "usar_root_medido": True,
                  "aplanar_tono": True, "aplanar_nivel": True,
                  "umbral_tono_cents": 1.5, "umbral_nivel_db": 0.4,
                  "max_correccion_nivel_db": 4.0, "loop_duracion_s": 0.5}
c["objetivo_rms_dbfs"] = -20.0
c["banco"] = 0
c["voces"]["M2"]["afinacion_cents"] = 15.0
c["registros"] = [
    {"nombre": "Clarinete", "programa": 0, "voces": ["M"]},
    {"nombre": "Fagot",     "programa": 1, "voces": ["L"]},
    {"nombre": "Piccolo",   "programa": 2, "voces": ["H"]},
    {"nombre": "Violin",    "programa": 3, "voces": ["M", "M2"]},
    {"nombre": "Master",    "programa": 4, "voces": ["L", "M", "M2", "H"]},
]
# el rango se deja al que tenga la fuente
c["rango_notas"] = None
json.dump(c, open(p, 'w'), indent=2, ensure_ascii=False)
print("  procesado:", json.dumps(c["procesado"]))
print("  objetivo_rms_dbfs:", c["objetivo_rms_dbfs"])
PYEOF

# --- 2. construir ---------------------------------------------------------
echo
echo "== construyendo =="
"$PY" "$HERR" construir \
  --sf2 "$ENT" \
  --config "$SAL/registros.json" \
  --salida "$SAL/5registros.sf2" \
  --wavs "$SAL/wavs" 2>&1 | tail -10

# --- 3. verificar (CONDICION DE EXITO: zonas > 1) -------------------------
echo
echo "== verificando =="
"$PY" "$HERR" verificar --sf2 "$SAL/5registros.sf2" --config "$SAL/registros.json" \
  | tee "$SAL/verificacion.txt"

echo
if grep -q "zonas=1 " "$SAL/verificacion.txt"; then
  echo "  OJO: alguna zona salio =1. Revisa la entrada (keyRange todas 0-0?)."
  exit 1
fi
if ! grep -q "OK" "$SAL/verificacion.txt"; then
  echo "  OJO: la verificacion no dijo OK."
  exit 1
fi

echo "  LISTO: $SAL/5registros.sf2"
echo
echo "  Abrelo en Polyphone y pruebalo ENTERO antes de darlo por bueno."
