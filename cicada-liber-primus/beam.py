import gp, corpus, math, heapq

M = corpus.MODEL
ORDER = M.order

def _lp(ctx, x):
    o=ORDER
    for k in range(o,0,-1):
        c=ctx[o-k:] if k>1 else ()
        num=M.counts[k][c+(x,)]
        if k>1:
            den=sum(M.counts[k][c+(y,)] for y in range(29))
        else:
            den=M.tot[1]
        if den>0 and num>0:
            return math.log((num+M.alpha)/(den+M.alpha*29))
    return math.log(1.0/29)-2.0

def beam_decode(ct, key, width=400, interrupt=0, mode='sub'):
    """ct: ciphertext indices. key: list of key indices.
    Branch at every ciphertext rune == interrupt: either normal decrypt, or
    pass-through as plaintext F with the key NOT advancing."""
    L=len(key)
    # state: (score, tuple(last ORDER-1 plain), keypos, path_tuple)
    init=(0.0, tuple([-1]*(ORDER-1)), 0, ())
    beam=[init]
    for c in ct:
        nxt={}
        for sc, ctx, kp, path in beam:
            opts=[]
            kv=key[kp%L]
            p=(c-kv)%29 if mode=='sub' else (c+kv)%29
            opts.append((p, (kp+1)))
            if interrupt is not None and c==interrupt:
                opts.append((0, kp))         # plaintext F, key frozen
            for p,nkp in opts:
                s=sc+_lp(ctx,p)
                nctx=(ctx+(p,))[1:]
                k=(nctx,nkp)
                if k not in nxt or nxt[k][0]<s:
                    nxt[k]=(s,nctx,nkp,path+(p,))
        beam=sorted(nxt.values(), key=lambda t:-t[0])[:width]
    best=max(beam,key=lambda t:t[0])
    return best[3], best[0]
