"""Differential tests: real JVM output vs our DEX run in the Dalvik test VM."""
import glob, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from forge.classfile import ClassFile
from forge.translate import translate_classes
from forge.dexwriter import DexWriter
from forge.dexcheck import DexFile
from forge.dexvm import run_dex

env = dict(os.environ)
env.pop("JAVA_TOOL_OPTIONS", None)
here = os.path.dirname(os.path.abspath(__file__))
cases = sys.argv[1:] or sorted(glob.glob(os.path.join(here, "cases", "*.java")))
ok = True
for src in cases:
    name = os.path.splitext(os.path.basename(src))[0]
    out = tempfile.mkdtemp()
    subprocess.run(["javac", "-Xlint:-options", "--release", "8", "-d", out, src], check=True, env=env)
    exp = subprocess.run(["java", "-cp", out, name], capture_output=True, text=True, env=env).stdout
    cfs = [ClassFile(open(f, "rb").read()) for f in glob.glob(out + "/**/*.class", recursive=True)]
    data = DexWriter(translate_classes(cfs)).write()
    d = DexFile(data)
    if d.errors:
        print("FAIL %s: dex errors:\n  %s" % (name, "\n  ".join(d.errors[:15])))
        ok = False
        continue
    try:
        got = run_dex(data, "L%s;" % name)
    except Exception as e:
        import traceback; traceback.print_exc()
        got = "VM CRASH: %r" % e
    if got == exp:
        print("PASS %-10s (%d bytes dex, %d classes)" % (name, len(data), len(d.classes)))
    else:
        ok = False
        print("FAIL %s" % name)
        el, gl = exp.splitlines(), got.splitlines()
        for i in range(max(len(el), len(gl))):
            e = el[i] if i < len(el) else "<none>"
            g = gl[i] if i < len(gl) else "<none>"
            if e != g:
                print("   line %d\n     jvm: %s\n     dex: %s" % (i + 1, e, g))
    shutil.rmtree(out)
sys.exit(0 if ok else 1)
