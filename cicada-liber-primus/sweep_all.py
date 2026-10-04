#!/usr/bin/env python3
"""Run the exclusion battery against every unsolved page. Prints one row per page."""
import math, collections, sys
from math import gcd
import gp, corpus, fast, keys as K

P = corpus.P
UNS = [15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,
       40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,
       66,67,68,69,70]
MODEL = corpus.MODEL
CAND = K.candidates()

def primes(k):
    out, c = [], 2
    while len(out) < k:
        if all(c % p for p in out if p*p <= c): out.append(c)
        c += 1
    return out
PR = primes(1500)
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
while len(FIB) < 1500: FIB.append(FIB[-1]+FIB[-2])
STREAMS = {"phi(p)": [p-1 for p in PR], "primes": PR, "phi(n)": [phi(m) for m in range(1,1500)],
           "nat": list(range(1,1500)), "fib": FIB, "sq": [m*m for m in range(1,1500)],
           "tri": [m*(m+1)//2 for m in range(1,1500)]}

def attack(i):
    ct = gp.idx_of(P[i]); n = len(ct)
    # A. monoalphabetic
    a_best = max(MODEL.logp([(a*c+b) % 29 for c in ct])/n
                 for a in range(1,29) if gcd(a,29)==1 for b in range(29))
    # B. keyword vigenere
    b_best, b_name = -99, ""
    for name, k in CAND.items():
        for mode in ("sub","add"):
            for pre in ("id","atbash"):
                c2 = gp.atbash(ct) if pre=="atbash" else ct
                s = fast.beam_decode(c2, k, width=12, mode=mode)[1]/n
                if s > b_best: b_best, b_name = s, f"{name}/{mode}/{pre}"
    # C. integer streams
    c_best, c_name = -99, ""
    for sname, S in STREAMS.items():
        for off in range(0, 250):
            if off+n+5 > len(S): break
            key = [v % 29 for v in S[off:off+n+5]]
            for mode in ("sub","add"):
                s = fast.beam_decode(ct, key, width=6, mode=mode)[1]/n
                if s > c_best: c_best, c_name = s, f"{sname}+{off}/{mode}"
    return n, a_best, b_best, b_name, c_best, c_name

print(f"{'pg':>3} {'n':>5} {'mono':>7} {'keyword':>7} {'stream':>7}   best-hit")
print("-"*78)
worst = []
for i in UNS:
    n, a, b, bn, c, cn = attack(i)
    top = max((a,"mono"), (b,"kw:"+bn), (c,"st:"+cn))
    worst.append((top[0], i, top[1]))
    print(f"{i:>3} {n:>5} {a:7.3f} {b:7.3f} {c:7.3f}   {top[1][:44]}", flush=True)
worst.sort(reverse=True)
print("\nBEST SCORE ACROSS ALL PAGES AND ALL FAMILIES:")
for s,i,w in worst[:8]:
    print(f"  pg{i:<3} {s:+.3f}  {w}")
print("\nreference: correct plaintext -1.2 .. -2.2 ; uniform noise -3.87")
print("VERDICT: no page decrypts under any tested family." if worst[0][0] < -3.0
      else "VERDICT: CANDIDATE FOUND - inspect above.")
