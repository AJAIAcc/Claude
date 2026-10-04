#!/usr/bin/env python3
"""Expanded number-theoretic keystream search, at full tiled coverage.

The book names its own key material: "THE PRIMES ARE SACRED. THE TOTIENT FUNCTION IS
SACRED." The one solved running-key page uses phi(p_n) = p_n - 1. The earlier battery
tested seven sequences; this tests roughly sixty, in raw and chain form, at every
offset, against every 240-rune tile of every unsolved segment.

This is cheap where the book search is not: a sequence of 40,000 terms is tiny beside
32M runes of candidate texts, so full coverage costs minutes rather than hours.
"""
import time, sys
import numpy as np
import gp, corpus, lm, runkey

N = 29
NTERMS = 20000
PROBE = 240
SCREEN_TOP = 10

# ---------------------------------------------------------------- sequences
def sieve(limit):
    s = np.ones(limit, dtype=bool); s[:2] = False
    for i in range(2, int(limit**0.5)+1):
        if s[i]: s[i*i::i] = False
    return np.nonzero(s)[0]

PRIMES = sieve(1200000)

def phi_sieve(n):
    ph = np.arange(n, dtype=np.int64)
    for p in range(2, n):
        if ph[p] == p:                      # p prime
            ph[p::p] -= ph[p::p] // p
    return ph

def divisor_counts(n):
    d = np.zeros(n, dtype=np.int64)
    for i in range(1, n):
        d[i::i] += 1
    return d

def divisor_sums(n):
    s = np.zeros(n, dtype=np.int64)
    for i in range(1, n):
        s[i::i] += i
    return s

def omega_counts(n, distinct=True):
    w = np.zeros(n, dtype=np.int64)
    for p in sieve(n):
        if distinct:
            w[p::p] += 1
        else:
            q = p
            while q < n:
                w[q::q] += 1
                q *= p
    return w

