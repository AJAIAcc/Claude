#!/usr/bin/env bash
# Parallel frame render -> H.264 + original audio.
set -euo pipefail
cd "$(dirname "$0")/.."
W=${W:-1920}; H=${H:-1080}; JOBS=${JOBS:-4}; GRAIN=${GRAIN:-6}
OUT=${OUT:-out/take_a_bow.mp4}; PRESET=${PRESET:-slow}; CRF=${CRF:-17}
FR=out/frames
TOTAL=$(node -e "const d=require('./analysis/drive.json');console.log(d.frames)")
echo "render ${W}x${H}  frames=$TOTAL  jobs=$JOBS -> $OUT"
rm -rf "$FR"; mkdir -p "$FR" out
CH=$(( (TOTAL + JOBS - 1) / JOBS ))
pids=()
for ((i=0;i<JOBS;i++)); do
  A=$(( i*CH )); B=$(( A+CH )); (( B>TOTAL )) && B=$TOTAL
  (( A>=TOTAL )) && continue
  node tools/worker.mjs "$A" "$B" "$W" "$H" "$FR" "$GRAIN" &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p"; done
N=$(ls "$FR" | wc -l)
echo "frames written: $N / $TOTAL"
[ "$N" -eq "$TOTAL" ] || { echo "FRAME COUNT MISMATCH"; exit 1; }
ffmpeg -y -v error -stats -framerate 30 -i "$FR/%06d.jpg" -i audio/track.mp3 \
  -vf "eq=contrast=1.075:saturation=1.10:gamma=0.985" \
  -c:v libx264 -preset ${PRESET:-slow} -crf ${CRF:-17} -pix_fmt yuv420p -profile:v high -level 4.2 \
  -c:a aac -b:a 256k -shortest -movflags +faststart "$OUT"
rm -rf "$FR"
ls -la "$OUT"; ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT"
