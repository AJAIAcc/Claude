#!/usr/bin/env python3
import subprocess, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
SR=22050; BPM=170.0; PH=0.165
BAR=4*60.0/BPM
def decode(p):
    r=subprocess.run(["ffmpeg","-v","error","-i",p,"-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True)
    return np.frombuffer(r.stdout,dtype=np.float32).astype(np.float64)
x=decode("audio/track.mp3"); dur=len(x)/SR
nfft,hop=2048,256
win=np.hanning(nfft); nfr=1+(len(x)-nfft)//hop
S=np.empty((nfft//2+1,nfr),dtype=np.float32)
for i in range(nfr): S[:,i]=np.abs(np.fft.rfft(x[i*hop:i*hop+nfft]*win))
t=np.arange(nfr)*hop/SR; fr=np.fft.rfftfreq(nfft,1/SR)
def band(lo,hi):
    m=(fr>=lo)&(fr<hi); return S[m].mean(axis=0)
def sm(a,n): 
    k=np.hanning(n); k/=k.sum(); return np.convolve(a,k,mode='same')
def nz(a): a=a-np.percentile(a,2); return np.clip(a/(np.percentile(a,98) or 1),0,1.3)
rms=nz(sm(np.sqrt((S.astype(np.float64)**2).mean(axis=0)),25))
sub=nz(sm(band(20,120),25)); voc=nz(sm(band(250,1100),25)); hi=nz(sm(band(2000,5000),25))
segs=[(0,40),(40,80),(80,120),(120,160),(160,200),(200,222.4)]
fig,axes=plt.subplots(len(segs),1,figsize=(28,19))
for ax,(a,b) in zip(axes,segs):
    m=(t>=a)&(t<=b)
    ax.plot(t[m],rms[m],lw=2.2,color="#111",label="RMS")
    ax.plot(t[m],sub[m],lw=1.5,color="#0077b6",label="sub(kick)")
    ax.plot(t[m],voc[m],lw=1.6,color="#d1006c",label="vocal 250-1100")
    ax.plot(t[m],hi[m],lw=1.2,color="#e8a000",label="2-5k")
    k0=int(np.ceil((a-PH)/BAR)); k1=int((b-PH)/BAR)
    for k in range(k0,k1+1):
        tb=PH+k*BAR
        ax.axvline(tb,color="#888",lw=.6,alpha=.55)
        if k%4==0:
            ax.axvline(tb,color="#c00",lw=1.4,alpha=.8)
            ax.text(tb,1.28,f"{k}",fontsize=8,color="#c00",ha="center")
    ax.set_xlim(a,b); ax.set_ylim(0,1.35); ax.set_ylabel("norm")
    ax.legend(loc="lower right",fontsize=7,ncol=4)
    ax.set_xticks(np.arange(a,b+.01,2))
    ax.grid(axis='y',alpha=.25)
axes[-1].set_xlabel("seconds  (red = every 4 bars, grey = bar, bar=1.412s @170bpm)")
plt.tight_layout(); plt.savefig("analysis/bars.png",dpi=66)
print("wrote analysis/bars.png ; BAR=%.4f PH=%.3f total bars=%.1f"%(BAR,PH,(dur-PH)/BAR))
