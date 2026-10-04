"""Interrupter-aware beam decoder driven by the big Runeglish model (lm.py)."""
import gp, lm
N = 29

def beam(ct, key, width=200, interrupt=0, mode='sub'):
    M = lm.model(); O = lm.ORDER - 1
    L = len(key)
    beam = {(tuple([-1]*O), 0): (0.0, ())}
    for c in ct:
        nxt = {}
        for (ctx, kp), (sc, path) in beam.items():
            d = M.logdist(ctx)
            kv = key[kp % L]
            p = (c - kv) % N if mode == 'sub' else (c + kv) % N
            cands = [(p, kp+1)]
            if interrupt is not None and c == interrupt:
                cands.append((interrupt, kp))      # unencrypted plaintext F, key frozen
            for pp, nkp in cands:
                ns = sc + d[pp]; nctx = (ctx + (pp,))[1:]
                k2 = (nctx, nkp)
                e = nxt.get(k2)
                if e is None or e[0] < ns: nxt[k2] = (ns, path + (pp,))
        if len(nxt) > width:
            nxt = dict(sorted(nxt.items(), key=lambda kv: -kv[1][0])[:width])
        beam = nxt
    k, (sc, path) = max(beam.items(), key=lambda kv: kv[1][0])
    return list(path), sc
