import gp, math, collections, pickle
import os
SRC = os.environ.get("LP_SOURCES", os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources"))
P = gp.load_pages(os.path.join(SRC, "iddqd", "liber-primus__transcription--master",
                               "liber-primus__transcription--master.txt"))

def plain_sequences():
    """Return list of (name, token-stream) where token stream is list of ('r',idx) / ('sp',..)"""
    seqs=[]
    for i in [3,8,9,10,11,14,72]:
        seqs.append((f"plain{i}", gp.structure(P[i]), gp.idx_of(P[i])))
    for i in [0]:
        seqs.append((f"atbash{i}", gp.structure(P[i]), gp.atbash(gp.idx_of(P[i]))))
    for i in [4,5,6,7]:
        seqs.append((f"koan{i}", gp.structure(P[i]), gp.shift(gp.atbash(gp.idx_of(P[i])),3)))
    return seqs

def build():
    seqs = plain_sequences()
    allidx=[]; words=collections.Counter()
    for name,toks,dec in seqs:
        allidx.extend(dec)
        txt=[]; it=iter(dec)
        cur=[]
        for k,v in toks:
            if k=='r': cur.append(next(it))
            else:
                if cur: words[tuple(cur)]+=1; cur=[]
        if cur: words[tuple(cur)]+=1
    return allidx, words

ALLIDX, WORDS = build()

class NGram:
    def __init__(self, seq, order=4, alpha=0.1):
        self.order=order; self.alpha=alpha; self.N=gp.N
        self.counts=[collections.Counter() for _ in range(order+1)]
        pad=[-1]*(order-1)
        s=pad+seq
        for o in range(1,order+1):
            for i in range(len(s)-o+1):
                self.counts[o][tuple(s[i:i+o])]+=1
        self.tot=[sum(c.values()) for c in self.counts]
    def logp(self, seq):
        o=self.order; tot=0.0
        pad=[-1]*(o-1); s=pad+list(seq)
        for i in range(o-1, len(s)):
            ctx=tuple(s[i-o+1:i]); x=s[i]
            # backoff
            lp=None
            for k in range(o,0,-1):
                c=ctx[o-k:] if k>1 else ()
                num=self.counts[k][c+(x,)]
                den=sum(self.counts[k][c+(y,)] for y in range(self.N)) if k>1 else self.tot[1]
                if den>0 and num>0:
                    lp=math.log((num+self.alpha)/(den+self.alpha*self.N)); break
            if lp is None: lp=math.log(1.0/self.N) - 2.0
            tot+=lp
        return tot

MODEL = NGram(ALLIDX, order=4)
VOCAB = set(WORDS)

def score_words(toks, dec):
    it=iter(dec); cur=[]; tot=0; hit=0
    for k,v in toks:
        if k=='r': cur.append(next(it))
        else:
            if cur:
                tot+=1
                if tuple(cur) in VOCAB: hit+=1
                cur=[]
    if cur:
        tot+=1
        if tuple(cur) in VOCAB: hit+=1
    return hit/max(tot,1), hit, tot
