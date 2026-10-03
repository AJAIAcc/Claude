#!/usr/bin/env python3
import subprocess, numpy as np
SR=22050; BPM=170.0; PH=0.165; BAR=4*60.0/BPM
r=subprocess.run(["ffmpeg","-v","error","-i","audio/track.mp3","-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True)
x=np.frombuffer(r.stdout,dtype=np.float32).astype(np.float64)
nfft,hop=2048,256; win=np.hanning(nfft); nfr=1+(len(x)-nfft)//hop
S=np.empty((nfft//2+1,nfr),dtype=np.float32)
for i in range(nfr): S[:,i]=np.abs(np.fft.rfft(x[i*hop:i*hop+nfft]*win))
fr=np.fft.rfftfreq(nfft,1/SR); t=np.arange(nfr)*hop/SR
def bnd(lo,hi):
    m=(fr>=lo)&(fr<hi); return S[m].mean(axis=0)
def sm(a,n):
    k=np.hanning(n); k/=k.sum(); return np.convolve(a,k,mode='same')
sub=sm(bnd(25,110),35); rms=sm(np.sqrt((S.astype(np.float64)**2).mean(axis=0)),35)
sub/=np.percentile(sub,97); rms/=np.percentile(rms,97)
def regions(mask,minlen):
    out=[];i=0;n=len(mask)
    while i<n:
        if mask[i]:
            j=i
            while j<n and mask[j]: j+=1
            if t[j-1]-t[i]>=minlen: out.append((t[i],t[j-1]))
            i=j
        else: i+=1
    return out
print("=== KICK/BASS ABSENT (sub < 0.17) for >=0.9s  -> breaks, half-time, intro ===")
for a,b in regions(sub<0.17,0.9):
    print(f"  {a:7.2f} -> {b:7.2f}  ({b-a:5.2f}s)   bars {(a-PH)/BAR:6.2f} -> {(b-PH)/BAR:6.2f}")
print("\n=== OVERALL DIP (rms < 0.33) for >=0.6s ===")
for a,b in regions(rms<0.33,0.6):
    print(f"  {a:7.2f} -> {b:7.2f}  ({b-a:5.2f}s)   bars {(a-PH)/BAR:6.2f} -> {(b-PH)/BAR:6.2f}")
