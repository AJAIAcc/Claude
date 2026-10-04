#!/usr/bin/env python3
"""Runeglish language model: interpolated 5-gram over the 29-rune alphabet.

Replaces the 2,058-rune model built from the solved pages alone. That model was the
limiting factor in every detector here: it mangled words it had never seen (it decoded
SUFFERING as SUMFMOS), and on short pages it could not tell a fitted key from a real one.

Corpus: 2.34M runes of English transliterated into the Gematria Primus alphabet
(relikd/LiberPrayground `baseline-rune-stream.txt`), interpolated with the Liber Primus
plaintext itself so that the book's own vocabulary -- CIRCUMFERENCE, INSTAR, DIVINITY,
KWESTION -- is not treated as improbable.

Counts live in flat arrays indexed base-29, so a context is an integer and the
conditional distribution is a contiguous slice.
"""
import os, math, pickle
from array import array
import gp

N = 29
ORDER = 5
POW = [N**k for k in range(ORDER + 1)]

class Interp:
    """Jelinek-Mercer interpolated n-gram. P_k = lam*ML_k + (1-lam)*P_{k-1}."""
    def __init__(self, seq, order=ORDER, lam=0.75):
        self.order, self.lam = order, lam
        self.c = [None] + [array('i', bytes(4 * POW[k])) for k in range(1, order + 1)]
        for k in range(1, order + 1):
            ck = self.c[k]
            code = 0
            # rolling base-29 code of the last k symbols
            for i, x in enumerate(seq):
                code = (code * N + x) % POW[k]
                if i >= k - 1:
                    ck[code] += 1
        self.tot1 = sum(self.c[1])

    def ctx_total(self, k, ctxcode):
        """Number of times this (k-1)-length context was seen. Uses the lower-order
        table, which equals the sum over x of count_k(ctx+x) up to stream-edge effects."""
        if k == 1: return self.tot1
        return self.c[k - 1][ctxcode]

    def dist(self, ctx):
        """ctx: tuple of up to order-1 ints (may contain -1 padding). -> list of 29 probs."""
        ctx = tuple(x for x in ctx if x >= 0)
        ctx = ctx[-(self.order - 1):]
        p = [1.0 / N] * N
        for k in range(1, self.order + 1):
            need = k - 1
            if len(ctx) < need: break
            sub = ctx[len(ctx) - need:] if need else ()
            code = 0
            for y in sub: code = code * N + y
            tot = self.ctx_total(k, code)
            if tot <= 0: break
            base = code * N
            ck = self.c[k]; lam = self.lam
            inv = 1.0 / tot
            p = [lam * (ck[base + x] * inv) + (1 - lam) * p[x] for x in range(N)]
        return p


def load_corpus():
    src = os.environ.get("LP_SOURCES",
                         os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources"))
    path = os.path.join(src, "relikd", "data", "baseline-rune-stream.txt")
    txt = open(path, encoding="utf-8").read()
    return [gp.R2I[c] for c in txt if c in gp.R2I]


class Mixed:
    """Big English model mixed with the Liber Primus plaintext model."""
    def __init__(self, big, lp, w_lp=0.35):
        self.big, self.lp, self.w = big, lp, w_lp
        self._cache = {}
    def logdist(self, ctx):
        v = self._cache.get(ctx)
        if v is not None: return v
        a = self.big.dist(ctx); b = self.lp.dist(ctx)
        w = self.w
        v = [math.log((1 - w) * a[x] + w * b[x]) for x in range(N)]
        self._cache[ctx] = v
        return v
    def logp(self, seq):
        o = ORDER - 1
        ctx = tuple([-1] * o); tot = 0.0
        for x in seq:
            tot += self.logdist(ctx)[x]
            ctx = (ctx + (x,))[1:]
        return tot


_MODEL = None
def model():
    global _MODEL
    if _MODEL is None:
        import corpus as lpc
        big = Interp(load_corpus())
        lp = Interp(lpc.ALLIDX)
        _MODEL = Mixed(big, lp)
    return _MODEL


if __name__ == "__main__":
    import random, time
    t = time.time()
    M = model()
    print(f"built in {time.time()-t:.0f}s")
    import corpus as lpc
    random.seed(1)
    plain = lpc.ALLIDX[:400]
    rnd = [random.randrange(29) for _ in range(400)]
    print(f"  LP plaintext : {M.logp(plain)/len(plain):+.3f} / rune")
    print(f"  uniform noise: {M.logp(rnd)/len(rnd):+.3f} / rune")
