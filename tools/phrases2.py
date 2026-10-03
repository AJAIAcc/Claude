#!/usr/bin/env python3
"""Adaptive vocal-phrase detection (local normalisation so loud band sections still resolve)."""
import numpy as np, json
BPM=170.0; PH=0.165; BAR=4*60.0/BPM; BEAT=60.0/BPM
t,voc,vocH,sid=np.load("analysis/voc.npy")
dt=t[1]-t[0]
sal = voc*0.70 + vocH*0.30 - 0.22*np.clip(sid,0,1.3)
sal = np.clip(sal,0,None)
k=np.hanning(11); k/=k.sum(); sal=np.convolve(sal,k,mode='same')
# local adaptive normalisation over a +-6s window
W=int(6.0/dt)
pad=np.pad(sal,(W,W),mode='edge')
loc=np.empty_like(sal)
cs=np.cumsum(pad)
for i in range(len(sal)):
    seg=pad[i:i+2*W]
    loc[i]=np.percentile(seg,75)
rel = sal/(loc+1e-6)
rel = np.convolve(rel,k,mode='same')
on = rel>0.92
ph=[];i=0;n=len(on)
while i<n:
    if on[i]:
        j=i
        while j<n and on[j]: j+=1
        if t[j-1]-t[i]>0.12: ph.append([t[i],t[j-1],float(rel[i:j].max())])
        i=j
    else: i+=1
mg=[]
for p in ph:
    if mg and p[0]-mg[-1][1]<0.30: mg[-1][1]=p[1]; mg[-1][2]=max(mg[-1][2],p[2])
    else: mg.append(p[:])
mg=[p for p in mg if p[1]-p[0]>0.25]
print(f"{len(mg)} phrases")
print(f"{'#':>3} {'start':>7} {'end':>7} {'dur':>5} {'bar':>7} {'gap':>5}")
prev=0
for i,(a,b,v) in enumerate(mg):
    print(f"{i:3d} {a:7.2f} {b:7.2f} {b-a:5.2f} {(a-PH)/BAR:7.2f} {a-prev:5.2f}")
    prev=b
json.dump([[round(a,3),round(b,3)] for a,b,_ in mg],open("analysis/phrases2.json","w"))
