"""Android binary resource formats, from the ResourceTypes.h layout:
  * binary XML (AXML) for AndroidManifest.xml
  * resources.arsc resource table (strings + a launcher icon)
  * a tiny PNG encoder for generating launcher icons
"""
import math
import struct
import zlib

RES_STRING_POOL_TYPE = 0x0001
RES_TABLE_TYPE = 0x0002
RES_XML_TYPE = 0x0003
RES_XML_START_NAMESPACE_TYPE = 0x0100
RES_XML_END_NAMESPACE_TYPE = 0x0101
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
RES_XML_RESOURCE_MAP_TYPE = 0x0180
RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_TYPE = 0x0201
RES_TABLE_TYPE_SPEC_TYPE = 0x0202

TYPE_NULL = 0x00
TYPE_REFERENCE = 0x01
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12

ANDROID_NS = "http://schemas.android.com/apk/res/android"

# android:* attribute resource ids (framework public.xml)
ATTR = {
    "theme": 0x01010000,
    "label": 0x01010001,
    "icon": 0x01010002,
    "name": 0x01010003,
    "permission": 0x01010006,
    "enabled": 0x0101000e,
    "exported": 0x01010010,
    "process": 0x01010011,
    "launchMode": 0x0101001d,
    "screenOrientation": 0x0101001e,
    "configChanges": 0x0101001f,
    "minSdkVersion": 0x0101020c,
    "versionCode": 0x0101021b,
    "versionName": 0x0101021c,
    "windowSoftInputMode": 0x0101022b,
    "targetSdkVersion": 0x01010270,
    "allowBackup": 0x01010280,
    "hardwareAccelerated": 0x010102d3,
    "supportsRtl": 0x010103af,
    "roundIcon": 0x0101052c,
    "compileSdkVersion": 0x01010572,
    "compileSdkVersionCodename": 0x01010573,
    "drawable": 0x01010199,
    # Contiguous in the framework's public.xml; each one added here has been
    # checked by decoding a built manifest and reading the id back. An attribute
    # that is not in this table fails the build rather than being guessed at --
    # a wrong id is a silent runtime failure, which is the worst kind.
    "value": 0x01010024,
    "resource": 0x01010025,
    "mimeType": 0x01010026,
    "scheme": 0x01010027,
    "host": 0x01010028,
    "port": 0x01010029,
    "path": 0x0101002a,
    "pathPrefix": 0x0101002b,
    "pathPattern": 0x0101002c,
    "priority": 0x0101001c,
    "description": 0x01010020,
    "hasCode": 0x0101000c,
    "persistent": 0x0101000d,
    "debuggable": 0x0101000f,
    "directBootAware": 0x01010505,
}

# Attributes whose value is always literal text. Without aapt's knowledge of each
# attribute's declared type, a bare "true" or "123" would otherwise be coerced to
# a boolean or an integer; for these it never should be.
STRING_ATTRS = {
    "name", "label", "permission", "process", "scheme", "host", "path",
    "pathPrefix", "pathPattern", "mimeType", "value", "description",
    "versionName", "compileSdkVersionCodename", "targetPackage",
}


def _pad4(b):
    return b + b"\0" * (-len(b) % 4)


def string_pool(strings, utf8=False):
    """ResStringPool chunk (UTF-16 variant, no styles)."""
    offsets = []
    data = bytearray()
    for s in strings:
        offsets.append(len(data))
        units = s.encode("utf-16-le")
        n = len(units) // 2
        if n > 0x7FFF:
            data += struct.pack("<HH", 0x8000 | (n >> 16), n & 0xFFFF)
        else:
            data += struct.pack("<H", n)
        data += units + b"\0\0"
    data = _pad4(bytes(data))
    header_size = 28
    strings_start = header_size + 4 * len(strings)
    body = struct.pack("<%dI" % len(strings), *offsets) + data
    size = header_size + len(body)
    head = struct.pack("<HHIIIIII", RES_STRING_POOL_TYPE, header_size, size, len(strings), 0, 0,
                       strings_start, 0)
    return head + body


# ------------------------------------------------------------------ AXML
class XmlElement:
    def __init__(self, tag, attrs=None, children=None):
        self.tag = tag
        self.attrs = attrs or []       # list of (name, value) ; name "android:foo" or "foo"
        self.children = children or []


