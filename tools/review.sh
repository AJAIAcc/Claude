#!/usr/bin/env bash
# Sample frames from a rendered video into a contact sheet (reviews the real output).
set -euo pipefail
cd "$(dirname "$0")/.."
VID=${1:-out/preview.mp4}; START=${2:-0}; END=${3:-222}; N=${4:-12}; COLS=${5:-4}
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
STEP=$(python3 -c "print(($END-$START)/max(1,$N-1))")
for ((i=0;i<N;i++)); do
  T=$(python3 -c "print($START+$i*$STEP)")
  ffmpeg -v error -ss "$T" -i "$VID" -frames:v 1 -q:v 3 "$TMP/$(printf %03d $i).jpg" -y
  python3 - "$TMP/$(printf %03d $i).jpg" "$T" <<'PY'
import sys
from PIL import Image, ImageDraw
p,t=sys.argv[1],float(sys.argv[2])
im=Image.open(p).convert('RGB'); d=ImageDraw.Draw(im)
d.rectangle([0,im.height-26,180,im.height],fill=(0,0,0))
d.text((6,im.height-20),f"{t:.1f}s",fill=(255,255,255))
im.save(p)
PY
done
python3 - "$TMP" "$COLS" out/review.png <<'PY'
import sys,os
from PIL import Image
d,cols,out=sys.argv[1],int(sys.argv[2]),sys.argv[3]
fs=sorted(f for f in os.listdir(d) if f.endswith('.jpg'))
ims=[Image.open(os.path.join(d,f)) for f in fs]
w,h=480,270
ims=[i.resize((w,h)) for i in ims]
rows=(len(ims)+cols-1)//cols
sheet=Image.new('RGB',(cols*(w+4)+4,rows*(h+4)+4),(24,24,24))
for k,i in enumerate(ims): sheet.paste(i,(4+(k%cols)*(w+4),4+(k//cols)*(h+4)))
sheet.save(out); print(out, sheet.size)
PY
