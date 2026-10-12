"""Twelfth stub pass (OPEN CRM): AlertDialog.Builder(Context, int theme) and the theme constants."""
import os
here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()
if "THEME_DEVICE_DEFAULT_LIGHT" in src:
    print("already patched")
    raise SystemExit(0)
a = "public class AlertDialog extends Dialog {\n"
assert a in src
src = src.replace(a, a +
    "    public static final int THEME_DEVICE_DEFAULT_DARK = 4;\n"
    "    public static final int THEME_DEVICE_DEFAULT_LIGHT = 5;\n", 1)
b = "        public Builder(Context context) STUB\n"
assert b in src
src = src.replace(b, b + "        public Builder(Context context, int themeResId) STUB\n", 1)
open(spec_path, "w").write(src)
print("patched")
