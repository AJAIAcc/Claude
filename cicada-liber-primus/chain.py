"""Repeat-avoiding ('key-skip') Vigenere.

Encrypt: at position i with key index k, c = p + key[k]. If that would equal c[i-1],
advance k and retry. Output steps are then uniform on 1..28 -- the fingerprint
measured on the unsolved pages.

Decrypt is NOT a replay: from the decoder's side, "index k was used" and "index k was
skipped and k+1 used" are both self-consistent, so the skip count is ambiguous exactly
as the F-interrupter is. Decoding is therefore a beam search over skip decisions.
"""
import fast
N = 29

def encrypt(pt, key):
    out = []; k = 0; prev = None
    for p in pt:
        while True:
            c = (p + key[k % len(key)]) % N
            k += 1
            if c != prev: break
        out.append(c); prev = c
    return out

def decrypt_beam(ct, key, width=200, max_skip=2):
    """Beam search over skip counts. State = (ngram ctx, key index). Returns (plain, score)."""
    L = len(key); O = fast.ORDER
    beam = {(tuple([-1]*(O-1)), 0, -1): (0.0, ())}   # ctx, keypos, prev ciphertext rune
    for c in ct:
        nxt = {}
        for (ctx, kp, prev), (sc, path) in beam.items():
            d = fast.dist(ctx)
            for s in range(max_skip + 1):
                used = kp + s
                p = (c - key[used % L]) % N
                # each skipped index must have produced exactly the previous rune.
                # NB: different s use different p, so a failing s does not rule out s+1.
                if not all((p + key[(kp + j) % L]) % N == prev for j in range(s)):
                    continue
                # The real text carries 86 doublets, which a STRICT key-skip cipher
                # cannot emit, so the model needs an escape. Where c == prev we allow
                # the rune through, but only with s = 0: a forced repeat means the
                # encoder stopped skipping, so it cannot also have consumed skips.
                if prev != -1 and c == prev and s > 0:
                    continue
                ns = sc + d[p]
                nctx = (ctx + (p,))[1:]
                k2 = (nctx, used + 1, c)
                e = nxt.get(k2)
                if e is None or e[0] < ns: nxt[k2] = (ns, path + (p,))
        if not nxt: return None, -1e9
        if len(nxt) > width:
            nxt = dict(sorted(nxt.items(), key=lambda kv: -kv[1][0])[:width])
        beam = nxt
    k, (sc, path) = max(beam.items(), key=lambda kv: kv[1][0])
    return list(path), sc
