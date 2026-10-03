#!/usr/bin/env python3
import subprocess, numpy as np, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
SR=22050
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
def sm(a,n=41):
    k=np.hanning(n); k/=k.sum(); return np.convolve(a,k,mode='same')
def nz(a): a=a-np.percentile(a,2); return np.clip(a/(np.percentile(a,98) or 1),0,1.3)

rms=nz(sm(np.sqrt((S.astype(np.float64)**2).mean(axis=0)),31))
sub=nz(sm(band(20,120)));  low=nz(sm(band(120,400)))
voc=nz(sm(band(250,1100))); hi=nz(sm(band(2000,5000))); air=nz(sm(band(6000,11000)))
cent=np.sum(S*fr[:,None],axis=0)/(np.sum(S,axis=0)+1e-9); cent=nz(sm(cent,61))
# spectral flatness in vocal band: low flatness => tonal (voice/solo)
m=(fr>=250)&(fr<2500); Sv=S[m]+1e-9
flat=np.exp(np.log(Sv).mean(axis=0))/Sv.mean(axis=0)
flat=nz(sm(flat,61))

segs=[(0,75),(75,150),(150,222.4)]
fig,axes=plt.subplots(len(segs),1,figsize=(26,13))
for ax,(a,b) in zip(axes,segs):
    m=(t>=a)&(t<=b)
    ax.plot(t[m],rms[m],label="RMS",lw=2.0,color="#111")
    ax.plot(t[m],voc[m],label="vocal band 250-1100",lw=1.5,color="#d1006c")
    ax.plot(t[m],hi[m],label="2-5k (clar/tpt/snare)",lw=1.2,color="#e8a000")
    ax.plot(t[m],sub[m],label="sub 20-120 (kick/bass)",lw=1.2,color="#0077b6")
    ax.plot(t[m],flat[m],label="flatness (low=tonal)",lw=1.2,color="#00916e",ls="--")
    ax.set_xlim(a,b); ax.set_ylim(0,1.35); ax.grid(alpha=.35,which='both')
    ax.set_xticks(np.arange(a,b+.1,5)); ax.set_xticks(np.arange(a,b+.1,1),minor=True)
    ax.grid(which='minor',alpha=.13)
    ax.legend(loc="upper right",fontsize=8,ncol=5)
    ax.set_ylabel("norm")
axes[-1].set_xlabel("seconds")
plt.tight_layout(); plt.savefig("analysis/features.png",dpi=72)
print("wrote analysis/features.png")
