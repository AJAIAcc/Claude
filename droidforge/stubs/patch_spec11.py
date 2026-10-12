"""Eleventh stub pass (OPEN CRM): View scroll position, so a re-rendered screen keeps its place."""
import os
here = os.path.dirname(os.path.abspath(__file__))
spec_path = os.path.join(here, "spec_content.txt")
src = open(spec_path).read()
if "public final int getScrollY()" in src:
    print("already patched")
    raise SystemExit(0)
anchor = "    public ViewPropertyAnimator animate() STUB\n"
assert anchor in src
src = src.replace(anchor, anchor +
    "    public final int getScrollY() STUB\n"
    "    public void scrollTo(int x, int y) STUB\n", 1)
open(spec_path, "w").write(src)
print("patched")
