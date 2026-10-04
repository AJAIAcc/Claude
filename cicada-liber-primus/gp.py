# Gematria Primus toolkit for Liber Primus
import re, itertools, math

RUNES = "ᚠᚢᚦᚩᚱᚳᚷᚹᚻᚾᛁᛄᛇᛈᛉᛋᛏᛒᛖᛗᛚᛝᛟᛞᚪᚫᚣᛡᛠ"
LETTERS = ["F","U","TH","O","R","C","G","W","H","N","I","J","EO","P","X","S","T","B","E","M","L","NG","OE","D","A","AE","Y","IA","EA"]
PRIMES  = [2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79,83,89,97,101,103,107,109]
R2I = {r:i for i,r in enumerate(RUNES)}
N = 29

# letter-string -> index, longest match first (for turning a word key into indices)
_L2I = sorted(((l,i) for i,l in enumerate(LETTERS)), key=lambda x:-len(x[0]))
ALIAS = {"V":1,"K":5,"Z":15,"Q":5,"NG":21,"ING":21}

def key_to_idx(s):
    """Convert an English key string to Gematria Primus indices (greedy longest-match)."""
    s = s.upper().replace(" ","")
    out, i = [], 0
    while i < len(s):
        for l,idx in _L2I:
            if s.startswith(l, i):
                out.append(idx); i += len(l); break
        else:
            if s[i] in ALIAS:
                out.append(ALIAS[s[i]]); i += 1
            else:
                raise ValueError(f"bad key char {s[i]!r} in {s!r}")
    return out

def to_text(idxs, sep=""):
    return sep.join(LETTERS[i] for i in idxs)

def load_pages(path):
    raw = open(path, encoding="utf-8").read()
    body = raw.split("Page     : %",1)[1]
    return body.split("%")

def runes_of(page):
    return [c for c in page if c in R2I]

def idx_of(page):
    return [R2I[c] for c in runes_of(page)]

def structure(page):
    """Return list of tokens preserving word/clause breaks, as (kind, payload)."""
    toks=[]
    for ch in page:
        if ch in R2I: toks.append(("r", R2I[ch]))
        elif ch == "-": toks.append(("sp", " "))
        elif ch == ".": toks.append(("sp", ". "))
        elif ch == "&": toks.append(("sp", "\n\n"))
        elif ch == "/": toks.append(("sp", ""))
    return toks

def render(toks, dec):
    """dec: iterator of decoded indices matched to 'r' tokens"""
    out=[]; it=iter(dec)
    for k,v in toks:
        if k=="r": out.append(LETTERS[next(it)])
        else: out.append(v)
    return "".join(out)

# ---------- ciphers ----------
def vigenere(idxs, key, decrypt=True, interrupt_rune=None, skip_interrupt=True):
    """Subtract (decrypt) or add (encrypt) key mod 29.
    If interrupt_rune is not None (an index, usually 0 for F): a ciphertext rune equal to it
    is passed through unchanged and does NOT advance the key."""
    out=[]; k=0
    L=len(key)
    for c in idxs:
        if interrupt_rune is not None and c == interrupt_rune:
            out.append(c)
            if not skip_interrupt: k += 1
            continue
        kv = key[k % L]
        out.append((c - kv) % N if decrypt else (c + kv) % N)
        k += 1
    return out

def atbash(idxs):
    return [(N-1-c) for c in idxs]

def shift(idxs, n):
    return [(c+n) % N for c in idxs]

def ioc(idxs):
    n=len(idxs)
    if n<2: return 0.0
    from collections import Counter
    c=Counter(idxs)
    return sum(v*(v-1) for v in c.values())/(n*(n-1)) * N
