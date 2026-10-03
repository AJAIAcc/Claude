#!/usr/bin/env python3
"""Per-frame animation drive data: band energies, vocal salience (mouth), beat grid."""
import numpy as np, json, subprocess
SR=22050; FPS=30.0
T=json.load(open("analysis/tempo.json"))
BPM,BEAT,BAR,DB=T["bpm"],T["beat"],T["bar"],T["downbeat"]
r=subprocess.run(["ffmpeg","-v","error","-i","audio/track.mp3","-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True)
x=np.frombuffer(r.stdout,dtype=np.float32).astype(np.float64); dur=len(x)/SR
nfft,hop=2048,256; win=np.hanning(nfft); nfr=1+(len(x)-nfft)//hop
S=np.empty((nfft//2+1,nfr),dtype=np.float32)
for i in range(nfr): S[:,i]=np.abs(np.fft.rfft(x[i*hop:i*hop+nfft]*win))
fr=np.fft.rfftfreq(nfft,1/SR); ts=np.arange(nfr)*hop/SR
N=int(dur*FPS); ft=np.arange(N)/FPS
def bnd(lo,hi):
    m=(fr>=lo)&(fr<hi); return np.interp(ft,ts,S[m].mean(axis=0))
def nz(a,p=97):
    a=a-np.percentile(a,2); return np.clip(a/(np.percentile(a,p) or 1),0,1.6)
bands={"sub":nz(bnd(20,120)),"low":nz(bnd(120,400)),"mid":nz(bnd(400,2000)),
       "high":nz(bnd(2000,6000)),"air":nz(bnd(6000,11000)),
       "rms":nz(np.interp(ft,ts,np.sqrt((S.astype(np.float64)**2).mean(axis=0))))}
# vocal salience -> mouth
tv,voc,vocH,sid=np.load("analysis/voc.npy")
sal=np.clip(voc*0.72+vocH*0.28-0.20*np.clip(sid,0,1.3),0,None)
k=np.hanning(9); k/=k.sum(); sal=np.convolve(sal,k,mode='same')
sal=np.interp(ft,tv,sal); sal=nz(sal,95)
# onset flux for hit detection
L=np.log1p(S*8); fl=np.sum(np.maximum(np.diff(L,axis=1,prepend=L[:,:1]),0),axis=0)
fl=np.interp(ft,ts,fl); fl=nz(fl,98)
beats=[]; kk=0
while DB+kk*BEAT<dur:
    if DB+kk*BEAT>=0: beats.append(round(DB+kk*BEAT,4))
    kk+=1
out={"fps":FPS,"frames":N,"duration":dur,"bpm":BPM,"beat":BEAT,"bar":BAR,"downbeat":DB,
     "beats":beats,
     "bands":{k:[round(float(v),4) for v in a] for k,a in bands.items()},
     "vocal":[round(float(v),4) for v in sal],
     "flux":[round(float(v),4) for v in fl]}
json.dump(out,open("analysis/drive.json","w"))
print(f"frames={N} beats={len(beats)} -> analysis/drive.json ({len(json.dumps(out))//1024}KB)")
