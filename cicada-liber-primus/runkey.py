#!/usr/bin/env python3
"""Running-key search against candidate texts.

A flat, aperiodic, repeat-avoiding keystream is what a running key from some specific
text looks like. This slides each candidate text against each unsolved segment at EVERY
offset, in Vigenere, Beaufort and variant form, on plain and Atbash ciphertext.

Two stages, because a full 5-gram score at every offset is far too slow:
  screen   a vectorised trigram score over all offsets at once (numpy), ~n array ops
  rescore  the top offsets re-scored with the full 2.34M-rune 5-gram model

A positive control encrypts real Liber Primus plaintext with a known running key at a
known offset and checks the search recovers it, so a negative result means something.
"""
import os, sys, time
import numpy as np
import gp, corpus, lm

N = 29
SCREEN_TOP = 15          # offsets per (text, segment, mode) promoted to full rescoring
PROBE = 240              # runes of each segment used as the probe

# ---------------------------------------------------------------- candidate texts
def runeify(s):
    """English -> Gematria Primus indices, using the book's own conventions."""
    s = s.upper()
    out = []
    i = 0
    DIG = [("ING", 21), ("TH", 2), ("EO", 12), ("OE", 22), ("AE", 25), ("EA", 28),
           ("IA", 27), ("IO", 27), ("NG", 21)]
    SNG = {"F":0,"U":1,"V":1,"O":3,"R":4,"C":5,"K":5,"Q":5,"G":6,"W":7,"H":8,"N":9,
           "I":10,"J":11,"P":13,"X":14,"S":15,"Z":15,"T":16,"B":17,"E":18,"M":19,
           "L":20,"D":23,"A":24,"Y":26}
    while i < len(s):
        for d, v in DIG:
            if s.startswith(d, i):
                out.append(v); i += len(d); break
        else:
            c = s[i]
            if c in SNG: out.append(SNG[c])
            i += 1
    return out

