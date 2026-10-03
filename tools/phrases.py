#!/usr/bin/env python3
"""Detect sung vocal phrases from the centre channel; print bar-aligned table."""
import numpy as np, json
BPM=170.0; PH=0.165; BAR=4*60.0/BPM; BEAT=60.0/BPM
t,voc,vocH,sid=np.load("analysis/voc.npy")
# vocal salience: centre energy that is NOT explained by the wide band
sal = voc*0.65 + vocH*0.35
sal = sal - 0.42*np.clip(sid,0,1.3)
sal = np.clip(sal,0,None)
k=np.hanning(15); k/=k.sum(); sal=np.convolve(sal,k,mode='same')
sal=sal/ (np.percentile(sal,98) or 1)
THR=0.30
on = sal>THR
# group
ph=[]; i=0; n=len(on)
while i<n:
    if on[i]:
        j=i
        while j<n and on[j]: j+=1
        a,b=t[i],t[j-1]
        if b-a>0.16: ph.append([a,b,float(sal[i:j].max())])
        i=j
    else: i+=1
# merge phrases separated by < 0.33 s (within-line syllable gaps)
mg=[]
for p in ph:
    if mg and p[0]-mg[-1][1] < 0.33: mg[-1][1]=p[1]; mg[-1][2]=max(mg[-1][2],p[2])
    else: mg.append(p[:])
mg=[p for p in mg if p[1]-p[0]>0.30]
print(f"{len(mg)} vocal phrases\n")
print(f"{'#':>3} {'start':>7} {'end':>7} {'dur':>5} {'bar':>7} {'beat':>6}  peak   gap")
prev=0
for i,(a,b,v) in enumerate(mg):
    bar=(a-PH)/BAR; beat=(a-PH)/BEAT
    print(f"{i:3d} {a:7.2f} {b:7.2f} {b-a:5.2f} {bar:7.2f} {beat:6.1f}  {v:.2f}  {a-prev:5.2f}")
    prev=b
json.dump([[round(a,3),round(b,3)] for a,b,_ in mg],open("analysis/phrases.json","w"))
