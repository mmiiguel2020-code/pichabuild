# pichadirector — informe de medición

27 oct 2026. Todas las cifras salen del espía local (`tools/groq-spy.mjs`),
de los registros de sesión de DSH (`request/header` y `usage`) o de cabeceras
de Groq. Nada estimado.

---

## 1. Antes y después

| # | Configuración | herramientas | chars tools | tokens entrada reales | status |
|---|---|---|---|---|---|
| 0 | original (con REA) | 241 | 862.242 | — (no llegó a responder) | 400 `tools > 128` |
| 1 | REA off, 31 tools | 31 | 28.552 | 6.616 | 413 (`Requested` 8.296) |
| 2 | solo preset reescrito | 25 | 20.729 | — | (no bajó: el árbol seguía) |
| 3 | solo plugins del árbol off | 2 | 2.847 | — | (faltaba el preset) |
| 4 | **árbol + preset + REA off** | **1** | **2.328** | **684** | **200 OK** |

Medición de la fila 4, tres turnos seguidos:
`684/37 · 684/32 · 684/40` → **3 turnos dentro de 60 s, sin 413 ni 429**.

### El error que faltaba encontrar: `max_tokens`

```
Requested 66.223  =  687 de entrada  +  65.536 de reserva de salida
```

`gpt-oss-120b` declara `maxTokens: 65536` en el catálogo de pi-ai, y DSH lo
manda entero. **Groq reserva ese hueco dentro del cupo de 8.000/min**, así que
la petición fallaba aunque el texto fuera diminuto.

Arreglo (en el perfil, no en el overlay):

```yaml
- id: llm-pi-ai
  config:
    providers:
      groq:
        modelOverrides:
          openai/gpt-oss-120b:
            maxOutputTokens: 1500
```

Nota: `models:` **no** sirve para esto (reemplaza el catálogo y se pierden los
demás campos); hay que usar `modelOverrides:`. Tampoco basta `maxTokens` como
clave hija: el código lee `maxOutputTokens` primero.

### Segundo hallazgo: `qwen` no sirve con DSH

Con `qwen/qwen3.8-27b`:

```
400 failed to template request: minijinja: rendering failed:
    raise_exception: Unexpected message role.
```

La plantilla de Qwen en Groq no acepta el rol `developer` que DSH manda.
`openai/gpt-oss-120b` sí. **Modelo definitivo: gpt-oss-120b.**

---

## 2. Orden de capas — comprobado con canario

Canario: `agent-default-model.model` con un valor distinto en cada capa, sobre
una copia `DSH_HOME=/tmp/dsh-canario`.

| capas presentes | valor que gana |
|---|---|
| perfil + home + `--patch` | **CAPA-PATCH** |
| perfil + home | **CAPA-HOME** |
| `--patch` con las tres | **CAPA-PATCH** |

El propio `--dump-config` lo declara en la cabecera:

```
# == @deepseek-ai/dsh-base, patched by
#    <perfil>/cordis.patch.yml,
#    $DSH_HOME/cordis.patch.yml,
#    <overlay --patch>
```

**Conclusión: bundles → perfil → home → `--patch`. Gana el último.**

Consecuencia práctica: por eso `rea-mcp` hay que apagarlo en el **overlay**; el
home lo inserta después del perfil, así que apagarlo en el perfil no sirve.

---

## 3. Decisión: B2 (sin herramientas) o B3 (herramienta propia)

**Ninguna de las dos. Se queda `bash` (1 herramienta).**

La cifra que lo justifica: con `bash` la petición son **684 tokens** (1 tool,
2.328 chars). El presupuesto es 8.000/min → **~11 peticiones por minuto**. Tres
turnos seguidos ya se midieron sin fallo.

B2 (cero herramientas) ahorraría 2.328 chars ≈ 600 tokens, pero dejaría al
director sin poder leer el repositorio, que es su único trabajo. B3 (herramienta
propia) daría lo mismo que `bash` con más piezas que mantener.

**Regla operativa que sí hay que respetar:** cada turno reenvía el historial.
En una conversación larga el gasto crece. **Un prompt por conversación**: abrir
chat nuevo para cada tarea.

---

## 4. Cómo lo abre Miguel

```
1. doble clic en "pichadirector" del Escritorio   (arranca y abre solo)
   o doble clic en "abrir-director"                (si ya está arrancado)
```

Verificación de que está bien:

```bash
ss -ltn | grep 3081                       # escucha
cat ~/Escritorio/ABRIR-DIRECTOR.txt       # URL con token
```

Prueba de humo sin navegador (perfil de prueba, gasta 1 petición):

```bash
cd ~/deepseek-harness
GROQ_API_KEY="$(cat ~/.groq.key)" ./node_modules/.bin/dsh \
  --profile director-test --patch ~/pichadirector/sin-rea.yml "Di solo: OK"
```

---

## 5. Listas finales

### VERIFICADO
- 1 herramienta (`bash`), 2.328 chars, 684 tokens de entrada — medido con espía
  y con registro de sesión.
- `max_tokens` de 65.536 era la causa del 413 (`Requested 66.223` = 687+65.536).
- `modelOverrides.maxOutputTokens: 1500` lo corrige; 3 turnos seguidos sin error.
- `qwen` falla por `Unexpected message role`; `gpt-oss-120b` responde.
- Orden de capas: perfil → home → `--patch`, con canario y con la cabecera del
  dump.
- El REA solo se apaga en el overlay (el home lo inserta después).
- Las herramientas del perfil web vienen de **dos** sitios (árbol + preset) y hay
  que apagarlas en los dos.
- Groq no cuenta `max_tokens` pequeños en el TPM de forma bloqueante
  (probado con 16.384 vía curl: 200), pero sí cuenta la reserva grande.

### NO VERIFICADO
- El número exacto de herramientas que manda el **servidor web real** (3081).
  Medido en `headless`, que no monta el preset; el preset se validó solo con
  `--dump-config`. **La primera respuesta buena de Miguel lo confirma o lo
  desmiente.**
- Cuántos turnos caben en una misma conversación del 3081 antes del 429 (el
  historial crece; no se midió).
- Si `AGENTS.md` se relee en cada turno o solo al crear la sesión.
- Cuánto aportan `persona` y `time-context` al tamaño de la petición.

---

## Archivos tocados

```
~/.dsh/profiles/director/cordis.patch.yml         modelo + modelOverrides
~/.dsh/profiles/director-test/cordis.patch.yml    clon de prueba
~/pichadirector/sin-rea.yml                       overlay definitivo
~/pichadirector/tools/groq-spy.mjs                el espía (modo stub)
~/pichadirector/test-spy.yml                      apunta al espía (solo pruebas)
~/bin/pichadirector                               lanzador + URL al Escritorio
```

Respaldos con fecha: `*.bak-YYYYMMDD-HHMM` junto a cada archivo editado.
