#!/usr/bin/env bash
# Prove picture events land on their musical events: pull the frame at each known
# musical landmark and lay it beside the audio energy at that instant.
set -euo pipefail
cd "$(dirname "$0")/.."
VID=${1:-out/take_a_bow_humanity.mp4}
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
# landmark, label
LM=("2.11|first downbeat / title slam" "12.30|band hit -> title card" "24.95|verse 1 enters"
    "45.85|pre-chorus call" "50.85|chorus 1 hits" "68.35|clarinet solo"
    "99.70|tenor sax" "129.45|triptych" "152.90|half-time bridge"
    "159.72|bridge explodes back" "188.92|final chorus" "221.20|the last bow")
i=0
for e in "${LM[@]}"; do
  T="${e%%|*}"
  ffmpeg -v error -ss "$T" -i "$VID" -frames:v 1 -q:v 3 "$TMP/$(printf %02d $i).jpg" -y
  i=$((i+1))
done
python3 - "$TMP" "$VID" <<'PY'
import sys,os,subprocess,numpy as np
from PIL import Image, ImageDraw
d=sys.argv[1]
LM=[("2.11","first downbeat / title slam"),("12.30","band hit -> title card"),("24.95","verse 1 enters"),
    ("45.85","pre-chorus call"),("50.85","chorus 1 hits"),("68.35","clarinet solo"),
    ("99.70","tenor sax"),("129.45","triptych"),("152.90","half-time bridge"),
    ("159.72","bridge explodes back"),("188.92","final chorus"),("221.20","the last bow")]
SR=22050
r=subprocess.run(["ffmpeg","-v","error","-i","audio/track.mp3","-ac","1","-ar",str(SR),"-f","f32le","-"],
                 capture_output=True,check=True)
x=np.frombuffer(r.stdout,dtype=np.float32).astype(np.float64)
w,h=460,259
sheet=Image.new('RGB',(3*(w+6)+6,4*(h+40)+6),(22,22,22))
dr=ImageDraw.Draw(sheet)
for k,(t,label) in enumerate(LM):
    p=os.path.join(d,f"{k:02d}.jpg")
    if not os.path.exists(p): continue
    im=Image.open(p).resize((w,h))
    X=6+(k%3)*(w+6); Y=6+(k//3)*(h+40)
    sheet.paste(im,(X,Y))
    tt=float(t); a=int((tt-0.25)*SR); b=int((tt+0.25)*SR)
    seg=x[max(0,a):min(len(x),b)]
    rms=float(np.sqrt((seg**2).mean())) if len(seg) else 0.0
    dr.text((X+4,Y+h+6),f"{t}s  {label}",fill=(255,255,255))
    dr.text((X+4,Y+h+22),f"audio RMS +/-0.25s = {rms:.3f}",fill=(170,200,255))
    bw=int(min(1.0,rms*6)*(w-16))
    dr.rectangle([X+4,Y+h+34,X+4+bw,Y+h+37],fill=(120,220,160))
sheet.save("out/syncheck.png"); print("out/syncheck.png",sheet.size)
PY
