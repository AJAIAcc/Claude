"""Repeat-avoiding (key-skip) chain cipher, decoded with the 2.34M-rune model."""
import lm
N = 29

def encrypt(pt, key):
    out=[]; k=0; prev=None
    for p in pt:
        while True:
            c=(p+key[k%len(key)])%N; k+=1
            if c!=prev: break
        out.append(c); prev=c
    return out

def decrypt_beam(ct, key, width=60, max_skip=2):
    M=lm.model(); O=lm.ORDER-1; L=len(key)
    beam={(tuple([-1]*O),0,-1):(0.0,())}
    for c in ct:
        nxt={}
        for (ctx,kp,prev),(sc,path) in beam.items():
            d=M.logdist(ctx)
            for s in range(max_skip+1):
                used=kp+s; p=(c-key[used%L])%N
                if not all((p+key[(kp+j)%L])%N==prev for j in range(s)): continue
                if prev!=-1 and c==prev and s>0: continue
                ns=sc+d[p]; nctx=(ctx+(p,))[1:]; k2=(nctx,used+1,c)
                e=nxt.get(k2)
                if e is None or e[0]<ns: nxt[k2]=(ns,path+(p,))
        if not nxt: return None,-1e9
        if len(nxt)>width:
            nxt=dict(sorted(nxt.items(),key=lambda kv:-kv[1][0])[:width])
        beam=nxt
    k,(sc,path)=max(beam.items(),key=lambda kv:kv[1][0])
    return list(path),sc