def candidate_texts():
    texts = {}
    src = os.environ.get("LP_SOURCES",
                         os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources"))
    p = os.path.join(src, "relikd", "data", "baseline-rune-stream.txt")
    if os.path.exists(p):
        t = open(p, encoding="utf-8").read()
        texts["war-and-peace"] = [gp.R2I[c] for c in t if c in gp.R2I]
    try:
        from nltk.corpus import gutenberg, inaugural
        for f in gutenberg.fileids():
            texts["gb:" + f] = runeify(gutenberg.raw(f))
        texts["inaugural-all"] = runeify(inaugural.raw())
    except Exception as e:
        print("nltk corpora unavailable:", e, file=sys.stderr)
    texts["liber-primus-plaintext"] = list(corpus.ALLIDX)
    return texts

# ---------------------------------------------------------------- segments
SEGS = {7: range(15,18), 8: range(18,23), 9: range(23,30), 10: range(30,31),
        11: range(31,38), 12: range(38,42), 13: range(42,49), 14: range(49,55),
        15: list(range(55,65)) + [66,67,68,69,70]}
def segments():
    P = corpus.P
    return {k: sum([gp.idx_of(P[i]) for i in v], []) for k, v in SEGS.items()}

# ---------------------------------------------------------------- screening
def trigram_table():
    """log P(x3 | x1 x2) flattened to 29^3, from the big model."""
    M = lm.model()
    tab = np.full(N**3, -8.0, dtype=np.float32)
    for a in range(N):
        for b in range(N):
            d = M.logdist((-1, -1, a, b))
            base = (a*N + b)*N
            tab[base:base+N] = d
    return tab

def screen(C, K, mode, tab):
    """Vectorised trigram score of every offset. Returns float32 array of scores."""
    n = len(C); M = len(K) - n + 1
    if M <= 0: return None
    Kv = K
    # p[i] as a function of offset, for each i: shape (M,)
    def p_at(i):
        seg = Kv[i:i+M]
        if mode == "sub":  return (C[i] - seg) % N      # Vigenere
        if mode == "add":  return (C[i] + seg) % N      # variant
        return (seg - C[i]) % N                          # Beaufort
    sc = np.zeros(M, dtype=np.float32)
    p0 = p_at(0); p1 = p_at(1)
    for i in range(2, n):
        p2 = p_at(i)
        sc += tab[(p0.astype(np.int64)*N + p1)*N + p2]
        p0, p1 = p1, p2
    return sc / (n - 2)

def decrypt(C, K, off, mode):
    seg = K[off:off+len(C)]
    if mode == "sub": return [(c - k) % N for c, k in zip(C, seg)]
    if mode == "add": return [(c + k) % N for c, k in zip(C, seg)]
    return [(k - c) % N for c, k in zip(C, seg)]

# ---------------------------------------------------------------- control
def control(texts, tab):
    M = lm.model()
    key_name = "gb:bible-kjv.txt" if "gb:bible-kjv.txt" in texts else list(texts)[0]
    K = np.array(texts[key_name], dtype=np.int64)
    pt = corpus.ALLIDX[:PROBE]
    off = 50000 if len(K) > 50000 + PROBE else 10
    C = np.array([(p + int(K[off+i])) % N for i, p in enumerate(pt)], dtype=np.int64)
    sc = screen(C, K, "sub", tab)
    rank = int((sc > sc[off]).sum())
    best = int(np.argmax(sc))
    full = M.logp(decrypt(C, K, off, "sub")) / PROBE
    print("POSITIVE CONTROL")
    print(f"  key text {key_name}, true offset {off}")
    print(f"  screen put the true offset at rank {rank} of {len(sc)} (0 = top)")
    print(f"  argmax offset {best} ({'CORRECT' if best == off else 'wrong'})")
    print(f"  full-model score at the true offset: {full:+.3f}")
    print(f"  -> the search can find a running key when one is there\n")
    return rank == 0

# ---------------------------------------------------------------- main
if __name__ == "__main__":
    t0 = time.time()
    M = lm.model()
    print("building trigram screen table...", flush=True)
    tab = trigram_table()
    texts = candidate_texts()
    print(f"candidate texts: {len(texts)}")
    for k, v in texts.items(): print(f"  {k:28s} {len(v):>9,} runes")
    print()
    ok = control(texts, tab)
    if not ok:
        print("CONTROL FAILED - not reporting negatives"); sys.exit(1)

    segs = segments()
    results = []
    for sname, sv in sorted(segs.items()):
        probe_plain = np.array(sv[:PROBE], dtype=np.int64)
        probe_atb = np.array([(N-1-x) for x in sv[:PROBE]], dtype=np.int64)
        for pre, C in (("id", probe_plain), ("atbash", probe_atb)):
            for tname, tv in texts.items():
                K = np.array(tv, dtype=np.int64)
                for mode in ("sub", "add", "beaufort"):
                    sc = screen(C, K, mode, tab)
                    if sc is None: continue
                    top = np.argpartition(sc, -min(SCREEN_TOP, len(sc)))[-SCREEN_TOP:]
                    for off in top:
                        off = int(off)
                        dec = decrypt(list(C), tv, off, mode)
                        if len(dec) < PROBE: continue
                        full = M.logp(dec) / len(dec)
                        results.append((full, sname, pre, tname, mode, off))
        results.sort(reverse=True)
        results = results[:40]
        print(f"seg{sname:<3} done  best so far {results[0][0]:+.3f}  ({results[0][3]})", flush=True)

    print("\nTOP 15 RUNNING-KEY CANDIDATES (full 5-gram score)")
    for full, sname, pre, tname, mode, off in results[:15]:
        print(f"  {full:+.3f}  seg{sname} {pre:6s} {tname:24s} {mode:8s} off={off}")
    print("\nreference: real LP plaintext -0.90 ; uniform noise -4.84")
    print("VERDICT: no running key found." if results[0][0] < -3.0 else "VERDICT: INSPECT top hits.")
    print(f"({time.time()-t0:.0f}s)")
