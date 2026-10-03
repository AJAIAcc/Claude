#!/usr/bin/env python3
"""Overlay timeline lyric cues on the vocal-salience curve so misalignment is visible."""
import numpy as np, json, subprocess, re
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
js=subprocess.run(["node","-e","""
const t=await import('./src/timeline.mjs');
console.log(JSON.stringify({sec:t.SECTIONS.map(s=>({id:s.id,t0:s.t0,t1:s.t1,n:s.lines.length})),
 lines:t.allLines().map(l=>({t:l.t,text:l.text}))}));
""","--input-type=module"],capture_output=True,text=True,cwd=".")
D=json.loads(js.stdout)
t,voc,vocH,sid=np.load("analysis/voc.npy")
sal=np.clip(voc*0.72+vocH*0.28-0.20*np.clip(sid,0,1.3),0,None)
k=np.hanning(13); k/=k.sum(); sal=np.convolve(sal,k,mode='same'); sal/=np.percentile(sal,97)
segs=[(0,46),(46,92),(92,138),(138,184),(184,222.5)]
fig,axes=plt.subplots(len(segs),1,figsize=(30,17))
for ax,(a,b) in zip(axes,segs):
    m=(t>=a)&(t<=b)
    ax.fill_between(t[m],0,sal[m],color="#d1006c",alpha=.40,lw=0)
    ax.plot(t[m],np.clip(sid,0,1.3)[m],color="#e8a000",lw=1.0,alpha=.75)
    for s in D["sec"]:
        if s["t1"]<a or s["t0"]>b: continue
        ax.axvspan(max(a,s["t0"]),min(b,s["t1"]),color="#0077b6",alpha=.055)
        ax.axvline(s["t0"],color="#0077b6",lw=1.6,alpha=.8)
        if s["t0"]>=a: ax.text(s["t0"]+0.1,1.30,s["id"],fontsize=8,color="#005b8c",rotation=0)
    for l in D["lines"]:
        if l["t"]<a or l["t"]>b: continue
        ax.axvline(l["t"],color="#111",lw=1.5,ls=(0,(3,2)))
        ax.text(l["t"]+0.08,0.04,l["text"][:26],fontsize=7.5,rotation=90,va="bottom",color="#111")
    ax.set_xlim(a,b); ax.set_ylim(0,1.45); ax.set_xticks(np.arange(a,b+.01,2))
    ax.grid(axis='x',alpha=.2)
axes[-1].set_xlabel("seconds — pink = lead-vocal salience, gold = band/sides, dashed = lyric cue")
plt.tight_layout(); plt.savefig("analysis/timing_check.png",dpi=62)
print("wrote analysis/timing_check.png")
