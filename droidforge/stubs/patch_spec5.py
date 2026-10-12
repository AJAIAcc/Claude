"""Fifth stub pass: writing a document the user picked."""
import os

here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()

if "openOutputStream" in src:
    print("already patched")
    raise SystemExit(0)

old = "    public java.io.InputStream openInputStream(android.net.Uri uri) throws java.io.FileNotFoundException STUB"
new = (old + "\n"
       "    public java.io.OutputStream openOutputStream(android.net.Uri uri) throws java.io.FileNotFoundException STUB")
assert src.count(old) == 1, "ContentResolver anchor"
src = src.replace(old, new)

old = '    public static final String ACTION_OPEN_DOCUMENT = "android.intent.action.OPEN_DOCUMENT";'
new = (old + "\n"
       '    public static final String ACTION_CREATE_DOCUMENT = "android.intent.action.CREATE_DOCUMENT";\n'
       '    public static final String EXTRA_TITLE = "android.intent.extra.TITLE";')
assert src.count(old) == 1, "Intent anchor"
src = src.replace(old, new)

open(spec_path, "w").write(src)
print("patched -> %d lines" % len(src.splitlines()))