def _typed(value):
    """Python value -> (dataType, data, raw_string or None)"""
    if isinstance(value, bool):
        return TYPE_INT_BOOLEAN, 0xFFFFFFFF if value else 0, None
    if isinstance(value, int):
        return TYPE_INT_DEC, value & 0xFFFFFFFF, None
    if isinstance(value, tuple) and value[0] == "ref":
        return TYPE_REFERENCE, value[1], None
    if isinstance(value, tuple) and value[0] == "hex":
        return TYPE_INT_HEX, value[1] & 0xFFFFFFFF, None
    if isinstance(value, tuple) and value[0] == "color":
        return TYPE_INT_COLOR_ARGB8, value[1] & 0xFFFFFFFF, None
    return TYPE_STRING, None, str(value)


def encode_axml(root):
    # collect strings: attribute names with resource ids first (resource map order)
    res_names = []
    others = []

    def walk(e):
        for (n, v) in e.attrs:
            local = n.split(":", 1)[1] if n.startswith("android:") else n
            if n.startswith("android:"):
                if local not in ATTR:
                    raise ValueError("unknown android attribute " + n)
                if local not in res_names:
                    res_names.append(local)
            else:
                others.append(local)
            t, d, raw = _typed(v)
            if raw is not None:
                others.append(raw)
        others.append(e.tag)
        for c in e.children:
            walk(c)
    walk(root)
    # resource-id'd names must be first & in the order of the resource map
    res_names.sort(key=lambda n: ATTR[n])
    strings = list(res_names)
    for s in ["android", ANDROID_NS] + others:
        if s not in strings:
            strings.append(s)
    idx = {s: i for i, s in enumerate(strings)}

    chunks = bytearray()
    chunks += string_pool(strings)
    rmap = struct.pack("<%dI" % len(res_names), *[ATTR[n] for n in res_names])
    chunks += struct.pack("<HHI", RES_XML_RESOURCE_MAP_TYPE, 8, 8 + len(rmap)) + rmap
    ns = struct.pack("<HHIIIII", RES_XML_START_NAMESPACE_TYPE, 16, 24, 1, 0xFFFFFFFF,
                     idx["android"], idx[ANDROID_NS])
    chunks += ns
    line = [1]

    def elem(e):
        attrs = []
        for (n, v) in e.attrs:
            if n.startswith("android:"):
                local = n.split(":", 1)[1]
                nsidx = idx[ANDROID_NS]
                sort_key = (0, ATTR[local])
            else:
                local = n
                nsidx = 0xFFFFFFFF
                sort_key = (1, local)
            t, d, raw = _typed(v)
            if raw is not None:
                d = idx[raw]
                rawidx = idx[raw]
            else:
                rawidx = 0xFFFFFFFF
            attrs.append((sort_key, struct.pack("<IIIHBBI", nsidx, idx[local], rawidx, 8, 0, t, d)))
        attrs.sort(key=lambda a: a[0])
        body = struct.pack("<IIHHHHHH", 0xFFFFFFFF, idx[e.tag], 20, 20, len(attrs), 0, 0, 0)
        body += b"".join(a[1] for a in attrs)
        out = struct.pack("<HHIII", RES_XML_START_ELEMENT_TYPE, 16, 16 + len(body), line[0], 0xFFFFFFFF) + body
        line[0] += 1
        for c in e.children:
            out += elem(c)
        out += struct.pack("<HHIIIII", RES_XML_END_ELEMENT_TYPE, 16, 24, line[0], 0xFFFFFFFF,
                           0xFFFFFFFF, idx[e.tag])
        line[0] += 1
        return out

    chunks += elem(root)
    chunks += struct.pack("<HHIIIII", RES_XML_END_NAMESPACE_TYPE, 16, 24, line[0], 0xFFFFFFFF,
                          idx["android"], idx[ANDROID_NS])
    return struct.pack("<HHI", RES_XML_TYPE, 8, 8 + len(chunks)) + bytes(chunks)


