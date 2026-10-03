#!/usr/bin/env python3
"""Segment the track into VOCAL-led vs BAND-led regions from centre/side dominance."""
import numpy as np, json
T=json.load(open("analysis/tempo.json")); BAR=T["bar"]; DB=T["downbeat"]
t,voc,vocH,sid=np.load("analysis/voc.npy")
dt=t[1]-t[0]
ctr=np.clip(voc*0.72+vocH*0.28,0,1.3)
sd =np.clip(sid,0,1.3)
def sm(a,sec):
    n=max(3,int(sec/dt)|1); k=np.hanning(n); k/=k.sum(); return np.convolve(a,k,mode='same')
c=sm(ctr,1.6); s=sm(sd,1.6)
score = (c-s)/(c+s+1e-6)           # +1 = pure centre(vocal), -1 = pure sides(band)
score = sm(score,2.2)
lab = score > 0.02
# enforce a minimum region length of 2 s, then snap edges to nearest bar line
runs=[];i=0;n=len(lab)
while i<n:
    j=i
    while j<n and lab[j]==lab[i]: j+=1
    runs.append([t[i],t[j-1],bool(lab[i])]); i=j
changed=True
while changed:
    changed=False
    for k,r in enumerate(runs):
        if r[1]-r[0]<2.0 and len(runs)>1:
            if k==0: runs[1][0]=r[0]
            elif k==len(runs)-1: runs[-2][1]=r[1]
            else:
                runs[k-1][1]=runs[k+1][0]=(r[0]+r[1])/2
            runs.pop(k); changed=True; break
# merge same-label neighbours
mg=[runs[0]]
for r in runs[1:]:
    if r[2]==mg[-1][2]: mg[-1][1]=r[1]
    else: mg.append(r)
print(f"{'kind':>6} {'start':>7} {'end':>7} {'dur':>6} {'bar':>6} -> {'bar':>6}")
for a,b,v in mg:
    print(f"{'VOCAL' if v else 'BAND':>6} {a:7.2f} {b:7.2f} {b-a:6.2f} {(a-DB)/BAR:6.2f} -> {(b-DB)/BAR:6.2f}")
print(f"\n{sum(1 for r in mg if r[2])} vocal regions, {sum(1 for r in mg if not r[2])} band regions")
json.dump([[round(a,2),round(b,2),v] for a,b,v in mg],open("analysis/regions.json","w"))
