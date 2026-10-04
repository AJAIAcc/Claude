#!/usr/bin/env python3
"""Running-key search with FULL coverage of every segment.

runkey/runkey2 probed only the first 240 runes of each of the nine segments: 2,160 of
12,956 runes, 17% of the text. Screen sensitivity (screen_sensitivity.log) shows the
detector needs about 60 contiguous keyed runes to rank the true offset first, so a
running key used anywhere outside those opening stretches was invisible to it. A
negative result on 17% of the text is not a negative result.

This tiles 240-rune probes across every segment end to end, so every rune is covered,
and runs them against the high-prior texts: the ten Cicada-canonical ones plus the
King James Bible and War and Peace. Streams: plain, Atbash, first difference (chain
form). Modes: Vigenere, variant, Beaufort.
"""
import os, sys, time
import numpy as np
import gp, corpus, lm, runkey, runkey2

N = 29
PROBE = 240
STRIDE = 240          # end-to-end tiling; probe >> the 60-rune detection floor
SCREEN_TOP = 8

HIGH_PRIOR = ("x:", "gb:bible-kjv.txt", "war-and-peace")

def chosen_texts():
    t = runkey.candidate_texts(); t.update(runkey2.extra_texts())
    return {k: v for k, v in t.items() if k.startswith("x:") or k in HIGH_PRIOR}

def tiles(seg):
    out = []
    i = 0
    while i < len(seg):
        chunk = seg[i:i+PROBE]
        if len(chunk) >= 80: out.append((i, chunk))
        i += STRIDE
    return out

def streams(chunk):
    plain = list(chunk)
    atb = [(N-1-x) for x in chunk]
    d = [(chunk[j]-chunk[j-1]) % N for j in range(1, len(chunk))]
    return {"plain": plain, "atbash": atb, "diff": d}

if __name__ == "__main__":
    t0 = time.time()
    M = lm.model()
    print("building screen table...", flush=True)
    tab = runkey.trigram_table()
    texts = chosen_texts()
    total = sum(len(v) for v in texts.values())
    print(f"texts: {len(texts)}  ({total:,} runes)")
    for k in texts: print("   ", k)
    if not runkey.control(texts, tab): sys.exit("control failed")

    segs = runkey.segments()
    ntiles = sum(len(tiles(v)) for v in segs.values())
    covered = sum(len(c) for v in segs.values() for _, c in tiles(v))
    print(f"tiles: {ntiles}, covering {covered:,} of {sum(len(v) for v in segs.values()):,} runes "
          f"({covered/sum(len(v) for v in segs.values())*100:.0f}%)\n", flush=True)

    results = []
    for sname, sv in sorted(segs.items()):
        for start, chunk in tiles(sv):
            for form, C in streams(chunk).items():
                Cv = np.array(C, dtype=np.int64)
                for tname, tv in texts.items():
                    K = np.array(tv, dtype=np.int64)
                    sc = runkey.screen(Cv, K, "sub", tab)
                    if sc is None: continue
                    for mode in ("sub", "add", "beaufort"):
                        s2 = sc if mode == "sub" else runkey.screen(Cv, K, mode, tab)
                        if s2 is None: continue
                        k = min(SCREEN_TOP, len(s2))
                        for off in np.argpartition(s2, -k)[-k:]:
                            off = int(off)
                            dec = runkey.decrypt(list(Cv), tv, off, mode)
                            if len(dec) < len(Cv): continue
                            results.append((M.logp(dec)/len(dec), sname, start, form,
                                            tname, mode, off))
            results.sort(reverse=True); results = results[:40]
        print(f"seg{sname:<3} done  best {results[0][0]:+.3f} "
              f"({results[0][3]}/{results[0][4]})", flush=True)

    print("\nTOP 20")
    for f, sname, start, form, tname, mode, off in results[:20]:
        print(f"  {f:+.3f} seg{sname:<3}@{start:<5} {form:7s} {tname:32s} {mode:9s} off={off}")
    best = results[0][0]
    print("\nreal LP plaintext -0.90 ; uniform noise -4.84")
    if best > -3.0:
        print("INSPECT:")
        f, sname, start, form, tname, mode, off = results[0]
        chunk = segs[sname][start:start+PROBE]
        dec = runkey.decrypt(streams(chunk)[form], texts[tname], off, mode)
        print("   ", gp.to_text(dec)[:300])
    else:
        print("VERDICT: no running key found, at full coverage, raw or chain form.")
    print(f"({time.time()-t0:.0f}s)")
