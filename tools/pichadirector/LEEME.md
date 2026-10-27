# pichadirector

Una segunda instancia de DeepSeek Harness que **escribe prompts** para que el
agente ejecutor los corra. Usa **Groq** (nivel gratuito) en vez de DeepSeek.

## Cómo está montado

```
~/.dsh/profiles/director/          el perfil (copia del perfil web)
   cordis.patch.yml                modelo + ruta de Groq   (aqui copiado)
~/pichadirector/
   AGENTS.md                       su oficio: leer el estado y escribir prompts
   sin-rea.yml                     overlay que apaga lo que no usa
~/.groq.key                        la clave de Groq (permisos 600)
~/.dsh/.credentials.yaml           GROQ_API_KEY dentro de "refs"
~/bin/pichadirector                el lanzador
~/Escritorio/pichadirector.desktop arranca el servidor
~/Escritorio/abrir-director.desktop abre la ventana ya autenticada
```

Puerto **3081**. La ventana del ejecutor esta en el 3080.

## Las dos trampas que costaron la tarde

### 1. Las herramientas NO estan en el arbol general

Estan **dentro del preset del agente** (`preset-standard`). Apagar plugins por
fuera no sirve: el preset los vuelve a montar. Hay que reescribir el preset.

```yaml
- id: preset-standard
  name: "@deepseek-ai/dsh-agent-preset"
  config:
    plugins:
      - persona · agent-instructions · time-context · tool-bash
```

### 2. El REA se inserta DESPUES, y trae 200 herramientas

`~/.dsh/cordis.patch.yml` hace `insert:` de `rea-mcp` para **todos** los
perfiles, y se aplica despues de `cordis.patch.yml` del perfil. Poner el
`disabled` en el perfil no sirve: hay que hacerlo en el overlay que pasa
`--patch` al lanzar.

Groq rechaza mas de **128 herramientas** por peticion. El REA solo ya pasa de
200.

## Los limites de Groq (nivel gratuito)

```
8.000 tokens por minuto     por CUENTA, igual en todos los modelos
1.000 peticiones
131.072 de contexto
```

Cada herramienta que se manda cuesta 600-900 tokens de manual **en cada
peticion**. Con 30 herramientas el manual eran 7.150 tokens y no cabia ni un
"hola". Con bash solo, ~600.

## El truco del token

Cada arranque genera un token nuevo y **la pestaña anterior muere**. Por eso el
lanzador escribe la URL buena en `~/Escritorio/ABRIR-DIRECTOR.txt` y genera
`abrir-director.desktop`.

## Si hay que rehacerlo

```bash
dsh --profile director --from-default-profile web
# copiar cordis.patch.yml de esta carpeta a ~/.dsh/profiles/director/
# copiar AGENTS.md a ~/pichadirector/
# meter GROQ_API_KEY en ~/.dsh/.credentials.yaml, bajo refs:
```
