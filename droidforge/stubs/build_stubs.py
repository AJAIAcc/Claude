"""Regenerate android-stubs.jar from spec_content.txt (add APIs there, then rerun)."""
import os, re, shutil, subprocess, glob
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "spec_content.txt")).read()
parts = re.split(r"^//// (.+)$", src, flags=re.M)
sdir = os.path.join(here, "src")
shutil.rmtree(sdir, ignore_errors=True)
for i in range(1, len(parts), 2):
    path, body = parts[i].strip(), parts[i + 1]
    body = body.replace(" STUB", ' { throw new RuntimeException("Stub!"); }')
    full = os.path.join(sdir, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w").write(body.lstrip())
cdir = os.path.join(here, "classes")
shutil.rmtree(cdir, ignore_errors=True)
env = dict(os.environ); env.pop("JAVA_TOOL_OPTIONS", None)
subprocess.run(["javac", "-Xlint:-options", "--release", "8", "-d", cdir] +
               glob.glob(os.path.join(sdir, "**", "*.java"), recursive=True), check=True, env=env)
jar = os.path.join(here, "android-stubs.jar")
if os.path.exists(jar):
    os.remove(jar)
shutil.make_archive(jar[:-4], "zip", cdir)
os.rename(jar[:-4] + ".zip", jar)
shutil.rmtree(cdir)
print("wrote", jar)