def digits_of(kind, count):
    from decimal import Decimal, getcontext
    getcontext().prec = count + 50
    if kind == "sqrt2": v = Decimal(2).sqrt()
    elif kind == "sqrt3": v = Decimal(3).sqrt()
    elif kind == "phi":   v = (1 + Decimal(5).sqrt()) / 2
    elif kind == "e":
        v = Decimal(0); f = Decimal(1)
        for k in range(1, count//2 + 60):
            f *= k; v += Decimal(1)/f
        v += 1
    elif kind == "pi":
        # Chudnovsky
        getcontext().prec = count + 60
        C = 426880 * Decimal(10005).sqrt()
        M, L, X, S = 1, 13591409, 1, Decimal(13591409)
        for k in range(1, count//13 + 30):
            M = M * (6*k-5)*(2*k-1)*(6*k-1) // (k*k*k)
            L += 545140134; X *= -262537412640768000
            S += Decimal(M*L)/X
        v = C / S
    s = str(v).replace(".", "").replace("-", "")
    return [int(c) for c in s[:count] if c.isdigit()]

def build():
    n = NTERMS
    seqs = {}
    P = PRIMES[:n]
    seqs["primes"] = P
    seqs["phi(p)=p-1"] = P - 1
    seqs["(p-1)/2"] = (P - 1)//2
    seqs["p+1"] = P + 1
    seqs["prime_gaps"] = np.diff(PRIMES[:n+1])
    seqs["p_n mod 29"] = P % 29
    seqs["2p+1"] = 2*P + 1
    seqs["p^2"] = (P.astype(np.int64)**2) % N

    M = n + 2
    ph = phi_sieve(M)
    seqs["phi(n)"] = ph[1:n+1]
    seqs["phi(phi(n))"] = ph[ph[1:n+1] % M]
    seqs["n-phi(n)"] = np.arange(1, n+1) - ph[1:n+1]
    dc = divisor_counts(M); ds = divisor_sums(M)
    seqs["d(n) divisors"] = dc[1:n+1]
    seqs["sigma(n)"] = ds[1:n+1]
    seqs["sigma(n)-n"] = ds[1:n+1] - np.arange(1, n+1)
    seqs["omega(n) distinct"] = omega_counts(M, True)[1:n+1]
    seqs["Omega(n) with mult"] = omega_counts(M, False)[1:n+1]
    w = omega_counts(M, False)[1:n+1]
    wd = omega_counts(M, True)[1:n+1]
    seqs["liouville"] = ((-1)**w) % N
    mob = np.where(w == wd, (-1)**wd, 0)
    seqs["mobius"] = mob % N
    seqs["squarefree"] = (w == wd).astype(np.int64)
    pi_n = np.zeros(M, dtype=np.int64)
    pi_n[PRIMES[PRIMES < M]] = 1
    seqs["pi(n) prime count"] = np.cumsum(pi_n)[1:n+1]

    seqs["naturals"] = np.arange(1, n+1)
    seqs["squares"] = (np.arange(1, n+1, dtype=np.int64)**2) % N
    seqs["cubes"] = (np.arange(1, n+1, dtype=np.int64)**3) % N
    seqs["triangular"] = (np.arange(1, n+1, dtype=np.int64)*(np.arange(2, n+2))//2) % N
    seqs["digit_sum(n)"] = np.array([sum(int(c) for c in str(i)) for i in range(1, n+1)])

    def rec(a, b):
        out = [a, b]
        while len(out) < n: out.append((out[-1]+out[-2]) % N)
        return np.array(out)
    seqs["fibonacci"] = rec(1, 1)
    seqs["lucas"] = rec(2, 1)
    pell = [0, 1]
    while len(pell) < n: pell.append((2*pell[-1]+pell[-2]) % N)
    seqs["pell"] = np.array(pell)
    pad = [1, 1, 1]
    while len(pad) < n: pad.append((pad[-2]+pad[-3]) % N)
    seqs["padovan"] = np.array(pad)
    tri = [0, 0, 1]
    while len(tri) < n: tri.append((tri[-1]+tri[-2]+tri[-3]) % N)
    seqs["tribonacci"] = np.array(tri)

    CAP = 4000      # these are O(n^2) or big-integer; 4000 offsets is ample for a 240-rune probe
    cat = [1]
    for k in range(1, CAP): cat.append(cat[-1]*2*(2*k-1)//(k+1))
    seqs["catalan"] = np.array([c % N for c in cat], dtype=np.int64)
    fac = [1]
    for k in range(1, n): fac.append(fac[-1]*k % N)
    seqs["factorial mod29"] = np.array(fac)
    pw = [1]
    for k in range(1, n): pw.append(pw[-1]*2 % N)
    seqs["2^n mod29"] = np.array(pw)
    prim = [1]
    for p in PRIMES[:n]: prim.append(prim[-1]*int(p) % N)
    seqs["primorial mod29"] = np.array(prim[:n])

    part = [1]+[0]*CAP
    for k in range(1, CAP+1):
        for j in range(k, CAP+1): part[j] = (part[j]+part[j-k]) % N
    seqs["partitions"] = np.array(part[:CAP])

    tm = [0]
    while len(tm) < n: tm += [1-x for x in tm]
    seqs["thue-morse"] = np.array(tm[:n])
    seen, rc, cur = {0}, [0], 0
    for k in range(1, n):
        c = cur - k
        if c < 0 or c in seen: c = cur + k
        seen.add(c); rc.append(c % N); cur = c
    seqs["recaman"] = np.array(rc)

    for kind in ("pi", "e", "sqrt2", "sqrt3", "phi"):
        try: seqs["digits_" + kind] = np.array(digits_of(kind, min(n, 8000)))
        except Exception as ex: print("  (skip digits", kind, ex, ")", file=sys.stderr)

    out = {}
    for k, v in seqs.items():
        a = np.asarray(v, dtype=np.int64) % N
        if len(a) >= 2000:
            out[k] = a
            out[k + " [rev]"] = a[::-1].copy()
    return out

def tiles(seg):
    out, i = [], 0
    while i < len(seg):
        c = seg[i:i+PROBE]
        if len(c) >= 80: out.append((i, c))
        i += PROBE
    return out

def streams(chunk):
    return {"plain": list(chunk),
            "atbash": [(N-1-x) for x in chunk],
            "diff": [(chunk[j]-chunk[j-1]) % N for j in range(1, len(chunk))]}

WIN = 60          # the screen's detection floor, from screen_sensitivity.log

def window_score(dec, M):
    """Best mean log-prob over any WIN-rune window.

    Calibration: on the SOLVED page 71, with its own correct key phi(p_n)=p_n-1, the
    whole-probe score is only -3.192, because the page carries an F-interrupter the
    screen does not model and the tail garbles ("IT IS THE DUTY OOE TAX"). A flat
    -3.0 threshold would therefore have REJECTED a known correct solve. Scoring the
    best window instead recovers the readable stretch and survives a garbled tail.
    """
    if len(dec) < WIN: return M.logp(dec) / max(len(dec), 1)
    lp = []
    o = lm.ORDER - 1
    ctx = tuple([-1] * o)
    for x in dec:
        lp.append(M.logdist(ctx)[x]); ctx = (ctx + (x,))[1:]
    run = sum(lp[:WIN]); best = run
    for i in range(WIN, len(lp)):
        run += lp[i] - lp[i - WIN]
        if run > best: best = run
    return best / WIN

CKPT = "seqkey_done.jsonl"

def load_done():
    import json, os
    done = {}
    if os.path.exists(CKPT):
        for line in open(CKPT):
            try:
                r = json.loads(line); done[r["seq"]] = r
            except Exception: pass
    return done

if __name__ == "__main__":
    import json
    t0 = time.time()
    M = lm.model()
    print("building screen table + sequences...", flush=True)
    tab = runkey.trigram_table()
    seqs = build()
    print(f"sequences: {len(seqs)}")
    segs = runkey.segments()
    all_tiles = [(sn, st, ch) for sn, sv in sorted(segs.items()) for st, ch in tiles(sv)]
    cov = sum(len(c) for _, _, c in all_tiles)
    print(f"tiles: {len(all_tiles)} covering {cov:,} runes\n", flush=True)

    done = load_done()
    results = [tuple(r["best"]) for r in done.values() if r.get("best")]
    print(f"resuming: {len(done)} sequences already done\n", flush=True)
    ck = open(CKPT, "a")
    for i, (sname, sv) in enumerate(sorted(seqs.items()), 1):
        if sname in done: continue
        K = sv
        best = (-99,)
        for tsn, start, chunk in all_tiles:
            for form, C in streams(chunk).items():
                Cv = np.array(C, dtype=np.int64)
                for mode in ("sub", "add", "beaufort"):
                    sc = runkey.screen(Cv, K, mode, tab)
                    if sc is None: continue
                    k = min(SCREEN_TOP, len(sc))
                    for off in np.argpartition(sc, -k)[-k:]:
                        off = int(off)
                        dec = runkey.decrypt(list(Cv), list(K), off, mode)
                        if len(dec) < len(Cv): continue
                        r = (window_score(dec, M), tsn, start, form, sname, mode, off)
                        results.append(r)
                        if r[0] > best[0]: best = r
        results.sort(reverse=True); results = results[:40]
        ck.write(json.dumps({"seq": sname, "best": list(best)}) + "\n"); ck.flush()
        print(f"[{i}/{len(seqs)}] {sname:26s} best {best[0]:+.3f} "
              f"(seg{best[1]}@{best[2]} {best[3]}/{best[5]})  [{time.time()-t0:.0f}s]", flush=True)

    print("\nTOP 20")
    for f, sn, st, form, name, mode, off in results[:20]:
        print(f"  {f:+.3f} seg{sn:<3}@{st:<5} {form:7s} {name:26s} {mode:9s} off={off}")
    print("\nscores are BEST-60-RUNE-WINDOW means.")
    print("calibration: real LP plaintext -0.90 ; uniform noise -4.84 ;")
    print("the known page-71 totient solve scores -2.395 on this statistic")
    print("(its whole-probe score is only -3.192 because of an unmodelled interrupter).")
    if results[0][0] > -2.6:
        f, sn, st, form, name, mode, off = results[0]
        chunk = segs[sn][st:st+PROBE]
        dec = runkey.decrypt(streams(chunk)[form], list(seqs[name]), off, mode)
        print("INSPECT:", gp.to_text(dec)[:300])
    else:
        print("VERDICT: no number-theoretic keystream found.")
    print(f"({time.time()-t0:.0f}s)")
