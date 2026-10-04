# Liber Primus, unsolved page 0 — attack report

**Verdict: not solved.** The page is one of the ~56 unsolved pages of Cicada 3301's
*Liber Primus*. I identified it, verified its ciphertext against two independent
transcriptions, reproduced all four known Cicada solve methods as positive controls,
and then excluded every public cipher family against it. What remains is a precise
statistical fingerprint that is consistent with exactly one construction — and with no
key source anyone has published.

I want to be straight about the headline finding: **I derived the fingerprint
independently, but I did not discover it.** After measuring it I checked prior work and
found it already documented (see [Prior work](#prior-work)). My numbers replicate it.

---

## Final state — read this first

Everything below this section was written against the **first** page attacked, using a
language model built from 2,058 runes. The work then widened to the whole unsolved
corpus and the model was replaced. **Where the body and this section disagree, this
section is current.** The living record is the
[decipherment ledger](https://claude.ai/code/artifact/6595b43d-ca27-4bdb-bc57-125de8686ed5).

| | |
|---|---|
| Scope | all 55 unsolved pages, 12,956 runes, 98% tiled coverage |
| Solved pages re-derived from the runes | 19 of 19 |
| Language model | 2,341,076 runes (was 2,058) |
| Reference scores | plaintext **−0.90**, noise **−4.84**, threshold **−2.6** |
| Number-theoretic keystreams excluded | 84, best −3.484 |
| Candidate texts excluded | 67 (32,046,644 runes), best −4.136 |

**The threshold is calibrated on a known answer, not guessed.** The solved page 71
(key φ(pₙ) = pₙ − 1) scores −2.395 on the best-60-rune-window statistic. An earlier
cutoff of −3.0 would have *rejected* it, because that page's whole-probe score is only
−3.192 — an unmodelled F-interrupter garbles its tail.

**The 67-text result is a null, not a near miss.** Sixty hits sit inside a band 0.11
wide with no separation, while a planted control key sits alone at −0.904, rank 0 of
2,991,080. The ranking is ordered by generic English statistics — Nietzsche and two
Austen novels lead, Agrippa and the Mabinogion sit mid-pack — and 15 of the top 18 land
on the shortest tile. The detector is measuring English, not keys.

**Four method errors, all caught by controls, all documented in the ledger:** a 17%
coverage hole in the running-key search; the −3.0 threshold above; a `break` that should
have been `continue` in the chain decoder; and a stage-1 offset overrun. The first two
would have turned into false conclusions had the controls not caught them.

**Operational note.** Detached background jobs do not survive container reclamation in
this environment — one 4.5-hour window yielded 7 minutes of compute. The searches
checkpoint per unit (`seqkey_done.jsonl`, `runkey3_done.jsonl`) and resume, and compute
runs in foreground chunks.

---

## 1. Which page this is

| | |
|---|---|
| Identity | **Unsolved page 0** = full-book page 17 = section **0.5**, "crosses/signs" |
| Content | 262 runes, 12 lines, two inverted crosses, a red sigil, a red two-word headline |
| Headline | `ᛋᚻᛖᚩᚷᛗᛡᚠ ᛋᚣᛖᛝᚳ` (ciphertext — index entry 0.5.0) |
| Status | The translation file has **no** entry for section 0.5. Genuinely unsolved. |

The uploaded image matches `liber-primus__images--unsolved/0.jpg` in `rtkd/iddqd`
line for line.

**The ciphertext is not in doubt.** `rtkd/iddqd` and `relikd/LiberPrayground` —
two independently produced community transcriptions — agree on **all 262 runes**.
Full text in [`transcription.txt`](transcription.txt).

---

## 2. The gate: four known methods, reproduced

No attack result is worth anything unless the toolkit can solve what is already solved.
`solve.py` refuses to report anything below until these four pass:

| Page | Method | Recovered opening |
|---|---|---|
| 0 | Atbash on the Gematria Primus | `A WARNING. BELIEVE NOTHING FROM THIS BOOK...` |
| 4–7 | Atbash, then shift +3 | `A KOAN. A MAN DECIDED TO GO AND STUDY WITH A MASTER.` |
| 1 | Vigenère, key `DIVINITY`, plaintext `F` passes through | `WELCOME. WELCOME PILGRIM TO THE GREAT JOURNEY TOWARD THE END OF ALL THINGS...` |
| 71 | Running key φ(pₙ) = pₙ − 1 over primes | `AN END. WITHIN THE DEEP WEB THERE EXISTS A PAGE THAT HASHES TO...` |

Page 1 needs an interrupter-aware **beam decoder**: a ciphertext `ᚠ` is ambiguous —
it may be an encrypted letter, or a plaintext `F` that was left unencrypted and did
*not* advance the key. A straight Vigenère gets as far as `...THE END O`**`G HFJ OLN`**
and then desynchronises. Branching on every `ᚠ` and scoring with a 4-gram model
trained on real LP plaintext recovers the page.

Alphabet: the 29-rune Gematria Primus,
`ᚠᚢᚦᚩᚱᚳᚷᚹᚻᚾᛁᛄᛇᛈᛉᛋᛏᛒᛖᛗᛚᛝᛟᛞᚪᚫᚣᛡᛠ` = F U TH O R C G W H N I J EO P X S T B E M L NG OE D A AE Y IO EA,
prime values 2…109. All arithmetic on indices mod 29.

---

## 3. What the ciphertext is

Scoring throughout is mean 4-gram log-probability per rune under a model trained on
2,058 runes of genuine LP plaintext. **Correct plaintext scores −1.2 to −2.2; uniform
noise scores −3.87.** That gap is the whole measuring instrument.

### It is flat

| text | normalised IoC (×29) |
|---|---|
| solved LP plaintext | **1.788** |
| page 1 ciphertext (Vigenère, 8-char key) | 1.227 |
| **target page** | **0.995** |
| all 49 unsolved pages (12,048 runes) | **1.0002** |

Unigram χ² = 29.9 on 28 df — indistinguishable from uniform. No rune is elevated,
including `ᚠ` (z = +0.78). Periodic IoC shows nothing at any period to 40
(max 1.009, where a real Vigenère of period *p* spikes to ~1.79 at *p*).

**This alone excludes every monoalphabetic substitution and every pure transposition**,
both of which preserve the 1.79 plaintext IoC.

### Except for one thing

Adjacent identical runes, against 3.448% expected under *any* flat model:

| corpus | rate | z |
|---|---|---|
| **unsolved pages (12,047 pairs)** | **0.67%** | **−16.70** |
| solved plaintext | 2.33% | −2.77 |
| solved ciphertext, page 0 (atbash) | 2.73% | −0.53 |
| solved ciphertext, page 1 (Vigenère) | 3.20% | −0.22 |
| solved ciphertext, page 71 (totient) | 2.38% | −0.54 |

And it is *only* at distance 1:

```
k=1  0.67%  z=-16.70      k=5  3.67%  z=+1.33
k=2  3.42%  z= -0.17      k=6  3.56%  z=+0.69
k=3  3.31%  z= -0.82      k=7  3.51%  z=+0.39
k=4  3.53%  z= +0.48      k=8  3.41%  z=-0.21
```

Two controls matter here. The deficit does **not** appear in the solved ciphertext
pages, which came out of the same transcription effort — so it is a property of the
cipher, not of the transcribers. And it is confined to lag 1 — so it is not a general
avoidance of repetition.

### What that pins down

Let `d[i] = c[i] − c[i−1] mod 29`.

* χ² over all 29 step values: **311.6** on 28 df — wildly non-uniform.
* χ² over the 28 **non-zero** step values: **31.9** on 27 df (critical 40.1) — **uniform**.

So the steps are uniform on exactly `{1…28}`, with zero suppressed. The ciphertext is a
**chain**: `c[i] = c[i−1] + s[i]`, with `s` drawn from a flat 28-symbol keystream that
never emits zero.

This also explains why the page resists everything. Any cipher `c = p + k` where the key
does not depend on the ciphertext produces ~3.4% doublets on English text regardless of
the key — because a doublet needs the plaintext difference to cancel the key difference,
which happens at the chance rate. Only a chain construction suppresses it.

Taking the first difference does **not** reveal plaintext (best score −3.64, vs −3.87
for noise): the step stream is itself uniform and aperiodic. Undoing the outer layer
leaves another fully encrypted layer, and the difference stream shows no periodicity
either (IoC 1.0235 at every period tested, consistent with uniform-on-28).

---

## 4. Exclusion ledger

Every row is an attack actually run against this page. Scores are per-rune; recall
**correct = −1.2 to −2.2, noise = −3.87**.

| Family | Coverage | Best score | Outcome |
|---|---|---|---|
| Monoalphabetic | all 812 affine maps `a·x+b`, including every shift and atbash | −3.61 | excluded |
| Transposition | — (IoC argument: transposition preserves unigrams) | — | excluded |
| Keyword Vigenère | 414 keys (LP vocabulary + thematic + known keys) × sub/add × plain/atbash, interrupter-aware beam | −3.39 | excluded |
| Integer-sequence running keys | 7 sequences (φ(p), primes, φ(n), naturals, Fibonacci, squares, triangular) × 300 offsets × sub/add × plain/atbash = 8,400 variants (a wider ad-hoc sweep of 12,800 over 8 sequences × 400 offsets gave the same answer) | −3.41 | excluded |
| Running key from LP text | every page and the solved plaintext, all offsets, both directions | −3.56 | excluded |

| Autokey | plaintext- and ciphertext-autokey, 414 primers, both signs | −3.95 | excluded |
| First difference / chain decode | both signs × 29 primers × 29 post-shifts × ±1 | −3.64 | excluded |
| Unconstrained Vigenère | coordinate-ascent hill-climb over the **entire** key space, lengths 1–12 | −3.21 | excluded |

`solve.py` reproduces the monoalphabetic, keyword-Vigenère, integer-sequence and
hill-climb rows with their controls; the running-key, autokey and first-difference rows
were run ad-hoc in the same session with the same scorer. One caveat on the running-key
row: the nominal top hit is page 15 keyed against *itself* at offset 0, which is the
degenerate all-`F` self-subtraction and not a decryption. The best genuine running-key
score is −3.56.

### The hill-climb carries its own control

The strongest generic attack needs proof it can actually see. Given 262 runes of **real
LP plaintext** encrypted with a random length-8 key, the same hill-climb recovers the
exact key and the exact plaintext:

```
recovered at L=8: score=-1.172  key=XIABIAAXXT  (true XIABIAAXXT)  MATCH=True
decrypt: EBEHAUIARSWHICHCAUSETHELOSSOFDIUINITYCONSUMPTIANWECONSUMETOOMUCHBECAUS
truth  : EBEHAUIARSWHICHCAUSETHELOSSOFDIUINITYCONSUMPTIANWECONSUMETOOMUCHBECAUS
```

On the target page the identical attack tops out at −3.21 (best at L=12). Scores drift upward with key
length purely because longer keys add free parameters — that is overfitting, not signal.
**The page is not a periodic Vigenère of any length ≤ 12.**

---

## 5. Prior work

After deriving the fingerprint I checked whether it was known. It is.
[`Leo-Y-Zhang/LiberPrimusAnalysis`](https://github.com/Leo-Y-Zhang/LiberPrimusAnalysis)
(September 2026) reports **86 doublets against 447 expected, z = −17**, uniform steps on
1…28, no periodicity — and the Uncovering Cicada wiki's frequency analysis independently
reports the same 86 doublets. My 81 doublets in 12,047 pairs (z = −16.70) is the same
measurement over a slightly smaller page selection.

That work also runs a far larger exclusion sweep than mine — 46 integer sequences in raw
and chain form, 14 step-alphabet bijections including discrete logs to all 12 primitive
roots, digraphic ciphers, prime-value feedback, cross-section keystream reuse, and
outguess over all 75 page images. All negative. I am recording this because the honest
summary of my own battery is *independent replication*, not discovery.

---

## 6. Why this page is not solvable from the page

A flat, aperiodic, non-repeating keystream is what a running key from an unavailable
text, a PRNG, or a hash-derived pad looks like. There is no statistical handle left: the
ciphertext has exactly one measurable property, and that property identifies the *shape*
of the cipher while saying nothing about its key.

Cicada's own trail points the same way. The solved page 71 — `AN END` — sends every
pilgrim to a deep-web page identified only by a SHA-512 hash that has never been found.
If the keystream comes from there, the remaining pages are a search problem for a
missing document, not a cryptanalytic problem.

Anyone claiming a plaintext for this page should be asked for three things: a key with a
stated source, a decryption that scores near −1.2 under a plaintext-trained model rather
than near −3.87, and the same key working on a second unsolved page.

---

## Reproducing

```bash
./setup_sources.sh      # clones rtkd/iddqd and relikd/LiberPrayground
python3 solve.py        # gate, characterisation, full battery
```

`solve.py` exits non-zero if the four known solutions fail to reproduce, so a broken
toolkit cannot silently emit attack results.

| file | contents |
|---|---|
| `gp.py` | Gematria Primus, ciphers, IoC |
| `corpus.py` | plaintext corpus + 4-gram model built from the solved pages |
| `fast.py` | cached interrupter-aware beam decoder |
| `keys.py` | 414 candidate keys |
| `solve.py` | the pipeline |
| `transcription.txt` | the verified 262-rune ciphertext |

Sources are fetched, not redistributed.
