"""Compile a res/ tree into a resource table, binary XML, and a generated R class.

What this does NOT do, deliberately: general layout XML. Binary AXML stores each
android:* attribute as a framework resource id, and a real layout touches hundreds
of them. Those ids cannot be derived -- they come from the framework's public.xml,
which is not available offline -- so any attribute missing from resources.ATTR
raises rather than being guessed. A wrong id is a silent runtime failure, which is
much worse than a build error. res/xml metadata and manifests use a small, known
set of attributes and are well served; layouts stay in Java.
"""
import os
import re
import xml.etree.ElementTree as ET

from . import resources as R

# density qualifier -> ResTable_config density value
DENSITIES = {
    "ldpi": 120, "mdpi": 160, "tvdpi": 213, "hdpi": 240, "xhdpi": 320,
    "xxhdpi": 480, "xxxhdpi": 640, "anydpi": 0xFFFE, "nodpi": 0xFFFF,
}

# res/ subdirectory -> resource type name
FILE_DIRS = {
    "drawable": "drawable",
    "mipmap": "mipmap",
    "xml": "xml",
    "raw": "raw",
}

VALUE_TAGS = {
    "string": ("string", "string"),
    "color": ("color", "color"),
    "integer": ("integer", "int"),
    "bool": ("bool", "bool"),
}

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
REF = re.compile(r"^@([a-z]+)/([A-Za-z0-9_.]+)$")


class ResError(Exception):
    pass


def _qualifiers(dirname):
    """'drawable-xxhdpi-v21' -> ('drawable', (480, 21))."""
    parts = dirname.split("-")
    base = parts[0]
    density = 0
    sdk = 0
    for q in parts[1:]:
        if q in DENSITIES:
            density = DENSITIES[q]
        elif re.match(r"^v\d+$", q):
            sdk = int(q[1:])
        else:
            raise ResError("unsupported resource qualifier %r in %s" % (q, dirname))
    return base, (density, sdk)


def _ident(name):
    clean = name.replace("-", "_").replace(".", "_")
    if not IDENT.match(clean):
        raise ResError("resource name %r is not a usable Java identifier" % name)
    return clean


def parse_color(s):
    t = s.strip().lstrip("#")
    if len(t) == 3:
        t = "".join(c * 2 for c in t)
    if len(t) == 6:
        t = "FF" + t
    if len(t) != 8:
        raise ResError("bad colour %r" % s)
    return int(t, 16)


def parse_values_file(path):
    """<resources> of <string>, <color>, <integer>, <bool>."""
    out = []
    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        raise ResError("cannot parse %s: %s" % (path, e))
    if root.tag != "resources":
        raise ResError("%s: root element must be <resources>" % path)
    for el in root:
        if not isinstance(el.tag, str) or el.tag not in VALUE_TAGS:
            if isinstance(el.tag, str):
                raise ResError("%s: unsupported <%s>" % (path, el.tag))
            continue
        name = el.get("name")
        if not name:
            raise ResError("%s: <%s> without a name" % (path, el.tag))
        tname, kind = VALUE_TAGS[el.tag]
        text = (el.text or "").strip()
        if kind == "string":
            value = text
        elif kind == "color":
            value = parse_color(text)
        elif kind == "int":
            try:
                value = int(text, 0)
            except ValueError:
                raise ResError("%s: <integer name=%r> is not a number" % (path, name))
        else:
            value = text.lower() in ("true", "1", "yes")
        out.append((tname, name, kind, value, (0, 0)))
    return out


