#!/usr/bin/env python3
"""Center-channel (mid-side) vocal isolation -> vocal activity curve."""
import subprocess, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
SR=22050; BPM=170.0; PH=0.165; BAR=4*60.0/BPM
r=subprocess.run(["ffmpeg","-v","error","-i","audio/track.mp3","-ac","2","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True)
st=np.frombuffer(r.stdout,dtype=np.float32).astype(np.float64).reshape(-1,2)
L,R=st[:,0],st[:,1]; dur=len(L)/SR
nfft,hop=2048,256; win=np.hanning(nfft); nfr=1+(len(L)-nfft)//hop
FL=np.empty((nfft//2+1,nfr),dtype=np.complex64); FR=np.empty_like(FL)
for i in range(nfr):
    FL[:,i]=np.fft.rfft(L[i*hop:i*hop+nfft]*win); FR[:,i]=np.fft.rfft(R[i*hop:i*hop+nfft]*win)
fr=np.fft.rfftfreq(nfft,1/SR); t=np.arange(nfr)*hop/SR
aL,aR=np.abs(FL),np.abs(FR)
# coherence-weighted centre: bins where L~R in magnitude AND phase
denom=(aL+aR+1e-9)
bal=1-np.abs(aL-aR)/denom                     # 1 = perfectly centred
coh=np.real(FL*np.conj(FR))/(aL*aR+1e-9)      # phase coherence
centre=((aL+aR)/2)*np.clip(bal,0,1)*np.clip(coh,0,1)
side=np.abs(FL-FR)/2
def bnd(M,lo,hi):
    m=(fr>=lo)&(fr<hi); return M[m].mean(axis=0)
def sm(a,n):
    k=np.hanning(n); k/=k.sum(); return np.convolve(a,k,mode='same')
def nz(a):
    a=a-np.percentile(a,3); return np.clip(a/(np.percentile(a,97) or 1),0,1.3)
voc  = nz(sm(bnd(centre,220,1200),21))   # centred vocal fundamental+low formants
vocH = nz(sm(bnd(centre,1200,3500),21))  # centred consonants/upper formants
sid  = nz(sm(bnd(side,300,4000),21))     # wide: brass sections / solos / reverb
np.save("analysis/voc.npy",np.vstack([t,voc,vocH,sid]))
segs=[(0,40),(40,80),(80,120),(120,160),(160,200),(200,222.4)]
fig,axes=plt.subplots(len(segs),1,figsize=(28,19))
for ax,(a,b) in zip(axes,segs):
    m=(t>=a)&(t<=b)
    ax.fill_between(t[m],0,voc[m],color="#d1006c",alpha=.45,label="CENTRE 220-1200 (lead vocal)")
    ax.plot(t[m],vocH[m],lw=1.1,color="#7a0045",label="centre 1.2-3.5k")
    ax.plot(t[m],sid[m],lw=1.3,color="#e8a000",label="SIDE 300-4k (band/solos)")
    k0=int(np.ceil((a-PH)/BAR)); k1=int((b-PH)/BAR)
    for k in range(k0,k1+1):
        tb=PH+k*BAR
        ax.axvline(tb,color="#999",lw=.5,alpha=.5)
        if k%4==0:
            ax.axvline(tb,color="#c00",lw=1.3,alpha=.75)
            ax.text(tb,1.28,str(k),fontsize=8,color="#c00",ha="center")
    ax.set_xlim(a,b); ax.set_ylim(0,1.35); ax.set_xticks(np.arange(a,b+.01,2))
    ax.legend(loc="lower right",fontsize=7,ncol=3); ax.grid(axis='y',alpha=.25)
axes[-1].set_xlabel("seconds (red=every 4 bars)")
plt.tight_layout(); plt.savefig("analysis/vocal.png",dpi=66); print("wrote analysis/vocal.png")
