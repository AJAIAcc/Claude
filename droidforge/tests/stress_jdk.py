"""Translate thousands of real JDK classes and validate the DEX (structure + register types)."""
import glob, sys, time, collections, traceback
sys.path.insert(0, '.')
from forge.classfile import ClassFile
from forge.translate import Context, TranslateError
from forge.dexwriter import DexWriter
from forge.dexcheck import DexFile

files = sorted(glob.glob('/tmp/jdk/java.base/java/**/*.class', recursive=True))
if len(sys.argv) > 1:
    files = [f for f in files if sys.argv[1] in f]
fails = collections.Counter()
examples = {}
ok = 0
t0 = time.time()
batch = []
for f in files:
    cf = ClassFile(open(f, 'rb').read())
    ctx = Context()
    try:
        ctx.translate(cf)
        batch.extend(ctx.out_classes)
        ok += 1
    except TranslateError as e:
        msg = str(e).split(': ', 1)[-1][:70]
        fails[msg] += 1
        examples.setdefault(msg, cf.name)
    except Exception as e:
        msg = 'CRASH ' + repr(e)[:80]
        fails[msg] += 1
        if msg not in examples:
            examples[msg] = cf.name + '\n' + traceback.format_exc()[-600:]
print("translated %d/%d classes in %.1fs" % (ok, len(files), time.time() - t0))
for m, n in fails.most_common(15):
    print("  %4d  %s   (e.g. %s)" % (n, m, examples[m]))
# write in chunks (65k method ref limit) and validate
errs = collections.Counter()
eg = {}
t0 = time.time()
total = 0
for i in range(0, len(batch), 300):
    chunk = batch[i:i + 300]
    seen = set(); uniq = []
    for c in chunk:
        if c.desc not in seen:
            seen.add(c.desc); uniq.append(c)
    data = DexWriter(uniq).write()
    total += len(data)
    d = DexFile(data)
    for e in d.errors:
        key = e.split(': ', 1)[-1]
        key = ' '.join(w for w in key.split() if not w.startswith(('v', '@')) or len(w) > 6)[:90]
        errs[key] += 1
        eg.setdefault(key, e[:200])
print("wrote+validated %d bytes of dex in %.1fs; %d distinct error kinds, %d total" % (total, time.time() - t0, len(errs), sum(errs.values())))
for k, n in errs.most_common(25):
    print("  %5d  %s\n         e.g. %s" % (n, k, eg[k]))
