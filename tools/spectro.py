#!/usr/bin/env python3
import subprocess, numpy as np, sys
from scipy.ndimage import zoom
SR=22050
def decode(p):
    r=subprocess.run(["ffmpeg","-v","error","-i",p,"-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True)
    return np.frombuffer(r.stdout,dtype=np.float32).astype(np.float64)
x=decode("audio/track.mp3"); dur=len(x)/SR
t0=float(sys.argv[1]); t1=float(sys.argv[2]); outp=sys.argv[3]
x=x[int(t0*SR):int(t1*SR)]
nfft,hop=2048,512
win=np.hanning(nfft); nfr=1+(len(x)-nfft)//hop
S=np.empty((nfft//2+1,nfr))
for i in range(nfr): S[:,i]=np.abs(np.fft.rfft(x[i*hop:i*hop+nfft]*win))
freqs=np.fft.rfftfreq(nfft,1/SR)
m=freqs<=4000                      # focus on vocal/solo range
S=S[m]; f=freqs[m]
L=np.log1p(S*60)
L=(L-L.min())/(L.max()-L.min())
H,W=360,1800
img=zoom(L,(H/L.shape[0],W/L.shape[1]),order=1)
img=np.flipud(img)
img=np.clip(img,0,1)
# colourise: magma-ish
r=np.clip(img*2.6-0.3,0,1); g=np.clip(img*1.9-0.75,0,1); b=np.clip(img*1.5-0.1,0,1)*0.75+np.clip(img*3-0.05,0,1)*0.25
rgb=(np.dstack([r,g,b])*255).astype(np.uint8)
# gridlines every 5 s
for s in range(0,int(t1-t0)+1,5):
    xp=int(s/(t1-t0)*(W-1))
    rgb[:,xp,:]=np.maximum(rgb[:,xp,:],np.array([90,255,160],dtype=np.uint8))
for s in range(0,int(t1-t0)+1,10):
    xp=int(s/(t1-t0)*(W-1))
    rgb[:,max(0,xp-1):xp+2,:]=np.array([255,255,255],dtype=np.uint8)
from PIL import Image
Image.fromarray(rgb).save(outp)
print(f"{outp}  {t0}-{t1}s  white line every 10s, green every 5s, 0-4kHz")
