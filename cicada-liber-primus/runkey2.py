#!/usr/bin/env python3
"""Running-key search, raw AND chain form.

runkey.py only tested running keys applied directly: c = p + k. But the doublet
fingerprint says the cipher is a chain, c[i] = c[i-1] + s[i]. If s[i] = p[i] + k[i]
with k a running key from some text, then

    d[i] = c[i] - c[i-1] = p[i] + k[i]    so    p[i] = d[i] - k[i]

i.e. chain-form decryption is the ordinary running-key search run on the FIRST
DIFFERENCE of the ciphertext. That costs nothing extra and was the obvious hole in the
previous search, so this version sweeps both forms.

Streams tested per segment: plain, Atbash, first difference, negated first difference.
Modes: Vigenere (c-k), variant (c+k), Beaufort (k-c).
"""
import os, sys, time, glob
import numpy as np
import gp, corpus, lm, runkey

N = 29
SCREEN_TOP = 12
PROBE = 240

def extra_texts():
    """Any .txt dropped into texts/ by the acquisition step."""
    out = {}
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "texts")
    for p in sorted(glob.glob(os.path.join(d, "*.txt"))):
        try:
            raw = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        v = runkey.runeify(raw)
        if len(v) > 2000:
            out["x:" + os.path.basename(p)[:-4]] = v
    return out

def streams_for(seg):
    plain = seg[:PROBE]
    atb = [(N-1-x) for x in seg[:PROBE]]
    d = [(seg[i] - seg[i-1]) % N for i in range(1, PROBE+1)]
    nd = [(-x) % N for x in d]
    return {"plain": plain, "atbash": atb, "diff": d, "negdiff": nd}

def chain_control(texts, tab):
    """Encrypt real plaintext in CHAIN form with a running key; the search must find it."""
    M = lm.model()
    kname = "gb:bible-kjv.txt" if "gb:bible-kjv.txt" in texts else list(texts)[0]
    K = texts[kname]
    off = 120000 if len(K) > 120000 + PROBE + 2 else 10
    pt = corpus.ALLIDX[:PROBE]
    # build chain ciphertext: c[i] = c[i-1] + (p[i] + k[i])
    c = [0];
    for i, p in enumerate(pt):
        c.append((c[-1] + p + K[off+i]) % N)
    ct = c[1:]
    d = [(ct[i] - ct[i-1]) % N for i in range(1, len(ct))]
    Ka = np.array(K, dtype=np.int64)
    sc = runkey.screen(np.array(d, dtype=np.int64), Ka, "sub", tab)
    true_off = off + 1
    rank = int((sc > sc[true_off]).sum())
    print("CHAIN-FORM POSITIVE CONTROL")
    print(f"  key {kname}, true offset {true_off}")
    print(f"  screen rank of the true offset: {rank} of {len(sc)}")
    print(f"  argmax {'CORRECT' if int(np.argmax(sc)) == true_off else 'wrong'}")
    ok = rank == 0
    print(f"  -> chain-form running keys are {'detectable' if ok else 'NOT detectable'}\n")
    return ok

if __name__ == "__main__":
    t0 = time.time()
    M = lm.model()
    print("building screen table...", flush=True)
    tab = runkey.trigram_table()
    texts = runkey.candidate_texts()
    texts.update(extra_texts())
    print(f"candidate texts: {len(texts)}  ({sum(len(v) for v in texts.values()):,} runes)")
    for k in texts: print("   ", k)
    print()
    if not runkey.control(texts, tab): sys.exit("raw control failed")
    if not chain_control(texts, tab):  sys.exit("chain control failed")

    segs = runkey.segments()
    results = []
    for sname, sv in sorted(segs.items()):
        for form, C in streams_for(sv).items():
            Cv = np.array(C, dtype=np.int64)
            for tname, tv in texts.items():
                K = np.array(tv, dtype=np.int64)
                for mode in ("sub", "add", "beaufort"):
                    sc = runkey.screen(Cv, K, mode, tab)
                    if sc is None: continue
                    k = min(SCREEN_TOP, len(sc))
                    for off in np.argpartition(sc, -k)[-k:]:
                        off = int(off)
                        dec = runkey.decrypt(list(Cv), tv, off, mode)
                        if len(dec) < len(Cv): continue
                        results.append((M.logp(dec)/len(dec), sname, form, tname, mode, off))
        results.sort(reverse=True); results = results[:40]
        print(f"seg{sname:<3} done   best {results[0][0]:+.3f}  "
              f"({results[0][2]}/{results[0][3]}/{results[0][4]})", flush=True)

    print("\nTOP 20 (full 5-gram score)")
    for full, sname, form, tname, mode, off in results[:20]:
        print(f"  {full:+.3f}  seg{sname:<3} {form:8s} {tname:26s} {mode:9s} off={off}")
    best = results[0][0]
    print("\nreal LP plaintext -0.90 ; uniform noise -4.84")
    if best > -3.0:
        print("INSPECT — printing the best decryption:")
        f, sname, form, tname, mode, off = results[0]
        dec = runkey.decrypt(list(np.array(streams_for(segs[sname])[form], dtype=np.int64)),
                             texts[tname], off, mode)
        print("   ", gp.to_text(dec)[:300])
    else:
        print("VERDICT: no running key found, raw or chain form.")
    print(f"({time.time()-t0:.0f}s)")
