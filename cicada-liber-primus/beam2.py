"""Beam decoder supporting BOTH interrupter conventions.

mode 'emit' : a ciphertext F may be an unencrypted plaintext F; key does not advance.
mode 'drop' : a ciphertext F may be a pure interrupter; it is DISCARDED (contributes no
              plaintext letter) and the key does not advance.
mode 'both' : allow either at each F.
"""
import fast
N = 29

def decode(ct, key, width=200, mode='both', interrupt=0):
    L = len(key); O = fast.ORDER
    beam = {(tuple([-1]*(O-1)), 0): (0.0, ())}
    for c in ct:
        nxt = {}
        for (ctx, kp), (sc, path) in beam.items():
            d = fast.dist(ctx)
            p = (c - key[kp % L]) % N                     # ordinary decrypt
            cands = [(p, kp + 1, True)]
            if c == interrupt:
                if mode in ('emit', 'both'):  cands.append((interrupt, kp, True))
                if mode in ('drop', 'both'):  cands.append((None, kp, False))
            for pp, nkp, emit in cands:
                if emit:
                    ns = sc + d[pp]; nctx = (ctx + (pp,))[1:]; npath = path + (pp,)
                else:
                    ns = sc; nctx = ctx; npath = path + (-1,)   # -1 marks a dropped rune
                k2 = (nctx, nkp)
                e = nxt.get(k2)
                if e is None or e[0] < ns: nxt[k2] = (ns, npath)
        if len(nxt) > width:
            nxt = dict(sorted(nxt.items(), key=lambda kv: -kv[1][0])[:width])
        beam = nxt
    k, (sc, path) = max(beam.items(), key=lambda kv: kv[1][0])
    return list(path), sc
