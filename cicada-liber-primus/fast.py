import gp, corpus, math
M=corpus.MODEL; ORDER=M.order; N=29
_cache={}
def dist(ctx):
    """log-prob vector over next symbol given context tuple (len ORDER-1), with backoff."""
    v=_cache.get(ctx)
    if v is not None: return v
    out=[None]*N
    for k in range(ORDER,0,-1):
        c=ctx[ORDER-k:] if k>1 else ()
        den=sum(M.counts[k][c+(y,)] for y in range(N))
        if den>0:
            for x in range(N):
                if out[x] is None and M.counts[k][c+(x,)]>0:
                    out[x]=math.log((M.counts[k][c+(x,)]+M.alpha)/(den+M.alpha*N))
        if all(o is not None for o in out): break
    flo=math.log(1.0/N)-2.0
    out=[flo if o is None else o for o in out]
    _cache[ctx]=out
    return out

def beam_decode(ct, key, width=60, interrupt=0, mode='sub'):
    L=len(key)
    beam={(tuple([-1]*(ORDER-1)),0):(0.0,())}
    for c in ct:
        nxt={}
        for (ctx,kp),(sc,path) in beam.items():
            d=dist(ctx)
            kv=key[kp%L]
            p=(c-kv)%N if mode=='sub' else (c+kv)%N
            cand=[(p,kp+1)]
            if interrupt is not None and c==interrupt: cand.append((0,kp))
            for pp,nkp in cand:
                s=sc+d[pp]; nctx=(ctx+(pp,))[1:]; k=(nctx,nkp)
                e=nxt.get(k)
                if e is None or e[0]<s: nxt[k]=(s,path+(pp,))
        if len(nxt)>width:
            nxt=dict(sorted(nxt.items(), key=lambda kv:-kv[1][0])[:width])
        beam=nxt
    (ctx,kp),(sc,path)=max(beam.items(), key=lambda kv:kv[1][0])
    return list(path), sc

def plain_decode(ct,key,mode='sub'):
    L=len(key)
    return [((c-key[i%L])%N if mode=='sub' else (c+key[i%L])%N) for i,c in enumerate(ct)]
