#!/usr/bin/env python3
"""Keyword-specific null.

The unconstrained hill-climb null is the wrong baseline for the keyword search: a
search restricted to real dictionary words has far fewer degrees of freedom than a free
climb over all 29^L keys, so comparing the two understates how good a keyword hit has
to be. This runs the EXACT keyword search -- same 414 keys, same rotations, same
sub/add and plain/atbash -- against uniform random ciphertext of matched lengths, and
reports the best score it finds when there is provably nothing to find.
"""
import random, time, statistics as st
import gp, corpus, lm, decode2, keys as K

M = lm.model()
CAND = K.candidates()
NTRIALS = 3

def keyword_best(ct):
    n = len(ct); best, name = -99, ""
    for kn, k in CAND.items():
        for r in range(len(k)):
            kk = k[r:] + k[:r]
            for mode in ("sub", "add"):
                for pre in ("id", "atbash"):
                    c2 = gp.atbash(ct) if pre == "atbash" else ct
                    s = decode2.beam(c2, kk, width=6, mode=mode)[1] / n
                    if s > best: best, name = s, f"{kn}r{r}/{mode}/{pre}"
    return best, name

if __name__ == "__main__":
    t = time.time()
    rng = random.Random(2024)
    print("KEYWORD-SPECIFIC NULL")
    print("the same 414-key search, run on UNIFORM RANDOM ciphertext\n")
    print(f"{'n':>5} {'trial':>6} {'best':>8}   key")
    rows = {}
    for n in (92, 137, 262, 273):
        vals = []
        for t_i in range(NTRIALS):
            ct = [rng.randrange(29) for _ in range(n)]
            b, nm = keyword_best(ct)
            vals.append(b)
            print(f"{n:>5} {t_i:>6} {b:8.3f}   {nm}", flush=True)
        rows[n] = vals
    print("\nsummary")
    print(f"{'n':>5} {'mean':>8} {'max':>8}")
    for n, v in rows.items():
        print(f"{n:>5} {st.mean(v):8.3f} {max(v):8.3f}")
    print("\nA keyword hit on a real page must beat the max column to mean anything.")
    print("Reference: real LP plaintext scores about -0.90 under this model.")
    print(f"({time.time()-t:.0f}s)")
