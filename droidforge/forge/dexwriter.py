"""DEX file writer (Dalvik Executable format, version 035), from the spec.

Takes a list of DexClass objects whose methods carry Dalvik IR (see dalvik.py),
builds the sorted constant pools, lays out every section and writes a file with
correct checksum (Adler-32) and signature (SHA-1).
"""
import hashlib
import struct
import zlib

from . import dalvik
from .classfile import encode_mutf8, to_code_units

NO_INDEX = 0xFFFFFFFF

ACC_CONSTRUCTOR = 0x10000
ACC_DECLARED_SYNCHRONIZED = 0x20000


class DexField:
    def __init__(self, cls, name, type_, access, static_value=None):
        self.cls, self.name, self.type, self.access = cls, name, type_, access
        self.static_value = static_value  # python value or None

    @property
    def key(self):
        return (self.cls, self.name, self.type)


class DexCode:
    def __init__(self, registers, ins, outs, items, tries=(), lines=()):
        self.registers = registers
        self.ins = ins
        self.outs = outs
        self.items = items          # list of dalvik.Insn / dalvik.Label
        self.tries = list(tries)    # list of dalvik.TryRegion
        self.lines = list(lines)    # list of (Label, line)


class DexMethod:
    def __init__(self, cls, name, params, ret, access, code=None):
        self.cls, self.name, self.params, self.ret = cls, name, tuple(params), ret
        self.access = access
        self.code = code

    @property
    def key(self):
        return (self.cls, self.name, self.params, self.ret)

    @property
    def is_direct(self):
        return bool(self.access & (0x0008 | 0x0002 | ACC_CONSTRUCTOR))


class DexClass:
    def __init__(self, desc, access, super_desc, interfaces=(), source_file=None):
        self.desc = desc
        self.access = access
        self.super = super_desc
        self.interfaces = list(interfaces)
        self.source_file = source_file
        self.fields = []
        self.methods = []


