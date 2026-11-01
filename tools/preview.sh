#!/bin/sh
# Renders the art into $1 (images/, blocks/, neko.txt) and makes a contact sheet
# of the first frames: $1/sheet.png
set -e
out=${1:?outdir}
python3 "$(dirname "$0")/draw.py" "$out" >/dev/null
cd "$out/images"
for f in neko-*.gif; do magick "${f}[0]" -background '#282a36' -flatten "${f%.gif}.png"; done
magick montage neko-*.png -tile 6x -geometry 256x256+4+4 -background '#111' ../sheet.png
