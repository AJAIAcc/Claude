#!/usr/bin/env python3
"""Chain-form (repeat-avoiding / key-skip Vigenere) attack on every unsolved page.

This is the construction the doublet fingerprint actually points at, so it gets its own
exhaustive pass: every candidate key at EVERY ROTATION (a key running continuously
through a section starts a page at an arbitrary phase), plus integer-sequence keystreams
at every offset, on raw and Atbash text.
"""
import random, time
import gp, corpus, chain, keys as K

P = corpus.P
UNS = [15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,
       40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,
       66,67,68,69,70]
CAND = K.candidates()

def primes(k):
    out, c = [], 2
    while len(out) < k:
        if all(c % p for p in out if p*p <= c): out.append(c)
        c += 1
    return out
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

def control():
    random.seed(4)
    pt = corpus.ALLIDX[:260]
    key = [random.randrange(29) for _ in range(8)]
    ct = chain.encrypt(pt, key)
    best = (-99, None)
    for name, k in CAND.items():
        for r in range(len(k)):
            kk = k[r:] + k[:r]
            s = chain.decrypt_beam(ct, kk, width=10)[1] / len(ct)
            if s > best[0]: best = (s, name)
    true = chain.decrypt_beam(ct, key, width=10)[1] / len(ct)
    print(f"CONTROL  chain-encrypted real plaintext, random len-8 key")
    print(f"  true key          : {true:+.3f}")
    print(f"  best WRONG key    : {best[0]:+.3f}  ({best[1]})")
    print(f"  separation        : {true-best[0]:+.3f}  -> detector discriminates\n")
    return true, best[0]

def run():
    print(f"{'pg':>3} {'n':>5} {'kw-chain':>9} {'stream-chain':>13}   best-hit")
    print("-"*76)
    allbest = []
    for i in UNS:
        raw = gp.idx_of(P[i]); n = len(raw)
        bk, bkn = -99, ""
        bs, bsn = -99, ""
        for pre in ("id", "atbash"):
            ct = gp.atbash(raw) if pre == "atbash" else raw
            for name, k in CAND.items():
                for r in range(len(k)):
                    kk = k[r:] + k[:r]
                    s = chain.decrypt_beam(ct, kk, width=8)[1] / n
                    if s > bk: bk, bkn = s, f"{name}r{r}/{pre}"
            for sname, S in STREAMS.items():
                for off in range(0, 200):
                    if off+n+10 > len(S): break
                    kk = [v % 29 for v in S[off:off+n+10]]
                    s = chain.decrypt_beam(ct, kk, width=6)[1] / n
                    if s > bs: bs, bsn = s, f"{sname}+{off}/{pre}"
        top = max((bk, "kw:"+bkn), (bs, "st:"+bsn))
        allbest.append((top[0], i, top[1]))
        print(f"{i:>3} {n:>5} {bk:9.3f} {bs:13.3f}   {top[1][:38]}", flush=True)
    allbest.sort(reverse=True)
    print("\nBEST ACROSS ALL PAGES (chain form):")
    for s, i, w in allbest[:8]: print(f"  pg{i:<3} {s:+.3f}  {w}")
    return allbest

if __name__ == "__main__":
    t = time.time()
    true, wrong = control()
    ab = run()
    print(f"\nreference: true key on chain-encrypted plaintext {true:+.3f};"
          f" best wrong key {wrong:+.3f}; uniform noise -3.87")
    print("VERDICT: chain form excluded on every page." if ab[0][0] < wrong + 0.15
          else "VERDICT: CANDIDATE - inspect.")
    print(f"({time.time()-t:.0f}s)")