def uleb(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def sleb(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if (v == 0 and not b & 0x40) or (v == -1 and b & 0x40):
            out.append(b)
            return bytes(out)
        out.append(b | 0x80)


def shorty_char(t):
    return "L" if t[0] in "L[" else t


def shorty(ret, params):
    return shorty_char(ret) + "".join(shorty_char(p) for p in params)


def sort_class_defs(classes):
    by_desc = {c.desc: c for c in classes}
    done, out, visiting = set(), [], set()

    def visit(c):
        if c.desc in done:
            return
        if c.desc in visiting:
            raise ValueError("class hierarchy cycle at " + c.desc)
        visiting.add(c.desc)
        for dep in [c.super] + c.interfaces:
            if dep in by_desc:
                visit(by_desc[dep])
        visiting.discard(c.desc)
        done.add(c.desc)
        out.append(c)

    for c in classes:
        visit(c)
    return out


class DexWriter:
    def __init__(self, classes, min_sdk=None):
        self.min_sdk = min_sdk
        self.classes = sort_class_defs(classes)
        seen = set()
        for c in self.classes:
            if c.desc in seen:
                raise ValueError("duplicate class " + c.desc)
            seen.add(c.desc)

    def version(self):
        """Like d8: 037 for minSdk 24+ (Android 7.0+); otherwise 035 unless interfaces carry code."""
        if self.min_sdk is not None and self.min_sdk >= 24:
            return "037"
        for c in self.classes:
            if c.access & 0x0200:
                for m in c.methods:
                    if m.code is not None and m.name != "<clinit>":
                        return "037"
        return "035"

    # ------------------------------------------------------------ collection
    def _collect(self):
        S, T, P, F, M = set(), set(), set(), set(), set()

        def typ(t):
            T.add(t)

        def proto(ret, params):
            P.add((ret, tuple(params)))
            typ(ret)
            for p in params:
                typ(p)

        def field(k):
            F.add(k)
            typ(k[0])
            typ(k[2])
            S.add(k[1])

        def method(k):
            M.add(k)
            typ(k[0])
            S.add(k[1])
            proto(k[3], k[2])

        for c in self.classes:
            typ(c.desc)
            if c.super:
                typ(c.super)
            for i in c.interfaces:
                typ(i)
            if c.source_file:
                S.add(c.source_file)
            for f in c.fields:
                field(f.key)
                if isinstance(f.static_value, str):
                    S.add(f.static_value)
            for m in c.methods:
                method(m.key)
                code = m.code
                if code is None:
                    continue
                for it in code.items:
                    if not isinstance(it, dalvik.Insn):
                        continue
                    kind = dalvik.REF_KIND.get(it.op)
                    if kind is None:
                        continue
                    ref = it.args[-1]
                    if kind == "string":
                        S.add(ref)
                    elif kind == "type":
                        typ(ref)
                    elif kind == "field":
                        field(ref)
                    elif kind == "method":
                        method(ref)
                for tr in code.tries:
                    for t, _ in tr.handlers:
                        typ(t)
        for t in T:
            S.add(t)
        for (ret, params) in P:
            S.add(shorty(ret, params))
        self.strings = sorted(to_code_units(s) for s in S)
        self.sidx = {s: i for i, s in enumerate(self.strings)}
        self.types = sorted(T, key=lambda t: self.sidx[to_code_units(t)])
        self.tidx = {t: i for i, t in enumerate(self.types)}
        self.protos = sorted(P, key=lambda p: (self.tidx[p[0]], [self.tidx[x] for x in p[1]]))
        self.pidx = {p: i for i, p in enumerate(self.protos)}
        self.fields = sorted(F, key=lambda k: (self.tidx[k[0]], self.sidx[to_code_units(k[1])], self.tidx[k[2]]))
        self.fidx = {k: i for i, k in enumerate(self.fields)}
        self.methods = sorted(M, key=lambda k: (self.tidx[k[0]], self.sidx[to_code_units(k[1])],
                                                self.pidx[(k[3], k[2])]))
        self.midx = {k: i for i, k in enumerate(self.methods)}
        if len(self.types) > 0xFFFF:
            raise ValueError("too many types for one dex (%d)" % len(self.types))
        if len(self.methods) > 0xFFFF:
            raise ValueError("too many method references for one dex (%d > 65535)" % len(self.methods))
        if len(self.fields) > 0xFFFF:
            raise ValueError("too many field references for one dex (%d > 65535)" % len(self.fields))

    def index_of(self, kind, ref):
        if kind == "string":
            return self.sidx[to_code_units(ref)]
        if kind == "type":
            return self.tidx[ref]
        if kind == "field":
            return self.fidx[ref]
        if kind == "method":
            return self.midx[ref]
        raise KeyError(kind)

    # ------------------------------------------------------------ encoding
    def _encoded_value(self, ftype, v):
        def intval(vt, x, size):
            b = (x & ((1 << (8 * size)) - 1)).to_bytes(size, "little")
            # minimal sign-extended length
            while len(b) > 1:
                last, prev = b[-1], b[-2]
                if (last == 0 and prev < 0x80) or (last == 0xFF and prev >= 0x80):
                    b = b[:-1]
                else:
                    break
            return bytes([((len(b) - 1) << 5) | vt]) + b

        def uval(vt, x):
            b = x.to_bytes(max(1, (x.bit_length() + 7) // 8), "little")
            return bytes([((len(b) - 1) << 5) | vt]) + b

        def rightzext(vt, bits, size):  # floats: drop low-order zero bytes
            b = bits.to_bytes(size, "little")
            while len(b) > 1 and b[0] == 0:
                b = b[1:]
            return bytes([((len(b) - 1) << 5) | vt]) + b

        if ftype == "Z":
            return bytes([(1 if v else 0) << 5 | 0x1F])
        if ftype == "B":
            return intval(0x00, v or 0, 1)
        if ftype == "S":
            return intval(0x02, v or 0, 2)
        if ftype == "C":
            return uval(0x03, (v or 0) & 0xFFFF)
        if ftype == "I":
            return intval(0x04, v or 0, 4)
        if ftype == "J":
            return intval(0x06, v or 0, 8)
        if ftype == "F":
            return rightzext(0x10, v or 0, 4)
        if ftype == "D":
            return rightzext(0x11, v or 0, 8)
        # reference
        if v is None:
            return bytes([0x1E])
        if isinstance(v, str) and ftype == "Ljava/lang/String;":
            return uval(0x17, self.sidx[to_code_units(v)])
        raise ValueError("cannot encode static value %r for %s" % (v, ftype))

    def _debug_info(self, m, code, addr_of):
        entries = sorted((addr_of(lbl), line) for lbl, line in code.lines)
        # dedupe per address (keep first)
        uniq = []
        for a, l in entries:
            if uniq and uniq[-1][0] == a:
                continue
            if uniq and uniq[-1][1] == l:
                continue
            uniq.append((a, l))
        if not uniq:
            return None
        out = bytearray()
        start_line = max(1, uniq[0][1])
        out += uleb(start_line)
        out += uleb(len(m.params))
        for _ in m.params:
            out += uleb(0)  # uleb128p1 NO_INDEX -> 0
        addr, line = 0, start_line
        for a, l in uniq:
            da, dl = a - addr, l - line
            if da:
                out.append(0x01)
                out += uleb(da)
            if not (-4 <= dl <= 10):
                out.append(0x02)
                out += sleb(dl)
                dl = 0
            out.append(0x0A + (dl + 4))  # special opcode, address delta 0
            addr, line = a, l
        out.append(0x00)
        return bytes(out)

    # ------------------------------------------------------------ layout
    def write(self):
        self._collect()
        # assemble all code up front (needs pool indices)
        asm = {}
        for c in self.classes:
            for m in c.methods:
                if m.code is not None:
                    units = dalvik.assemble(m.code.items, self.index_of)
                    asm[id(m)] = units

        n_str, n_typ, n_pro, n_fld, n_met, n_cls = (len(self.strings), len(self.types), len(self.protos),
                                                     len(self.fields), len(self.methods), len(self.classes))
        off = 0x70
        string_ids_off = off
        off += 4 * n_str
        type_ids_off = off
        off += 4 * n_typ
        proto_ids_off = off
        off += 12 * n_pro
        field_ids_off = off
        off += 8 * n_fld
        method_ids_off = off
        off += 8 * n_met
        class_defs_off = off
        off += 32 * n_cls
        data_off = off

        data = bytearray()
        map_items = []  # (type, count, offset)

        def pos():
            return data_off + len(data)

        def align4():
            while (data_off + len(data)) % 4:
                data.append(0)

        # --- type lists
        type_lists = {}
        wanted = []
        for p in self.protos:
            if p[1]:
                wanted.append(p[1])
        for c in self.classes:
            if c.interfaces:
                wanted.append(tuple(c.interfaces))
        align4()
        tl_start, tl_count = pos(), 0
        for tl in wanted:
            if tl in type_lists:
                continue
            align4()
            type_lists[tl] = pos()
            data += struct.pack("<I", len(tl))
            for t in tl:
                data += struct.pack("<H", self.tidx[t])
            tl_count += 1
        if tl_count:
            map_items.append((0x1001, tl_count, tl_start))

        # --- code items (+ debug info written afterwards)
        align4()
        code_off = {}
        code_start, code_count = pos(), 0
        debug_blobs = []  # (method, blob, patch position)
        for c in self.classes:
            for m in c.methods:
                if m.code is None:
                    continue
                align4()
                code_off[id(m)] = pos()
                code_count += 1
                code = m.code
                units = asm[id(m)]
                label_addr = lambda l: l.pos
                tries = []
                for tr in code.tries:
                    s, e = tr.start.pos, tr.end.pos
                    if e <= s:
                        continue
                    tries.append((s, e - s, tuple((self.tidx[t], h.pos) for t, h in tr.handlers),
                                  tr.catch_all.pos if tr.catch_all else None))
                tries.sort()
                for a, b in zip(tries, tries[1:]):
                    if a[0] + a[1] > b[0]:
                        raise ValueError("overlapping try ranges in %s.%s" % (m.cls, m.name))
                data += struct.pack("<HHHHII", code.registers, code.ins, code.outs, len(tries), 0, len(units))
                dbg_patch = len(data) - 8
                data += struct.pack("<%dH" % len(units), *units)
                if tries:
                    if len(units) % 2:
                        data += b"\0\0"
                    # handlers
                    hl = bytearray()
                    hoff = {}
                    uniq_h = []
                    for t in tries:
                        key = (t[2], t[3])
                        if key not in hoff:
                            hoff[key] = None
                            uniq_h.append(key)
                    hl += uleb(len(uniq_h))
                    for key in uniq_h:
                        hoff[key] = len(hl)
                        typed, ca = key
                        hl += sleb(-len(typed) if ca is not None else len(typed))
                        for ti, addr in typed:
                            hl += uleb(ti) + uleb(addr)
                        if ca is not None:
                            hl += uleb(ca)
                    for t in tries:
                        data += struct.pack("<IHH", t[0], t[1], hoff[(t[2], t[3])])
                    data += hl
                if code.lines:
                    blob = self._debug_info(m, code, label_addr)
                    if blob:
                        debug_blobs.append((blob, dbg_patch))
        if code_count:
            map_items.append((0x2001, code_count, code_start))

        # --- debug info
        if debug_blobs:
            dstart = pos()
            for blob, patch in debug_blobs:
                struct.pack_into("<I", data, patch, pos())
                data += blob
            map_items.append((0x2003, len(debug_blobs), dstart))

        # --- class data
        class_data_off = {}
        cd_start, cd_count = pos(), 0
        for c in self.classes:
            sf = sorted([f for f in c.fields if f.access & 0x0008], key=lambda f: self.fidx[f.key])
            inf = sorted([f for f in c.fields if not f.access & 0x0008], key=lambda f: self.fidx[f.key])
            dm = sorted([m for m in c.methods if m.is_direct], key=lambda m: self.midx[m.key])
            vm = sorted([m for m in c.methods if not m.is_direct], key=lambda m: self.midx[m.key])
            c._static_fields = sf
            if not (sf or inf or dm or vm):
                continue
            class_data_off[c.desc] = pos()
            cd_count += 1
            data += uleb(len(sf)) + uleb(len(inf)) + uleb(len(dm)) + uleb(len(vm))
            for lst in (sf, inf):
                prev = 0
                for f in lst:
                    i = self.fidx[f.key]
                    data += uleb(i - prev) + uleb(f.access)
                    prev = i
            for lst in (dm, vm):
                prev = 0
                for m in lst:
                    i = self.midx[m.key]
                    data += uleb(i - prev) + uleb(m.access) + uleb(code_off.get(id(m), 0))
                    prev = i
        if cd_count:
            map_items.append((0x2000, cd_count, cd_start))

        # --- string data
        str_data_off = []
        sd_start = pos()
        for s in self.strings:
            str_data_off.append(pos())
            data += uleb(len(s)) + encode_mutf8(s) + b"\0"
        if self.strings:
            map_items.append((0x2002, len(self.strings), sd_start))

        # --- static values (encoded arrays)
        static_off = {}
        ea_start, ea_count = pos(), 0
        for c in self.classes:
            sf = c._static_fields
            last = -1
            for i, f in enumerate(sf):
                if f.static_value is not None:
                    last = i
            if last < 0:
                continue
            static_off[c.desc] = pos()
            ea_count += 1
            data += uleb(last + 1)
            for f in sf[:last + 1]:
                data += self._encoded_value(f.type, f.static_value)
        if ea_count:
            map_items.append((0x2005, ea_count, ea_start))

        # --- map list
        align4()
        map_off = pos()
        head = [(0x0000, 1, 0)]
        for (t, n, o) in [(0x0001, n_str, string_ids_off), (0x0002, n_typ, type_ids_off),
                          (0x0003, n_pro, proto_ids_off), (0x0004, n_fld, field_ids_off),
                          (0x0005, n_met, method_ids_off), (0x0006, n_cls, class_defs_off)]:
            if n:
                head.append((t, n, o))
        all_items = head + sorted(map_items, key=lambda x: x[2]) + [(0x1000, 1, map_off)]
        data += struct.pack("<I", len(all_items))
        for t, n, o in all_items:
            data += struct.pack("<HHII", t, 0, n, o)
        file_size = data_off + len(data)

        # --- id sections
        out = bytearray(data_off)
        for i, o in enumerate(str_data_off):
            struct.pack_into("<I", out, string_ids_off + 4 * i, o)
        for i, t in enumerate(self.types):
            struct.pack_into("<I", out, type_ids_off + 4 * i, self.sidx[to_code_units(t)])
        for i, (ret, params) in enumerate(self.protos):
            struct.pack_into("<III", out, proto_ids_off + 12 * i, self.sidx[shorty(ret, params)],
                             self.tidx[ret], type_lists[params] if params else 0)
        for i, (c, n, t) in enumerate(self.fields):
            struct.pack_into("<HHI", out, field_ids_off + 8 * i, self.tidx[c], self.tidx[t],
                             self.sidx[to_code_units(n)])
        for i, (c, n, params, ret) in enumerate(self.methods):
            struct.pack_into("<HHI", out, method_ids_off + 8 * i, self.tidx[c], self.pidx[(ret, params)],
                             self.sidx[to_code_units(n)])
        for i, c in enumerate(self.classes):
            struct.pack_into("<IIIIIIII", out, class_defs_off + 32 * i,
                             self.tidx[c.desc], c.access,
                             self.tidx[c.super] if c.super else NO_INDEX,
                             type_lists[tuple(c.interfaces)] if c.interfaces else 0,
                             self.sidx[to_code_units(c.source_file)] if c.source_file else NO_INDEX,
                             0, class_data_off.get(c.desc, 0), static_off.get(c.desc, 0))
        # header
        out[0:8] = b"dex\n%s\0" % self.version().encode()
        struct.pack_into("<III", out, 32, file_size, 0x70, 0x12345678)
        struct.pack_into("<III", out, 44, 0, 0, map_off)
        struct.pack_into("<IIIIIIIIIIIIII", out, 56,
                         n_str, string_ids_off if n_str else 0,
                         n_typ, type_ids_off if n_typ else 0,
                         n_pro, proto_ids_off if n_pro else 0,
                         n_fld, field_ids_off if n_fld else 0,
                         n_met, method_ids_off if n_met else 0,
                         n_cls, class_defs_off if n_cls else 0,
                         len(data), data_off)
        blob = bytearray(out) + data
        assert len(blob) == file_size
        blob[12:32] = hashlib.sha1(blob[32:]).digest()
        struct.pack_into("<I", blob, 8, zlib.adler32(bytes(blob[12:])) & 0xFFFFFFFF)
        return bytes(blob)
