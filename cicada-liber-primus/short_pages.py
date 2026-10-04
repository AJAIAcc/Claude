#!/usr/bin/env python3
"""Resolve the chain hill-climb's short-page flags with the new model.

The old-model chain climb ended "CANDIDATE - inspect" on the shortest pages
(pg64 n=66 at -2.715, pg66 n=92 at -2.790, pg37 n=131 at -2.985, ...). Those sit above
-3.0, so they cannot simply be waved away. This re-runs the climb on exactly those
pages with the 2.34M-rune model, AND measures the chain-form overfitting null at the
same lengths and key lengths, so each page is judged against its own baseline.
"""
import random, time
import gp, corpus, lm, chain2

M = lm.model()
PAGES = [64, 66, 47, 37, 29, 30, 21]
P = corpus.P

def score(ct, key): return chain2.decrypt_beam(ct, key, width=5)[1] / len(ct)

def climb(ct, L, restarts, rng):
    best = (-99, None)
    for _ in range(restarts):
        key = [rng.randrange(29) for _ in range(L)]
        cur = score(ct, key); imp = True
        while imp:
            imp = False
            for i in range(L):
                bv, bx = cur, key[i]
                for v in range(29):
                    key[i] = v
                    s = score(ct, key)
                    if s > bv: bv, bx = s, v
                key[i] = bx
                if bv > cur: cur, imp = bv, True
        if cur > best[0]: best = (cur, key[:])
    return best

if __name__ == "__main__":
    t = time.time()
    rng = random.Random(7)
    print("SHORT-PAGE RESOLUTION — chain hill-climb under the new model")
    print("each page against a null of the SAME length and key length\n")
    print(f"{'pg':>4} {'n':>5} {'L':>3} {'real':>8} {'null':>8} {'verdict':>10}")
    for i in PAGES:
        ct = gp.idx_of(P[i]); n = len(ct)
        for L in (7, 10):
            real, key = climb(ct, L, 4, rng)
            nulls = [climb([rng.randrange(29) for _ in range(n)], L, 4, rng)[0]
                     for _ in range(2)]
            nl = max(nulls)
            verdict = "NOISE" if real <= nl + 0.10 else "CHECK"
            print(f"{i:>4} {n:>5} {L:>3} {real:8.3f} {nl:8.3f} {verdict:>10}", flush=True)
            if verdict == "CHECK":
                dec = chain2.decrypt_beam(ct, key, width=200)[0]
                print(f"      text: {gp.render(gp.structure(P[i]), dec)[:100].strip()}")
    print(f"\nreal LP plaintext scores about -0.90 under this model")
    print(f"({time.time()-t:.0f}s)")
