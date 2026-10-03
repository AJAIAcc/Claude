#!/usr/bin/env python3
"""Analyse the track: beat grid, section novelty, band energies, vocal presence.
Outputs analysis/timing.json consumed by the renderer."""
import json, subprocess, sys, math
import numpy as np

SRC = "audio/track.mp3"
SR = 22050
FPS = 30.0

def decode(path, sr=SR):
    p = subprocess.run(["ffmpeg","-v","error","-i",path,"-ac","1","-ar",str(sr),
                        "-f","f32le","-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.float32).astype(np.float64)

x = decode(SRC)
dur = len(x)/SR
print(f"duration {dur:.3f}s  samples {len(x)}")

# ---- STFT ----
nfft, hop = 2048, 256                     # hop = 11.61ms
win = np.hanning(nfft)
nfr = 1 + (len(x)-nfft)//hop
S = np.empty((nfft//2+1, nfr))
for i in range(nfr):
    seg = x[i*hop:i*hop+nfft]*win
    S[:,i] = np.abs(np.fft.rfft(seg))
times = np.arange(nfr)*hop/SR
freqs = np.fft.rfftfreq(nfft, 1/SR)
logS = np.log1p(S*10)

# ---- spectral flux / onset envelope ----
diff = np.diff(logS, axis=1, prepend=logS[:,:1])
flux = np.sum(np.maximum(diff,0), axis=0)
flux = flux/ (np.max(flux) or 1)
# smooth
k = np.hanning(9); k/=k.sum()
flux_s = np.convolve(flux, k, mode='same')

# ---- tempo: lyrics say 170bpm; verify + phase-lock ----
def beat_phase(bpm):
    period = 60.0/bpm
    best, bestph = -1, 0
    for ph in np.arange(0, period, 0.005):
        t = np.arange(ph, dur, period)
        idx = np.clip((t*SR/hop).astype(int), 0, nfr-1)
        sc = flux_s[idx].mean()
        if sc > best: best, bestph = sc, ph
    return best, bestph

cands = {}
for bpm in [168,169,170,171,172,85,170/2]:
    sc, ph = beat_phase(bpm)
    cands[bpm]=(sc,ph)
    print(f"  bpm {bpm:7.2f} score {sc:.5f} phase {ph:.3f}")
BPM = 170.0
score, phase = cands[170]
period = 60.0/BPM
beats = np.arange(phase, dur, period)
print(f"BPM {BPM} phase {phase:.3f} -> {len(beats)} beats, bar={period*4:.3f}s")

# ---- band energies at FPS ----
nframes = int(dur*FPS)
ft = np.arange(nframes)/FPS
def band(lo,hi):
    m = (freqs>=lo)&(freqs<hi)
    e = S[m,:].mean(axis=0)
    return np.interp(ft, times, e)
sub   = band(20,120)      # kick / upright bass
low   = band(120,400)     # bass, low brass
mid   = band(400,2000)    # vocals, sax, trombone
high  = band(2000,6000)   # clarinet, trumpet, snare
air   = band(6000,11000)  # cymbals, air, sibilance
rms   = np.interp(ft, times, np.sqrt((S**2).mean(axis=0)))

def norm(a):
    a = a - a.min()
    return a/(a.max() or 1)
sub,low,mid,high,air,rms = map(norm,(sub,low,mid,high,air,rms))

# ---- novelty curve for section boundaries ----
# chroma-ish + timbre self similarity on coarse frames
cf = 4  # coarse: every ~46ms
M = logS[:, ::cf]
M = M / (np.linalg.norm(M,axis=0, keepdims=True)+1e-9)
ct = times[::cf]
W = 64
nov = np.zeros(M.shape[1])
for i in range(W, M.shape[1]-W):
    a = M[:, i-W:i].mean(axis=1)
    b = M[:, i:i+W].mean(axis=1)
    nov[i] = 1 - float(a@b)
nov = norm(np.convolve(nov, np.hanning(21)/np.hanning(21).sum(), mode='same'))
# peak pick
peaks=[]
for i in range(2,len(nov)-2):
    if nov[i]>nov[i-1] and nov[i]>=nov[i+1] and nov[i]>0.30:
        peaks.append((ct[i], float(nov[i])))
# dedupe within 3s keeping strongest
peaks.sort(key=lambda p:-p[1])
kept=[]
for t,v in peaks:
    if all(abs(t-k[0])>3.0 for k in kept): kept.append((t,v))
kept.sort()
print("\nsection candidates (t, strength):")
for t,v in kept: print(f"   {t:7.2f}s  {v:.3f}  bar {t/ (period*4):6.2f}")

out = {
  "duration": dur, "fps": FPS, "bpm": BPM, "beatPhase": float(phase),
  "beatPeriod": period, "barPeriod": period*4,
  "beats": [round(float(b),4) for b in beats],
  "frames": nframes,
  "bands": {k: [round(float(v),4) for v in arr] for k,arr in
            {"sub":sub,"low":low,"mid":mid,"high":high,"air":air,"rms":rms}.items()},
  "novelty": [[round(float(t),3), round(float(v),3)] for t,v in kept],
}
with open("analysis/timing.json","w") as f: json.dump(out,f)
print(f"\nwrote analysis/timing.json  frames={nframes}")
