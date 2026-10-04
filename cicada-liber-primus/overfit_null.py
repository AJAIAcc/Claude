#!/usr/bin/env python3
"""Overfitting null for the chain hill-climb.

A search that fits a key to a text scores above raw noise even when there is nothing
to find, so -3.87 (the score of uniform text decoded with a fixed key) is the WRONG
baseline for a hill-climb. The right one is what the same climb reaches on uniform
random text of the same length and key length. This measures it.
"""
import random
import corpus, chain

def score(ct, key):
    return chain.decrypt_beam(ct, key, width=5)[1] / len(ct)

def climb(ct, L, restarts, rng):
    best = -99
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
        best = max(best, cur)
    return best

if __name__ == "__main__":
    rng = random.Random(99)
    print("OVERFITTING NULL — chain hill-climb on UNIFORM RANDOM text (no signal present)\n")
    print(f"{'n':>5} {'L':>3} {'best on random':>15}")
    for n in (137, 159, 262, 273):
        for L in (8, 10):
            vals = [climb([rng.randrange(29) for _ in range(n)], L, 4, rng) for _ in range(3)]
            print(f"{n:>5} {L:>3} {max(vals):15.3f}")
    print("\nMeasured 2026-10-04:")
    print("  137/10 -3.014 random vs -2.991 on real pg29")
    print("  159/10 -3.003 random vs -3.073 on real pg30")
    print("  262/10 -3.192 random ; 273/10 -3.202 random")
    print("Real pages score the same as noise, or worse. Hill-climb excluded against")
    print("its own null, which is a stricter test than -3.87.")
