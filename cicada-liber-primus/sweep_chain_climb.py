#!/usr/bin/env python3
"""Hill-climb the key against the CHAIN (repeat-avoiding / key-skip) cipher.

The earlier hill-climb in solve.py assumed a plain Vigenere, which cannot track the
phase drift that skips introduce (~9 skips per page at a 3.4% collision rate is enough
to destroy a fixed-key fit). This climbs the key while scoring through the skip-aware
beam, so it is the strongest generic attack against the construction the doublet
fingerprint actually points at.
"""
import random, sys, time
from multiprocessing import Pool
import gp, corpus, chain

UNS = [15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,
       40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,
       66,67,68,69,70]
P = corpus.P
WIDTH = 5
LENGTHS = range(1, 11)
RESTARTS = 4

def score(ct, key):
    s = chain.decrypt_beam(ct, key, width=WIDTH)[1]
    return s / len(ct)

def climb(ct, L, restarts, rng):
    best = (-99, None)
    for _ in range(restarts):
        key = [rng.randrange(29) for _ in range(L)]
        cur = score(ct, key); improved = True
        while improved:
            improved = False
            for i in range(L):
                bv, bx = cur, key[i]
                for v in range(29):
                    key[i] = v
                    s = score(ct, key)
                    if s > bv: bv, bx = s, v
                key[i] = bx
                if bv > cur: cur, improved = bv, True
        if cur > best[0]: best = (cur, key[:])
    return best

def work(i):
    rng = random.Random(1000 + i)
    ct = gp.idx_of(P[i])
    rows = [(climb(ct, L, RESTARTS, rng)[0], L) for L in LENGTHS]
    rows.sort(reverse=True)
    return i, len(ct), rows[0][0], rows[0][1]

def control():
    rng = random.Random(77)
    pt = corpus.ALLIDX[:260]
    key = [rng.randrange(29) for _ in range(6)]
    ct = chain.encrypt(pt, key)
    v, k = climb(ct, 6, 6, rng)
    dec = chain.decrypt_beam(ct, k, width=60)[0]
    print("CONTROL: chain-encrypted real plaintext, random len-6 key")
    print(f"  recovered score {v:+.3f}  key match {k == key}  plaintext match {dec == pt}")
    print(f"  {gp.to_text(dec)[:64]}")
    print(f"  {gp.to_text(pt)[:64]}\n")
    return v

if __name__ == "__main__":
    t = time.time()
    cv = control()
    print(f"{'pg':>3} {'n':>5} {'best':>8} {'L':>3}")
    print("-"*26)
    out = []
    with Pool(2) as pool:
        for i, n, s, L in pool.imap(work, UNS):
            out.append((s, i, L))
            print(f"{i:>3} {n:>5} {s:8.3f} {L:>3}", flush=True)
    out.sort(reverse=True)
    print("\nBEST ACROSS ALL PAGES (chain hill-climb):")
    for s, i, L in out[:8]: print(f"  pg{i:<3} {s:+.3f} at L={L}")
    print(f"\ncontrol (true key on chain-encrypted plaintext): {cv:+.3f}")
    print("reference: correct -1.2 ; uniform noise -3.87")
    print("VERDICT: chain hill-climb excluded on every page."
          if out[0][0] < -3.0 else "VERDICT: CANDIDATE - inspect.")
    print(f"({time.time()-t:.0f}s)")
