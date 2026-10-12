"""Builds the resource fixture and verifies every generated id round-trips.

This is the automated form of checking that used to be done by hand: the ids in
the generated R class, the ids in resources.arsc, and the references inside the
manifest and the compiled res/xml must all agree.
"""
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from forge import build as B            # noqa: E402
from forge import resources as R        # noqa: E402

FIXTURE = os.path.join(HERE, "resfixture")

failures = []


def check(what, got, want):
    ok = got == want
    print(("  PASS  " if ok else "  FAIL  ") + what + "  got=%r want=%r" % (got, want))
    if not ok:
        failures.append(what)


def check_true(what, got):
    check(what, bool(got), True)


def main():
    apk = B.build(FIXTURE)
    print()

    # ---- what the generated R class claims
    r_java = open(os.path.join(FIXTURE, "build", "gen", "R.java")).read()
    r_ids = {}
    current = None
    for line in r_java.split("\n"):
        m = re.match(r"\s*public static final class (\w+) \{", line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r"\s*public static final int (\w+) = (0x[0-9a-f]+);", line)
        if m and current:
            r_ids[(current, m.group(1))] = int(m.group(2), 16)

    # ---- what the shipped resource table actually says
    z = zipfile.ZipFile(apk)
    arsc_text = R.decode_arsc(z.read("resources.arsc"))
    table = {}
    for line in arsc_text.split("\n"):
        m = re.match(r"\s*0x([0-9a-f]{8}) (\w+)/(\w+) ", line)
        if m:
            table[(m.group(2), m.group(3))] = int(m.group(1), 16)

    print("R class ids: %d, resource table ids: %d" % (len(r_ids), len(table)))
    check("every R id exists in the table", sorted(r_ids) == sorted(table), True)
    mismatched = [k for k in r_ids if table.get(k) != r_ids[k]]
    check("no id disagrees between R and the table", mismatched, [])

    print()
    print("Expected resources are present")
    for key in [("string", "app_name"), ("string", "greeting"), ("color", "accent"),
                ("color", "short_form"), ("integer", "answer"), ("bool", "feature_on"),
                ("bool", "feature_off"), ("xml", "config"), ("drawable", "dot"),
                ("mipmap", "ic_launcher"), ("color", "ic_launcher_background")]:
        check_true("%s/%s" % key, key in r_ids)

    print()
    print("Files landed in the apk")
    names = set(z.namelist())
    check_true("res/xml/config.xml", "res/xml/config.xml" in names)
    check_true("res/drawable/dot.png", "res/drawable/dot.png" in names)
    check_true("classes.dex", "classes.dex" in names)

    print()
    print("Manifest references resolve to real resources")
    man = R.decode_axml(z.read("AndroidManifest.xml"))
    m = re.search(r"android:label\(0x01010001\)=@0x([0-9a-f]+)", man)
    check_true("app label is a reference", m is not None)
    if m:
        check("label points at string/app_name", int(m.group(1), 16), r_ids[("string", "app_name")])
    m = re.search(r"android:icon\(0x01010002\)=@0x([0-9a-f]+)", man)
    if m:
        check("icon points at mipmap/ic_launcher", int(m.group(1), 16),
              r_ids[("mipmap", "ic_launcher")])
    m = re.search(r"android:resource\(0x01010025\)=@0x([0-9a-f]+)", man)
    check_true("meta-data carries a resource reference", m is not None)
    if m:
        check("meta-data points at xml/config", int(m.group(1), 16), r_ids[("xml", "config")])

    print()
    print("Receiver is declared with its filter")
    check_true("receiver element", "<receiver " in man)
    check_true("package data scheme", "android:scheme(0x01010027)='package'" in man)
    check_true("PACKAGE_ADDED action", "PACKAGE_ADDED" in man)
    check_true("app-level meta-data value", "android:value(0x01010024)='fixture'" in man)

    print()
    print("Compiled res/xml decodes back correctly")
    xml = R.decode_axml(z.read("res/xml/config.xml"))
    print(xml)
    m = re.search(r"android:label\(0x01010001\)=@0x([0-9a-f]+)", xml)
    check_true("label inside res/xml is a reference", m is not None)
    if m:
        check("and points at string/app_name", int(m.group(1), 16), r_ids[("string", "app_name")])
    check_true("priority stayed an integer", "android:priority(0x0101001c)=7" in xml)
    check_true("a literal 'true' in a string attribute stayed text",
               "android:value(0x01010024)='true'" in xml)
    check_true("a numeric string attribute stayed text",
               "android:value(0x01010024)='123'" in xml)

    print()
    print("Unknown attributes fail the build rather than being guessed")
    try:
        R.encode_axml(R.XmlElement("x", [("android:notARealAttribute", "1")]))
        check("unknown attribute refused", "accepted", "refused")
    except ValueError:
        check("unknown attribute refused", "refused", "refused")

    print()
    if failures:
        print("%d FAILURE(S): %s" % (len(failures), failures))
        sys.exit(1)
    print("ALL RESOURCE PIPELINE CHECKS PASSED")


if __name__ == "__main__":
    main()
