#!/bin/sh
# pichadirector — la ventana del director (escribe prompts)
#
# Cada arranque genera un token NUEVO y la pestaña vieja deja de servir.
# Por eso la URL buena se escribe tambien en el Escritorio, para poder
# abrirla con un clic sin depender de la pestaña anterior.
cd "$HOME/pichadirector" || exit 1
export GROQ_API_KEY="$(cat "$HOME/.groq.key" 2>/dev/null)"

# lanzar y capturar la URL que imprime
"$HOME/deepseek-harness/node_modules/.bin/dsh" \
    --profile director --patch "$HOME/pichadirector/sin-rea.yml" --port 3081 \
    > /tmp/pichadirector.log 2>&1 &

# esperar a que aparezca la URL (hasta 60 s)
i=0
while [ $i -lt 60 ]; do
  URL=$(grep -oE 'http://127\.0\.0\.1:3081/\?token=[A-Za-z0-9_-]+' /tmp/pichadirector.log 2>/dev/null | head -1)
  [ -n "$URL" ] && break
  sleep 1
  i=$((i+1))
done

if [ -z "$URL" ]; then
  echo "no arrancó. Mira /tmp/pichadirector.log"
  exit 1
fi

# dejar la URL en el Escritorio, con un archivo que se pueda abrir
printf '%s\n' "$URL" > "$HOME/Escritorio/ABRIR-DIRECTOR.txt"
# Type=Link ya no se puede lanzar en GNOME 50: va como Application, con la
# URL entre comillas (el "?" es caracter reservado en Exec).
cat > "$HOME/Escritorio/abrir-director.desktop" <<EOD
[Desktop Entry]
Type=Application
Name=Abrir el director
Comment=Abre la ventana del director ya autenticada
Exec=xdg-open "$URL"
Icon=web-browser
Terminal=false
Categories=Development;
EOD
chmod +x "$HOME/Escritorio/abrir-director.desktop"
gio set "$HOME/Escritorio/abrir-director.desktop" metadata::trusted true 2>/dev/null

echo "  director en marcha"
echo "  URL: $URL"
xdg-open "$URL" >/dev/null 2>&1 &