def scan(res_dir):
    """Walk res/ and return (entries, xml_paths).

    entries: (type, name, kind, value, cfg) -- file entries carry their apk path.
    xml_paths: {apk_path: source_path} for files still needing compilation.
    """
    entries = []
    xml_paths = {}
    binaries = {}
    if not res_dir or not os.path.isdir(res_dir):
        return entries, xml_paths, binaries

    for dirname in sorted(os.listdir(res_dir)):
        full = os.path.join(res_dir, dirname)
        if not os.path.isdir(full):
            continue
        base, cfg = _qualifiers(dirname)

        if base == "values":
            for f in sorted(os.listdir(full)):
                if f.endswith(".xml"):
                    entries.extend(parse_values_file(os.path.join(full, f)))
            continue

        if base not in FILE_DIRS:
            raise ResError("unsupported res/ directory %r" % dirname)
        tname = FILE_DIRS[base]
        for f in sorted(os.listdir(full)):
            src = os.path.join(full, f)
            if not os.path.isfile(src):
                continue
            stem = f.rsplit(".", 1)[0]
            apk_path = "res/%s/%s" % (dirname, f)
            entries.append((tname, stem, "file", apk_path, cfg))
            if f.endswith(".xml"):
                xml_paths[apk_path] = src
            else:
                binaries[apk_path] = open(src, "rb").read()
    return entries, xml_paths, binaries


def build_table(package, pkg_id, entries):
    """Group entries by type in a stable order and encode the table."""
    by_type = {}
    for (tname, name, kind, value, cfg) in entries:
        by_type.setdefault(tname, []).append((name, kind, value, cfg))
    types = []
    for tname in sorted(by_type):
        seen = set()
        for e in by_type[tname]:
            key = (e[0], e[3])
            if key in seen:
                raise ResError("duplicate resource %s/%s for the same configuration"
                               % (tname, e[0]))
            seen.add(key)
        types.append((tname, by_type[tname]))
    arsc, ids = R.encode_arsc(package, pkg_id, types)
    return arsc, ids


def make_resolver(ids):
    def resolve(ref):
        m = REF.match(ref.strip())
        if not m:
            raise ResError("cannot parse resource reference %r" % ref)
        tname, name = m.group(1), m.group(2)
        if (tname, name) not in ids:
            raise ResError("reference %r does not match any resource" % ref)
        return ids[(tname, name)]
    return resolve


_NS = "{%s}" % R.ANDROID_NS


def _value(raw, attr_local, resolve):
    s = raw.strip()
    if s.startswith("@"):
        return ("ref", resolve(s))
    if attr_local in R.STRING_ATTRS:
        return s
    if s in ("true", "false"):
        return s == "true"
    if re.match(r"^-?\d+$", s):
        return int(s)
    if re.match(r"^0x[0-9a-fA-F]+$", s):
        return ("hex", int(s, 16))
    if re.match(r"^#[0-9a-fA-F]{3,8}$", s):
        return ("color", parse_color(s))
    return s


def _convert(el, resolve, path):
    attrs = []
    for k in sorted(el.attrib):
        v = el.attrib[k]
        if k.startswith(_NS):
            local = k[len(_NS):]
            name = "android:" + local
        elif k.startswith("{"):
            raise ResError("%s: attribute %r is in an unsupported namespace" % (path, k))
        else:
            local = k
            name = k
        attrs.append((name, _value(v, local, resolve)))
    tag = el.tag
    if tag.startswith("{"):
        tag = tag.split("}", 1)[1]
    children = [_convert(c, resolve, path) for c in el if isinstance(c.tag, str)]
    return R.XmlElement(tag, attrs, children)


def compile_xml(path, resolve):
    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        raise ResError("cannot parse %s: %s" % (path, e))
    return R.encode_axml(_convert(root, resolve, path))


def generate_r(package, ids):
    """The R class real Android generates, so no resource id is ever a literal."""
    by_type = {}
    for (tname, name), rid in ids.items():
        by_type.setdefault(tname, {})[name] = rid
    lines = [
        "package %s;" % package,
        "",
        "/** Generated by droidforge from res/. Do not edit. */",
        "public final class R {",
        "    private R() {",
        "    }",
    ]
    for tname in sorted(by_type):
        lines.append("")
        lines.append("    public static final class %s {" % _ident(tname))
        lines.append("        private %s() {" % _ident(tname))
        lines.append("        }")
        lines.append("")
        for name in sorted(by_type[tname]):
            lines.append("        public static final int %s = 0x%08x;"
                         % (_ident(name), by_type[tname][name]))
        lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"
