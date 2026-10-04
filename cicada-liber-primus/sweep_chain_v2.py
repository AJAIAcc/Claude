#!/usr/bin/env python3
"""Chain-form keyword/stream sweep under the 2.34M-rune model, with matched nulls.

sweep_chain.py did this with the 2,058-rune model, which is the model that made noise
look borderline (it flagged pg66 at -3.218 as a candidate; the new model scores that
same text -4.326). This repeats the chain-form sweep with the sharper detector AND,
for every page, runs the identical search against uniform random ciphertext of the
same length, so each page is judged against its own baseline instead of one global
threshold. Anything that beats its own null gets its plaintext printed.
"""
import random, time, sys
from multiprocessing import Pool
import gp, corpus, lm, chain2, keys as K

P = corpus.P
UNS = [15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,
       40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,
       66,67,68,69,70]
CAND = K.candidates()
WIDTH = 5

def best_chain(ct):
    n = len(ct); best, name = -99, ""
    for kn, k in CAND.items():
        for r in range(len(k)):
            kk = k[r:] + k[:r]
            for pre in ("id", "atbash"):
                c2 = gp.atbash(ct) if pre == "atbash" else ct
                s = chain2.decrypt_beam(c2, kk, width=WIDTH)[1] / n
                if s > best: best, name = s, f"{kn}r{r}/{pre}"
    return best, name

def work(i):
    rng = random.Random(9000 + i)
    ct = gp.idx_of(P[i]); n = len(ct)
    real, rname = best_chain(ct)
    null = max(best_chain([rng.randrange(29) for _ in range(n)])[0] for _ in range(2))
    return i, n, real, rname, null

if __name__ == "__main__":
    t0 = time.time()
    lm.model()
    print("CHAIN-FORM KEYWORD SWEEP — new model, per-page matched nulls\n")
    print(f"{'pg':>4} {'n':>5} {'real':>8} {'null':>8} {'verdict':>8}   key")
    flagged = []
    with Pool(2) as pool:
        for i, n, real, rname, null in pool.imap(work, UNS):
            v = "CHECK" if real > null + 0.10 else "noise"
            if v == "CHECK": flagged.append((i, real, null, rname))
            print(f"{i:>4} {n:>5} {real:8.3f} {null:8.3f} {v:>8}   {rname[:30]}", flush=True)
    print(f"\nflagged: {len(flagged)}")
    for i, real, null, rname in flagged:
        ct = gp.idx_of(P[i])
        k = CAND[rname.split('r')[0]] if rname.split('r')[0] in CAND else None
        print(f"  pg{i} real {real:+.3f} null {null:+.3f} key {rname}")
        if k:
            r = int(rname.split('r')[1].split('/')[0]); pre = rname.split('/')[1]
            kk = k[r:] + k[:r]
            c2 = gp.atbash(ct) if pre == "atbash" else ct
            dec = chain2.decrypt_beam(c2, kk, width=200)[0]
            print(f"    text: {gp.render(gp.structure(P[i]), dec)[:140].strip()}")
    print(f"\nreal LP plaintext scores about -0.90 under this model")
    print("VERDICT: chain-form keyword family excluded on every page."
          if not flagged else "VERDICT: inspect the flagged pages above.")
    print(f"({time.time()-t0:.0f}s)")