def decode_axml(b):
    """Minimal AXML -> text decoder, used to self-check the encoder."""
    t, hs, size = struct.unpack_from("<HHI", b, 0)
    assert t == RES_XML_TYPE and size == len(b), "bad xml header"
    p = hs
    strings = []
    rmap = []
    out = []
    depth = 0
    while p < len(b):
        ct, chs, csz = struct.unpack_from("<HHI", b, p)
        if ct == RES_STRING_POOL_TYPE:
            n, _, flags, sstart, _ = struct.unpack_from("<IIIII", b, p + 8)
            offs = struct.unpack_from("<%dI" % n, b, p + 28)
            for o in offs:
                q = p + sstart + o
                (ln,) = struct.unpack_from("<H", b, q)
                strings.append(b[q + 2:q + 2 + 2 * ln].decode("utf-16-le"))
        elif ct == RES_XML_RESOURCE_MAP_TYPE:
            rmap = list(struct.unpack_from("<%dI" % ((csz - 8) // 4), b, p + 8))
        elif ct == RES_XML_START_ELEMENT_TYPE:
            ns, name, ast, asz, cnt = struct.unpack_from("<IIHHH", b, p + 16)
            attrs = []
            for i in range(cnt):
                q = p + 16 + ast + i * asz
                ans, an, araw, vs, _, vt, vd = struct.unpack_from("<IIIHBBI", b, q)
                nm = strings[an]
                if an < len(rmap):
                    nm = "android:%s(0x%08x)" % (nm, rmap[an])
                if vt == TYPE_STRING:
                    val = repr(strings[vd])
                elif vt == TYPE_INT_BOOLEAN:
                    val = "true" if vd else "false"
                elif vt == TYPE_REFERENCE:
                    val = "@0x%08x" % vd
                else:
                    val = str(vd if vd < 0x80000000 else vd - (1 << 32))
                attrs.append("%s=%s" % (nm, val))
            out.append("  " * depth + "<%s %s>" % (strings[name], " ".join(attrs)))
            depth += 1
        elif ct == RES_XML_END_ELEMENT_TYPE:
            depth -= 1
        p += csz
    return "\n".join(out)


CONFIG_CHANGES = 0x80 | 0x400 | 0x800 | 0x100 | 0x20 | 0x10 | 0x40  # orientation|screenSize|... (no restart)


def _component(tag, spec, handle_config=False):
    """<service> or <receiver>, with intent filters, data specs and meta-data."""
    if isinstance(spec, str):
        spec = {"name": spec}
    attrs = [("android:name", spec["name"]),
             ("android:exported", bool(spec.get("exported", False)))]
    if spec.get("permission"):
        attrs.append(("android:permission", spec["permission"]))
    if spec.get("process"):
        attrs.append(("android:process", spec["process"]))
    if "enabled" in spec:
        attrs.append(("android:enabled", bool(spec["enabled"])))
    if handle_config:
        attrs.append(("android:configChanges", ("hex", CONFIG_CHANGES)))

    children = []
    actions = spec.get("actions", ())
    categories = spec.get("categories", ())
    data = spec.get("data", ())
    if actions or categories or data:
        filter_attrs = []
        if spec.get("priority") is not None:
            filter_attrs.append(("android:priority", int(spec["priority"])))
        kids = []
        for a in actions:
            kids.append(XmlElement("action", [("android:name", a)]))
        for c in categories:
            kids.append(XmlElement("category", [("android:name", c)]))
        for d in data:
            dattrs = []
            for key in ("scheme", "host", "port", "path", "pathPrefix", "pathPattern",
                        "mimeType"):
                if d.get(key):
                    dattrs.append(("android:" + key, d[key]))
            if dattrs:
                kids.append(XmlElement("data", dattrs))
        children.append(XmlElement("intent-filter", filter_attrs, kids))

    for md in spec.get("meta_data", ()):
        mattrs = [("android:name", md["name"])]
        if "resource" in md:
            mattrs.append(("android:resource", ("ref", md["resource"])))
        elif "value" in md:
            mattrs.append(("android:value", md["value"]))
        children.append(XmlElement("meta-data", mattrs))

    return XmlElement(tag, attrs, children)


def manifest(package, version_code, version_name, label, activity, min_sdk=24, target_sdk=34,
             icon_ref=None, extra_activities=(), permissions=(), orientation=None, handle_config=True,
             services=(), receivers=(), app_meta_data=(), allow_backup=True):
    app_attrs = [("android:label", label), ("android:allowBackup", bool(allow_backup))]
    if icon_ref is not None:
        app_attrs.append(("android:icon", ("ref", icon_ref)))
    act_attrs = [("android:name", activity), ("android:exported", True)]
    if handle_config:
        act_attrs.append(("android:configChanges", ("hex", CONFIG_CHANGES)))
    if orientation is not None:
        act_attrs.append(("android:screenOrientation", orientation))
    main = XmlElement("activity", act_attrs, [
        XmlElement("intent-filter", [], [
            XmlElement("action", [("android:name", "android.intent.action.MAIN")]),
            XmlElement("category", [("android:name", "android.intent.category.LAUNCHER")]),
        ])
    ])
    acts = [main]
    for a in extra_activities:
        ea = [("android:name", a), ("android:exported", False)]
        if handle_config:
            ea.append(("android:configChanges", ("hex", CONFIG_CHANGES)))
        acts.append(XmlElement("activity", ea))
    for s in services:
        acts.append(_component("service", s))
    for r in receivers:
        acts.append(_component("receiver", r))
    for md in app_meta_data:
        mattrs = [("android:name", md["name"])]
        if "resource" in md:
            mattrs.append(("android:resource", ("ref", md["resource"])))
        elif "value" in md:
            mattrs.append(("android:value", md["value"]))
        acts.append(XmlElement("meta-data", mattrs))
    children = [XmlElement("uses-sdk", [("android:minSdkVersion", min_sdk),
                                        ("android:targetSdkVersion", target_sdk)])]
    for perm in permissions:
        children.append(XmlElement("uses-permission", [("android:name", perm)]))
    children.append(XmlElement("application", app_attrs, acts))
    root = XmlElement("manifest", [("android:versionCode", version_code),
                                   ("android:versionName", version_name),
                                   ("package", package)], children)
    return encode_axml(root)


def adaptive_icon_xml(bg_ref, fg_ref):
    root = XmlElement("adaptive-icon", [], [
        XmlElement("background", [("android:drawable", ("ref", bg_ref))]),
        XmlElement("foreground", [("android:drawable", ("ref", fg_ref))]),
    ])
    return encode_axml(root)


# ------------------------------------------------------------------ resources.arsc
DENSITY_XXXHDPI = 640
DENSITY_ANY = 0xFFFE
TYPE_INT_COLOR_ARGB8 = 0x1c
CONFIG_DENSITY = 0x0100
CONFIG_VERSION = 0x0400


def _config(density=0, sdk=0):
    """ResTable_config (64 bytes): only size, density and sdkVersion are set."""
    c = bytearray(64)
    struct.pack_into("<I", c, 0, 64)
    struct.pack_into("<H", c, 14, density)   # screenType.density
    struct.pack_into("<H", c, 24, sdk)       # version.sdkVersion
    return bytes(c)


def encode_arsc(package, pkg_id, types):
    """types: list of (type_name, [(entry_name, kind, value, (density, sdk))]);
    kind 'file' (value = path inside the apk) or 'color' (value = 0xAARRGGBB).
    Returns (bytes, {(type_name, entry_name): resource_id})."""
    global_strings = []
    for tname, entries in types:
        for (ename, kind, value, cfg) in entries:
            if kind in ("file", "string") and value not in global_strings:
                global_strings.append(value)
    type_names = [t for t, _ in types]
    key_names = []
    for tname, entries in types:
        for e in entries:
            if e[0] not in key_names:
                key_names.append(e[0])
    ids = {}
    pkg_body = bytearray()
    type_pool = string_pool(type_names)
    key_pool = string_pool(key_names)
    header_size = 288
    type_strings_off = header_size
    key_strings_off = header_size + len(type_pool)
    pkg_body += type_pool + key_pool
    for ti, (tname, entries) in enumerate(types):
        tid = ti + 1
        names = []
        for e in entries:
            if e[0] not in names:
                names.append(e[0])
        flags = []
        for n in names:
            f = 0
            for e in entries:
                if e[0] == n:
                    if e[3][0]:
                        f |= CONFIG_DENSITY
                    if e[3][1]:
                        f |= CONFIG_VERSION
            flags.append(f)
        spec = struct.pack("<HHIBBHI", RES_TABLE_TYPE_SPEC_TYPE, 16, 16 + 4 * len(names), tid, 0, 0, len(names))
        spec += struct.pack("<%dI" % len(names), *flags)
        pkg_body += spec
        by_cfg = {}
        for e in entries:
            by_cfg.setdefault(e[3], {})[e[0]] = e
        for cfg, emap in sorted(by_cfg.items()):
            offsets = []
            ent = bytearray()
            for n in names:
                if n not in emap:
                    offsets.append(0xFFFFFFFF)
                    continue
                offsets.append(len(ent))
                ename, kind, value, _ = emap[n]
                ent += struct.pack("<HHI", 8, 0, key_names.index(ename))
                if kind in ("file", "string"):
                    ent += struct.pack("<HBBI", 8, 0, TYPE_STRING, global_strings.index(value))
                elif kind == "color":
                    ent += struct.pack("<HBBI", 8, 0, TYPE_INT_COLOR_ARGB8, value & 0xFFFFFFFF)
                elif kind == "int":
                    ent += struct.pack("<HBBI", 8, 0, TYPE_INT_DEC, int(value) & 0xFFFFFFFF)
                elif kind == "bool":
                    ent += struct.pack("<HBBI", 8, 0, TYPE_INT_BOOLEAN,
                                       0xFFFFFFFF if value else 0)
                else:
                    raise ValueError("unsupported resource kind " + repr(kind))
            hsz = 8 + 4 + 4 + 4 + 64
            entries_start = hsz + 4 * len(names)
            chunk = struct.pack("<HHIBBHII", RES_TABLE_TYPE_TYPE, hsz, entries_start + len(ent), tid, 0, 0,
                                len(names), entries_start) + _config(*cfg)
            chunk += struct.pack("<%dI" % len(names), *offsets) + bytes(ent)
            pkg_body += chunk
        for i, n in enumerate(names):
            ids[(tname, n)] = (pkg_id << 24) | (tid << 16) | i
    name16 = package.encode("utf-16-le")[:254].ljust(256, b"\0")
    pkg_head = struct.pack("<HHII", RES_TABLE_PACKAGE_TYPE, header_size, header_size + len(pkg_body), pkg_id)
    pkg_head += name16
    pkg_head += struct.pack("<IIIII", type_strings_off, len(type_names), key_strings_off, len(key_names), 0)
    assert len(pkg_head) == header_size
    gpool = string_pool(global_strings)
    body = gpool + pkg_head + bytes(pkg_body)
    table = struct.pack("<HHII", RES_TABLE_TYPE, 12, 12 + len(body), 1) + body
    return table, ids


def decode_arsc(b):
    """Summarise a resources.arsc (self-check)."""
    t, hs, size, npkg = struct.unpack_from("<HHII", b, 0)
    assert t == RES_TABLE_TYPE and size == len(b)
    out = []
    p = hs
    gstr = []

    def pool(q):
        n, _, flags, sstart, _ = struct.unpack_from("<IIIII", b, q + 8)
        offs = struct.unpack_from("<%dI" % n, b, q + 28)
        res = []
        for o in offs:
            r = q + sstart + o
            (ln,) = struct.unpack_from("<H", b, r)
            res.append(b[r + 2:r + 2 + 2 * ln].decode("utf-16-le"))
        return res
    while p < len(b):
        ct, chs, csz = struct.unpack_from("<HHI", b, p)
        if ct == RES_STRING_POOL_TYPE:
            gstr = pool(p)
        elif ct == RES_TABLE_PACKAGE_TYPE:
            (pid,) = struct.unpack_from("<I", b, p + 8)
            name = b[p + 12:p + 268].decode("utf-16-le").rstrip("\0")
            ts, _, ks, _ = struct.unpack_from("<IIII", b, p + 268)
            tnames, knames = pool(p + ts), pool(p + ks)
            out.append("package 0x%02x %s types=%s keys=%s" % (pid, name, tnames, knames))
            q = p + chs
            while q < p + csz:
                ct2, chs2, csz2 = struct.unpack_from("<HHI", b, q)
                if ct2 == RES_TABLE_TYPE_TYPE:
                    tid, fl, _, cnt, est = struct.unpack_from("<BBHII", b, q + 8)
                    dens, = struct.unpack_from("<H", b, q + 20 + 14)
                    sdk, = struct.unpack_from("<H", b, q + 20 + 24)
                    offs = struct.unpack_from("<%dI" % cnt, b, q + chs2)
                    for i, o in enumerate(offs):
                        if o == 0xFFFFFFFF:
                            continue
                        e = q + est + o
                        esz, efl, key = struct.unpack_from("<HHI", b, e)
                        vs, _, vt, vd = struct.unpack_from("<HBBI", b, e + esz)
                        val = gstr[vd] if vt == TYPE_STRING else "#%08x" % vd
                        out.append("  0x%02x%02x%04x %s/%s density=%d sdk=%d -> %s" % (
                            pid, tid, i, tnames[tid - 1], knames[key], dens, sdk, val))
                q += csz2
        p += csz
    return "\n".join(out)


# ------------------------------------------------------------------ PNG
def png_encode(width, height, rgba_rows):
    """rgba_rows: list of bytes objects (width*4 each)."""
    raw = b"".join(b"\0" + r for r in rgba_rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# 5x7 bitmap font for icon letters (A-Z, 0-9)
FONT = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01111 10000 10000 10000 10000 10000 01111", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01111 10000 10000 10011 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "11111 00100 00100 00100 00100 00100 11111", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10011 10101 10101 10101 11001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00110 01000 10000 11111", "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "01110 10000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00001 01110",
}


def make_icon(size, bg, fg, letter):
    """Round launcher icon: filled circle in bg colour with a letter in fg colour, antialiased."""
    glyph = FONT.get(letter.upper(), FONT["A"]).split()
    rows = []
    r = size / 2.0
    cx = cy = r
    gw, gh = 5, 7
    cell = size * 0.085
    gx0 = cx - gw * cell / 2
    gy0 = cy - gh * cell / 2
    ss = 4  # supersampling
    for y in range(size):
        row = bytearray()
        for x in range(size):
            cov_bg = cov_fg = 0
            for sy in range(ss):
                for sx in range(ss):
                    px = x + (sx + 0.5) / ss
                    py = y + (sy + 0.5) / ss
                    if (px - cx) ** 2 + (py - cy) ** 2 <= (r - 0.5) ** 2:
                        cov_bg += 1
                        gx = int(math.floor((px - gx0) / cell))
                        gy = int(math.floor((py - gy0) / cell))
                        if 0 <= gx < gw and 0 <= gy < gh and glyph[gy][gx] == "1":
                            cov_fg += 1
            n = ss * ss
            a = cov_bg / n
            if a == 0:
                row += b"\0\0\0\0"
                continue
            f = cov_fg / max(cov_bg, 1)
            col = [int(bg[i] * (1 - f) + fg[i] * f) for i in range(3)]
            row += bytes(col + [int(round(255 * a))])
        rows.append(bytes(row))
    return png_encode(size, size, rows)


def make_foreground(size, fg, letter):
    """Adaptive-icon foreground layer (108dp canvas): transparent with a centred glyph
    kept inside the 66dp safe zone."""
    glyph = FONT.get(letter.upper(), FONT["A"]).split()
    gw, gh = 5, 7
    cell = size * 0.052
    gx0 = size / 2.0 - gw * cell / 2
    gy0 = size / 2.0 - gh * cell / 2
    ss = 3
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            cov = 0
            for sy in range(ss):
                for sx in range(ss):
                    px = x + (sx + 0.5) / ss
                    py = y + (sy + 0.5) / ss
                    gx = int(math.floor((px - gx0) / cell))
                    gy = int(math.floor((py - gy0) / cell))
                    if 0 <= gx < gw and 0 <= gy < gh and glyph[gy][gx] == "1":
                        cov += 1
            a = cov / (ss * ss)
            row += bytes([fg[0], fg[1], fg[2], int(round(255 * a))]) if a else b"\0\0\0\0"
        rows.append(bytes(row))
    return png_encode(size, size, rows)
