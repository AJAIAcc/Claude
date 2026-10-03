#!/usr/bin/env python3
import subprocess, numpy as np, json
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
SR=22050
r=subprocess.run(["ffmpeg","-v","error","-i","audio/track.mp3","-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True)
x=np.frombuffer(r.stdout,dtype=np.float32).astype(np.float64)
nfft,hop=1024,128; win=np.hanning(nfft); nfr=1+(len(x)-nfft)//hop
S=np.empty((nfft//2+1,nfr),dtype=np.float32)
for i in range(nfr): S[:,i]=np.abs(np.fft.rfft(x[i*hop:i*hop+nfft]*win))
fps=SR/hop; L=np.log1p(S*8)
flux=np.sum(np.maximum(np.diff(L,axis=1,prepend=L[:,:1]),0),axis=0)
flux-=np.convolve(flux,np.ones(int(fps*0.4))/int(fps*0.4),mode='same')
flux=np.clip(flux,0,None); flux/=flux.std()
n=len(flux); dur=n/fps
best=(0,0,0)
for bpm in np.arange(98.0,101.0,0.01):
    per=60.0/bpm; step=per*fps
    npulse=int(n/step); idx=np.arange(npulse)*step
    for ph in np.arange(0,step,step/40):
        j=(idx+ph).astype(int); j=j[j<n]
        s=flux[j].mean()
        if s>best[0]: best=(s,bpm,ph/fps)
score,BPM,PHS=best
BEAT=60.0/BPM; BAR=4*BEAT
print(f"REFINED  bpm={BPM:.3f}  beat={BEAT:.4f}s  bar={BAR:.4f}s  phase={PHS:.4f}s  score={score:.4f}")
print(f"total bars = {(dur-PHS)/BAR:.2f}")
# downbeat: pick phase among 4 beat offsets maximising low-band energy (kick on 1)
m=(np.fft.rfftfreq(nfft,1/SR)<120)
subE=S[m].mean(axis=0)
cand=[]
for o in range(4):
    tb=PHS+o*BEAT
    idx=((np.arange(int((dur-tb)/BAR))*BAR+tb)*fps).astype(int); idx=idx[idx<n]
    cand.append((subE[idx].mean(),o))
cand.sort(reverse=True)
DB=PHS+cand[0][1]*BEAT
print(f"downbeat offset = beat {cand[0][1]}  -> first downbeat {DB:.4f}s")
json.dump({"bpm":BPM,"beat":BEAT,"bar":BAR,"beatPhase":PHS,"downbeat":DB,"duration":dur},
          open("analysis/tempo.json","w"),indent=1)
# zoom plot over verse 1 with beat lines
t,voc,vocH,sid=np.load("analysis/voc.npy")
sal=np.clip(voc*0.7+vocH*0.3-0.22*np.clip(sid,0,1.3),0,None)
k=np.hanning(11);k/=k.sum();sal=np.convolve(sal,k,mode='same')
segs=[(13,33),(33,53),(53,73)]
fig,axes=plt.subplots(3,1,figsize=(26,10))
for ax,(a,b) in zip(axes,segs):
    m2=(t>=a)&(t<=b)
    ax.fill_between(t[m2],0,sal[m2],color="#d1006c",alpha=.5)
    ax.plot(t[m2],sid[m2],color="#e8a000",lw=1.1)
    kk=0
    while DB+kk*BEAT < b:
        tb=DB+kk*BEAT
        if tb>=a:
            isdb = (kk%4==0)
            ax.axvline(tb,color=("#c00" if isdb else "#999"),lw=(1.5 if isdb else .6),alpha=(.85 if isdb else .5))
            if isdb: ax.text(tb,1.02,str(kk//4),fontsize=7,color="#c00",ha="center")
        kk+=1
    ax.set_xlim(a,b);ax.set_ylim(0,1.1);ax.set_xticks(np.arange(a,b+.01,1))
plt.tight_layout();plt.savefig("analysis/beatzoom.png",dpi=74);print("wrote analysis/beatzoom.png")
