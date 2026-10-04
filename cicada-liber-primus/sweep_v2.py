#!/usr/bin/env python3
"""Re-run the exclusion battery with the 2.34M-rune model (lm.py).

Everything in the first battery was scored by a 2,058-rune model. This repeats it with
a model whose correct-vs-noise separation is 3.95 instead of 2.65, and re-measures the
overfitting null, which is the baseline any searched key has to beat.
"""
import random, time, sys
from math import gcd
import gp, corpus, lm, decode2, keys as K

P = corpus.P
UNS = [15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,
       40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,
       66,67,68,69,70]
M = lm.model()
CAND = K.candidates()

def primes(k):
    o, c = [], 2
    while len(o) < k:
        if all(c % p for p in o if p*p <= c): o.append(c)
        c += 1
    return o
PR = primes(1200)
def phi(m):
    r, x, p = m, m, 2
    while p*p <= x:
        if x % p == 0:
            while x % p == 0: x //= p
            r -= r//p
        p += 1
    if x > 1: r -= r//x
    return r
FIB = [1,1]
while len(FIB) < 1200: FIB.append(FIB[-1]+FIB[-2])
STREAMS = {"phi(p)": [p-1 for p in PR], "primes": PR, "phi(n)": [phi(m) for m in range(1,1200)],
           "nat": list(range(1,1200)), "fib": FIB, "sq": [m*m for m in range(1,1200)],
           "tri": [m*(m+1)//2 for m in range(1,1200)]}

def plain_dec(ct, key, mode='sub'):
    L = len(key)
    return [((c-key[i%L]) % 29 if mode == 'sub' else (c+key[i%L]) % 29) for i, c in enumerate(ct)]

def references():
    random.seed(3)
    print("REFERENCES under the new model")
    print(f"  real LP plaintext : {M.logp(corpus.ALLIDX[:400])/400:+.3f}")
    print(f"  uniform noise     : {M.logp([random.randrange(29) for _ in range(400)])/400:+.3f}")
    # overfitting null: hill-climb a key against pure random text
    def climb(ct, L, restarts, rng):
        best = -99
        for _ in range(restarts):
            key = [rng.randrange(29) for _ in range(L)]
            cur = M.logp(plain_dec(ct, key))/len(ct); imp = True
            while imp:
                imp = False
                for i in range(L):
                    bv, bx = cur, key[i]
                    for v in range(29):
                        key[i] = v
                        s = M.logp(plain_dec(ct, key))/len(ct)
                        if s > bv: bv, bx = s, v
                    key[i] = bx
                    if bv > cur: cur, imp = bv, True
            best = max(best, cur)
        return best
    rng = random.Random(42)
    print("  overfitting null (hill-climb on UNIFORM RANDOM text):")
    out = {}
    for n in (92, 137, 262, 273):
        for L in (8, 12):
            v = max(climb([rng.randrange(29) for _ in range(n)], L, 3, rng) for _ in range(2))
            out[(n, L)] = v
            print(f"    n={n:3d} L={L:2d}  {v:+.3f}")
    return out

def attack(i):
    ct = gp.idx_of(P[i]); n = len(ct)
    a = max(M.logp([(x*c+b) % 29 for c in ct])/n
            for x in range(1, 29) if gcd(x, 29) == 1 for b in range(29))
    b_best, b_name = -99, ""
    for name, k in CAND.items():
        for r in range(len(k)):
            kk = k[r:] + k[:r]
            for mode in ("sub", "add"):
                for pre in ("id", "atbash"):
                    c2 = gp.atbash(ct) if pre == "atbash" else ct
                    s = decode2.beam(c2, kk, width=6, mode=mode)[1]/n
                    if s > b_best: b_best, b_name = s, f"{name}r{r}/{mode}/{pre}"
    c_best, c_name = -99, ""
    for sname, S in STREAMS.items():
        for off in range(0, 200):
            if off+n+5 > len(S): break
            key = [v % 29 for v in S[off:off+n+5]]
            for mode in ("sub", "add"):
                s = decode2.beam(ct, key, width=4, mode=mode)[1]/n
                if s > c_best: c_best, c_name = s, f"{sname}+{off}/{mode}"
    return n, a, b_best, b_name, c_best, c_name

if __name__ == "__main__":
    t = time.time()
    null = references()
    print(f"\n{'pg':>3} {'n':>5} {'mono':>7} {'keyword':>7} {'stream':>7}   best-hit")
    print("-"*78)
    rows = []
    for i in UNS:
        n, a, b, bn, c, cn = attack(i)
        top = max((a, "mono"), (b, "kw:"+bn), (c, "st:"+cn))
        rows.append((top[0], i, n, top[1]))
        print(f"{i:>3} {n:>5} {a:7.3f} {b:7.3f} {c:7.3f}   {top[1][:42]}", flush=True)
    rows.sort(reverse=True)
    print("\nBEST ACROSS ALL PAGES (new model):")
    for s, i, n, w in rows[:8]:
        print(f"  pg{i:<3} n={n:<4} {s:+.3f}  {w}")
    print(f"\nreal plaintext ~ -0.90 ; uniform noise ~ -4.84 ; overfitting null ~ {min(null.values()):+.2f}..{max(null.values()):+.2f}")
    print(f"({time.time()-t:.0f}s)")
