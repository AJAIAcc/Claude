#!/usr/bin/env python3
"""Proper tempo estimate: autocorrelation + comb-filter over the onset envelope."""
import subprocess, numpy as np
SR=22050
r=subprocess.run(["ffmpeg","-v","error","-i","audio/track.mp3","-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True)
x=np.frombuffer(r.stdout,dtype=np.float32).astype(np.float64)
nfft,hop=1024,128                      # 5.8 ms resolution
win=np.hanning(nfft); nfr=1+(len(x)-nfft)//hop
S=np.empty((nfft//2+1,nfr),dtype=np.float32)
for i in range(nfr): S[:,i]=np.abs(np.fft.rfft(x[i*hop:i*hop+nfft]*win))
fps=SR/hop
L=np.log1p(S*8)
flux=np.sum(np.maximum(np.diff(L,axis=1,prepend=L[:,:1]),0),axis=0)
flux-=np.convolve(flux,np.ones(int(fps*0.4))/int(fps*0.4),mode='same')
flux=np.clip(flux,0,None); flux/=flux.std()
# --- autocorrelation ---
n=len(flux); ac=np.correlate(flux-flux.mean(),flux-flux.mean(),'full')[n-1:]
ac/=ac[0]
print("top autocorrelation lags (period -> implied BPM):")
cands=[]
for lag in range(int(fps*0.25),int(fps*1.4)):
    if ac[lag]>ac[lag-1] and ac[lag]>=ac[lag+1]:
        cands.append((ac[lag],lag/fps))
cands.sort(reverse=True)
for v,p in cands[:14]:
    print(f"   r={v:.4f}  period {p:.4f}s  -> {60/p:7.2f} bpm   (x2 {120/p:7.2f})")
# --- comb filter over bpm grid, phase-optimised ---
print("\ncomb-filter score across tempo grid:")
best=[]
for bpm in np.arange(60,210,0.25):
    per=60.0/bpm; step=per*fps
    npulse=int(n/step)
    if npulse<20: continue
    idx=(np.arange(npulse)*step).astype(int)
    # best phase
    bs=0
    for ph in range(0,int(step),max(1,int(step//12))):
        j=idx+ph; j=j[j<n]
        s=flux[j].mean()
        if s>bs: bs=s
    best.append((bs,bpm))
best.sort(reverse=True)
for s,b in best[:12]: print(f"   bpm {b:7.2f}  score {s:.4f}")
