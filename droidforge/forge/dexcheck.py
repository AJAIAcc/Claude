"""Independent DEX parser + validator + disassembler.

Mirrors the important structural checks of ART's DexFileVerifier and a
simplified version of the bytecode verifier (register categories), so broken
output is caught here instead of on the phone.
"""
import hashlib
import struct
import sys
import zlib

from . import dalvik as D
from .classfile import decode_mutf8


class DexError(Exception):
    pass


def read_uleb(b, p):
    v = shift = 0
    while True:
        x = b[p]
        p += 1
        v |= (x & 0x7F) << shift
        shift += 7
        if not x & 0x80:
            return v, p


def read_sleb(b, p):
    v = shift = 0
    while True:
        x = b[p]
        p += 1
        v |= (x & 0x7F) << shift
        shift += 7
        if not x & 0x80:
            if x & 0x40:
                v -= 1 << shift
            return v, p


class CodeItem:
    pass


class DexFile:
    def __init__(self, data, strict=True):
        self.b = b = bytes(data)
        self.errors = []
        if b[:4] != b"dex\n" or b[7] != 0:
            raise DexError("bad magic")
        self.version = b[4:7].decode()
        (self.checksum,) = struct.unpack_from("<I", b, 8)
        if zlib.adler32(b[12:]) & 0xFFFFFFFF != self.checksum:
            self.err("checksum mismatch")
        if hashlib.sha1(b[32:]).digest() != b[12:32]:
            self.err("signature mismatch")
        (fsize, hsize, endian) = struct.unpack_from("<III", b, 32)
        if fsize != len(b):
            self.err("file_size %d != actual %d" % (fsize, len(b)))
        if hsize != 0x70 or endian != 0x12345678:
            self.err("bad header size / endian tag")
        (link_size, link_off, self.map_off) = struct.unpack_from("<III", b, 44)
        h = struct.unpack_from("<14I", b, 56)
        (ns, so, nt, to, np_, po, nf, fo, nm, mo, nc, co, dsize, doff) = h
        self.data_off, self.data_size = doff, dsize
        for (n, o, nm_) in [(ns, so, "string_ids"), (nt, to, "type_ids"), (np_, po, "proto_ids"),
                            (nf, fo, "field_ids"), (nm, mo, "method_ids"), (nc, co, "class_defs")]:
            if n == 0 and o != 0:
                self.err("%s: size 0 but offset %d" % (nm_, o))
            if o % 4:
                self.err("%s offset not 4-aligned" % nm_)
        if doff + dsize != len(b):
            self.err("data section does not end at file end")
        if dsize % 4:
            self.err("data_size not multiple of 4")
        self.strings = []
        for i in range(ns):
            (off,) = struct.unpack_from("<I", b, so + 4 * i)
            n16, p = read_uleb(b, off)
            e = b.index(b"\0", p)
            s = decode_mutf8(b[p:e])
            if len(s) != n16:
                self.err("string %d utf16 length mismatch" % i)
            self.strings.append(s)
        for i in range(1, ns):
            if not self.strings[i - 1] < self.strings[i]:
                self.err("string_ids not sorted/unique at %d (%r, %r)" % (i, self.strings[i - 1], self.strings[i]))
        self.types = []
        prev = -1
        for i in range(nt):
            (si,) = struct.unpack_from("<I", b, to + 4 * i)
            if si <= prev:
                self.err("type_ids not sorted at %d" % i)
            prev = si
            t = self.strings[si]
            self._check_desc(t)
            self.types.append(t)
        self.protos = []
        for i in range(np_):
            (shi, rti, poff) = struct.unpack_from("<III", b, po + 12 * i)
            params = self.type_list(poff)
            ret = self.types[rti]
            sh = self.strings[shi]
            exp = "".join(("L" if t[0] in "L[" else t) for t in [ret] + params)
            if sh != exp:
                self.err("proto %d shorty %s != %s" % (i, sh, exp))
            self.protos.append((ret, tuple(params), rti, tuple(self.types.index(p) for p in params)))
        for i in range(1, np_):
            a, c = self.protos[i - 1], self.protos[i]
            if not (a[2], list(a[3])) < (c[2], list(c[3])):
                self.err("proto_ids not sorted at %d" % i)
        self.fields = []
        for i in range(nf):
            (ci, ti, ni) = struct.unpack_from("<HHI", b, fo + 8 * i)
            self.fields.append((self.types[ci], self.strings[ni], self.types[ti], (ci, ni, ti)))
        for i in range(1, nf):
            if not self.fields[i - 1][3] < self.fields[i][3]:
                self.err("field_ids not sorted at %d" % i)
        self.methods = []
        for i in range(nm):
            (ci, pi, ni) = struct.unpack_from("<HHI", b, mo + 8 * i)
            self.methods.append((self.types[ci], self.strings[ni], self.protos[pi], (ci, ni, pi)))
        for i in range(1, nm):
            if not self.methods[i - 1][3] < self.methods[i][3]:
                self.err("method_ids not sorted at %d" % i)
        self.classes = []
        defined = set()
        for i in range(nc):
            (ci, acc, sup, ioff, sf, aoff, cdoff, svoff) = struct.unpack_from("<8I", b, co + 32 * i)
            c = {"desc": self.types[ci], "access": acc,
                 "super": None if sup == 0xFFFFFFFF else self.types[sup],
                 "interfaces": self.type_list(ioff),
                 "source": None if sf == 0xFFFFFFFF else self.strings[sf],
                 "static_fields": [], "instance_fields": [], "direct": [], "virtual": [],
                 "static_values": self.encoded_array(svoff) if svoff else []}
            if acc & ~0x7611:
                self.err("class %s has invalid access flags 0x%x" % (c["desc"], acc))
            for dep in ([c["super"]] if c["super"] else []) + c["interfaces"]:
                if dep in self.all_class_descs_after(i, co, nc):
                    self.err("class %s defined before its supertype %s" % (c["desc"], dep))
            if cdoff:
                p = cdoff
                cnt = []
                for _ in range(4):
                    v, p = read_uleb(b, p)
                    cnt.append(v)
                for kind_i, key in enumerate(["static_fields", "instance_fields"]):
                    idx = 0
                    for j in range(cnt[kind_i]):
                        dlt, p = read_uleb(b, p)
                        fa, p = read_uleb(b, p)
                        if j and dlt == 0:
                            self.err("duplicate field in %s" % c["desc"])
                        idx += dlt
                        c[key].append((self.fields[idx], fa))
                for kind_i, key in enumerate(["direct", "virtual"]):
                    idx = 0
                    for j in range(cnt[2 + kind_i]):
                        dlt, p = read_uleb(b, p)
                        ma, p = read_uleb(b, p)
                        coff, p = read_uleb(b, p)
                        if j and dlt == 0:
                            self.err("duplicate method in %s" % c["desc"])
                        idx += dlt
                        m = self.methods[idx]
                        if m[0] != c["desc"]:
                            self.err("method %s listed in class %s" % (m[1], c["desc"]))
                        code = self.code_item(coff, m) if coff else None
                        self._check_method_flags(c, m, ma, key == "direct", code)
                        c[key].append((m, ma, code))
            self.classes.append(c)
            defined.add(c["desc"])
        self._check_map()

    def all_class_descs_after(self, i, co, nc):
        out = set()
        for j in range(i + 1, nc):
            (ci,) = struct.unpack_from("<I", self.b, co + 32 * j)
            out.add(self.types[ci])
        return out

    def err(self, msg):
        self.errors.append(msg)

    def _check_desc(self, t):
        i = 0
        while i < len(t) and t[i] == "[":
            i += 1
        rest = t[i:]
        ok = rest in ("Z", "B", "S", "C", "I", "J", "F", "D") or (rest == "V" and i == 0) or \
            (len(rest) > 2 and rest[0] == "L" and rest[-1] == ";" and ";" not in rest[1:-1]
             and "." not in rest and "//" not in rest)
        if not ok:
            self.err("invalid type descriptor %r" % t)

    def type_list(self, off):
        if not off:
            return []
        if off % 4:
            self.err("type_list misaligned")
        (n,) = struct.unpack_from("<I", self.b, off)
        return [self.types[x] for x in struct.unpack_from("<%dH" % n, self.b, off + 4)]

    def encoded_array(self, off):
        n, p = read_uleb(self.b, off)
        vals = []
        for _ in range(n):
            v, p = self.encoded_value(p)
            vals.append(v)
        return vals

    def encoded_value(self, p):
        b = self.b
        h = b[p]
        p += 1
        vt, arg = h & 0x1F, h >> 5
        if vt == 0x1E:
            return ("null", None), p
        if vt == 0x1F:
            return ("boolean", bool(arg)), p
        size = arg + 1
        raw = b[p:p + size]
        p += size
        if vt in (0x00, 0x02, 0x04, 0x06):
            v = int.from_bytes(raw, "little", signed=True)
            return ({0: "byte", 2: "short", 4: "int", 6: "long"}[vt], v), p
        if vt == 0x03:
            return ("char", int.from_bytes(raw, "little")), p
        if vt == 0x10:
            bits = int.from_bytes(raw.rjust(4, b"\0"), "little") if False else \
                int.from_bytes(b"\0" * (4 - size) + raw, "little")
            return ("float", struct.unpack("<f", struct.pack("<I", bits))[0]), p
        if vt == 0x11:
            bits = int.from_bytes(b"\0" * (8 - size) + raw, "little")
            return ("double", struct.unpack("<d", struct.pack("<Q", bits))[0]), p
        if vt == 0x17:
            return ("string", self.strings[int.from_bytes(raw, "little")]), p
        if vt == 0x18:
            return ("type", self.types[int.from_bytes(raw, "little")]), p
        raise DexError("unsupported encoded value type 0x%x" % vt)

    def _check_method_flags(self, c, m, acc, direct, code):
        name = m[1]
        is_ctor = name in ("<init>", "<clinit>")
        if bool(acc & 0x10000) != is_ctor:
            self.err("%s.%s: constructor flag mismatch" % (c["desc"], name))
        if name == "<clinit>" and not acc & 0x8:
            self.err("<clinit> not static in " + c["desc"])
        is_direct = bool(acc & (0x8 | 0x2)) or is_ctor
        if is_direct != direct:
            self.err("%s.%s in wrong method list" % (c["desc"], name))
        if acc & 0x20 and not acc & 0x100:
            self.err("%s.%s: ACC_SYNCHRONIZED on non-native method" % (c["desc"], name))
        needs_code = not acc & (0x400 | 0x100)
        if needs_code != (code is not None):
            self.err("%s.%s: code presence mismatch" % (c["desc"], name))
        if c["access"] & 0x200 and not is_ctor and not acc & 0x400 and self.version < "037":
            self.err("%s.%s: non-abstract instance method in interface (needs dex 037)" % (c["desc"], name))
        if code is not None:
            ret, params = m[2][0], m[2][1]
            ins = sum(2 if p in ("J", "D") else 1 for p in params) + (0 if acc & 0x8 else 1)
            if code.ins != ins:
                self.err("%s.%s: ins_size %d != %d" % (c["desc"], name, code.ins, ins))
            self.verify_code(c, m, acc, code)

    def code_item(self, off, m):
        b = self.b
        if off % 4:
            self.err("code_item misaligned")
        ci = CodeItem()
        (ci.regs, ci.ins, ci.outs, ntries, ci.dbg, n) = struct.unpack_from("<HHHHII", b, off)
        ci.units = list(struct.unpack_from("<%dH" % n, b, off + 16))
        p = off + 16 + 2 * n
        ci.tries = []
        ci.handlers = {}
        if ntries:
            if n % 2:
                p += 2
            raw = []
            for i in range(ntries):
                raw.append(struct.unpack_from("<IHH", b, p))
                p += 8
            hbase = p
            for (start, cnt, hoff) in raw:
                q = hbase + hoff
                sz, q = read_sleb(b, q)
                hl = []
                for _ in range(abs(sz)):
                    ti, q = read_uleb(b, q)
                    addr, q = read_uleb(b, q)
                    hl.append((self.types[ti], addr))
                ca = None
                if sz <= 0:
                    ca, q = read_uleb(b, q)
                ci.tries.append((start, cnt, hl, ca))
        if ci.ins > ci.regs:
            self.err("%s.%s: ins_size > registers_size" % (m[0], m[1]))
        ci.lines = []
        if ci.dbg:
            q = ci.dbg
            line, q = read_uleb(b, q)
            np_, q = read_uleb(b, q)
            for _ in range(np_):
                _, q = read_uleb(b, q)
            addr = 0
            while True:
                opb = b[q]
                q += 1
                if opb == 0:
                    break
                if opb == 1:
                    v, q = read_uleb(b, q)
                    addr += v
                elif opb == 2:
                    v, q = read_sleb(b, q)
                    line += v
                elif opb >= 0x0a:
                    adj = opb - 0x0a
                    line += -4 + adj % 15
                    addr += adj // 15
                    ci.lines.append((addr, line))
                else:
                    raise DexError("unsupported debug opcode %d" % opb)
        return ci

    # ---------------------------------------------------------------- bytecode
    def insns(self, ci):
        """Yield (addr, op, name, fmt, size, F) for the instruction stream (payloads included)."""
        i = 0
        out = []
        while i < len(ci.units):
            op, name, fmt, size, F = D.decode(ci.units, i)
            out.append((i, op, name, fmt, size, F))
            i += size
        if i != len(ci.units):
            raise DexError("instruction runs past end of code")
        return out

    def describe(self, op, F):
        k = D.REF_KIND.get(op)
        if k is None:
            return ""
        idx = F["B"] if "B" in F and D.OPS[op][1] != "22c" else F.get("C")
        if D.OPS[op][1] in ("35c", "3rc"):
            idx = F["B"]
        try:
            if k == "string":
                return repr(self.strings[idx])
            if k == "type":
                return self.types[idx]
            if k == "field":
                f = self.fields[idx]
                return "%s->%s:%s" % f[:3]
            m = self.methods[idx]
            return "%s->%s(%s)%s" % (m[0], m[1], "".join(m[2][1]), m[2][0])
        except IndexError:
            return "<bad %s index %d>" % (k, idx)

    def verify_code(self, c, m, acc, ci):
        where = "%s.%s" % (c["desc"], m[1])
        try:
            ins = self.insns(ci)
        except Exception as e:  # noqa
            self.err("%s: decode error: %s" % (where, e))
            return
        starts = {a for (a, *_r) in ins if not _r[1].endswith("payload")}
        payloads = {a: n for (a, op, n, f, s, F) in ins if n.endswith("payload")}
        regs = ci.regs
        prev = None
        for (a, op, name, fmt, size, F) in ins:
            if name.endswith("payload"):
                if a % 2:
                    self.err("%s: payload at odd address %d" % (where, a))
                prev = None
                continue
            used = []
            if fmt in ("35c", "3rc"):
                used = F["regs"]
            else:
                for key in ("A", "B", "C"):
                    if key in F and self._is_reg(fmt, key):
                        used.append(F[key])
            wide_regs = self._wide_operands(name, F, fmt)
            for r in used + [r + 1 for r in wide_regs]:
                if r >= regs:
                    self.err("%s@%d %s: register v%d >= registers_size %d" % (where, a, name, r, regs))
            if fmt in ("10t", "20t", "30t", "21t", "22t"):
                off = F["A"] if fmt in ("10t", "20t", "30t") else (F["B"] if fmt == "21t" else F["C"])
                if a + off not in starts:
                    self.err("%s@%d %s: branch target %d not an instruction" % (where, a, name, a + off))
            if fmt == "31t":
                t = a + F["B"]
                if t not in payloads:
                    self.err("%s@%d: payload target %d missing" % (where, a, t))
                else:
                    want = {"packed-switch": "packed-switch-payload", "sparse-switch": "sparse-switch-payload",
                            "fill-array-data": "fill-array-data-payload"}[name]
                    if payloads[t] != want:
                        self.err("%s@%d: payload kind mismatch" % (where, a))
                    else:
                        for tgt in self.switch_targets(ci, t, a):
                            if tgt not in starts:
                                self.err("%s@%d: switch target %d invalid" % (where, a, tgt))
            if name.startswith("move-result"):
                if prev is None or not (prev.startswith("invoke") or prev.startswith("filled-new-array")):
                    self.err("%s@%d: %s not after invoke" % (where, a, name))
            if fmt in ("35c", "3rc") and name.startswith("invoke"):
                mref = self.methods[F["B"]]
                pw = sum(2 if p in ("J", "D") else 1 for p in mref[2][1]) + (0 if "static" in name else 1)
                if pw != F["count"]:
                    self.err("%s@%d %s: arg words %d != %d for %s" % (where, a, name, F["count"], pw, mref[1]))
                if F["count"] > ci.outs:
                    self.err("%s@%d: outs_size %d < %d" % (where, a, ci.outs, F["count"]))
            k = D.REF_KIND.get(op)
            if k:
                idx = F["B"] if fmt in ("21c", "31c", "35c", "3rc") else F["C"]
                lim = {"string": len(self.strings), "type": len(self.types), "field": len(self.fields),
                       "method": len(self.methods)}[k]
                if idx >= lim:
                    self.err("%s@%d: %s index out of range" % (where, a, k))
            prev = name
        handler_addrs = set()
        last_end = -1
        for (start, cnt, hl, ca) in ci.tries:
            if start < last_end:
                self.err("%s: try items overlap/unsorted" % where)
            last_end = start + cnt
            if start not in starts or (start + cnt not in starts and start + cnt != self._code_end(ins)):
                self.err("%s: try range [%d,%d) not on instruction boundaries" % (where, start, start + cnt))
            for (_, h) in hl:
                handler_addrs.add(h)
            if ca is not None:
                handler_addrs.add(ca)
        for h in handler_addrs:
            if h not in starts:
                self.err("%s: handler %d not an instruction" % (where, h))
        for (a, op, name, fmt, size, F) in ins:
            if name == "move-exception" and a not in handler_addrs:
                self.err("%s@%d: move-exception outside handler start" % (where, a))
        self.type_check(c, m, acc, ci, ins, where)

    def _code_end(self, ins):
        # end of real instructions (before payloads)
        end = 0
        for (a, op, name, fmt, size, F) in ins:
            if not name.endswith("payload"):
                end = a + size
        return end

    def switch_targets(self, ci, pa, base):
        u = ci.units
        n = u[pa + 1]
        out = []
        if u[pa] == 0x0100:
            for i in range(n):
                off = D.s32(u[pa + 4 + 2 * i] | (u[pa + 5 + 2 * i] << 16))
                out.append(base + off)
        else:
            for i in range(n):
                off = D.s32(u[pa + 2 + 2 * n + 2 * i] | (u[pa + 3 + 2 * n + 2 * i] << 16))
                out.append(base + off)
        return out

    @staticmethod
    def _is_reg(fmt, key):
        regs = {"12x": "AB", "11n": "A", "11x": "A", "22x": "AB", "21t": "A", "21s": "A", "21h": "A",
                "21c": "A", "23x": "ABC", "22b": "AB", "22t": "AB", "22s": "AB", "22c": "AB", "32x": "AB",
                "31i": "A", "31t": "A", "31c": "A", "51l": "A"}
        return key in regs.get(fmt, "")

    @staticmethod
    def _wide_operands(name, F, fmt):
        """registers that are the low half of a wide pair."""
        w = []
        if name.startswith(("move-wide", "move-result-wide", "return-wide", "const-wide")):
            w.append(F["A"])
            if name.startswith("move-wide"):
                w.append(F["B"])
        elif name in ("aget-wide", "aput-wide", "iget-wide", "iput-wide", "sget-wide", "sput-wide"):
            w.append(F["A"])
        elif name.endswith(("-long", "-double")) and fmt == "23x" and not name.startswith("cmp"):
            w += [F["A"], F["B"]]
            if not name.startswith(("shl", "shr", "ushr")):
                w.append(F["C"])
        elif name.startswith("cmp") and ("long" in name or "double" in name):
            w += [F["B"], F["C"]]
        return w

    # ---------------------------------------------------------------- type check
    def type_check(self, c, m, acc, ci, ins, where):
        """Register-category dataflow: u=undef i=32bit w/W=wide lo/hi r=ref z=zero-const."""
        regs = ci.regs
        by_addr = {a: (op, name, fmt, size, F) for (a, op, name, fmt, size, F) in ins
                   if not name.endswith("payload")}
        init = ["u"] * regs
        p = regs - ci.ins
        if not acc & 0x8:
            init[p] = "r"
            p += 1
        for t in m[2][1]:
            if t in ("J", "D"):
                init[p], init[p + 1] = "w", "W"
                p += 2
            else:
                init[p] = "r" if t[0] in "L[" else "i"
                p += 1
        handlers_at = {}
        for (start, cnt, hl, ca) in ci.tries:
            hs = [h for (_, h) in hl] + ([ca] if ca is not None else [])
            for a in by_addr:
                if start <= a < start + cnt:
                    handlers_at.setdefault(a, []).extend(hs)
        states = {0: init}
        work = [0]
        errs = set()

        def merge(x, y):
            if x == y:
                return x
            if {x, y} == {"z", "i"}:
                return "i"
            if {x, y} == {"z", "r"}:
                return "r"
            return "c"

        def flow(a, stt):
            if a not in by_addr:
                errs.add("%s: flow to non-instruction %d" % (where, a))
                return
            old = states.get(a)
            if old is None:
                states[a] = list(stt)
                work.append(a)
                return
            new = [merge(x, y) for x, y in zip(old, stt)]
            if new != old:
                states[a] = new
                work.append(a)

        ret = m[2][0]
        guard = 0
        while work:
            guard += 1
            if guard > 200000:
                break
            a = work.pop()
            s = list(states[a])
            op, name, fmt, size, F = by_addr[a]
            for h in handlers_at.get(a, []):
                hs = list(s)
                flow(h, hs)
            try:
                succ = self._tstep(a, op, name, fmt, size, F, s, ci, ret, where)
            except DexError as e:
                errs.add(str(e))
                continue
            for t in succ:
                flow(t, s)
        for e in sorted(errs):
            self.err(e)

    def _tstep(self, a, op, name, fmt, size, F, s, ci, ret, where):
        def need(r, cat):
            v = s[r]
            ok = {"i": v in ("i", "z"), "r": v in ("r", "z"), "w": v == "w" and s[r + 1] == "W"}[cat]
            if not ok:
                got = v if cat != "w" else v + s[r + 1]
                raise DexError("%s@%d %s: v%d expected %s got %s" % (where, a, name, r, cat, got))

        def put(r, cat):
            # writing clobbers any wide pair overlapping r
            if r > 0 and s[r - 1] == "w":
                s[r - 1] = "c"
            if cat == "w":
                if s[r + 1] == "w" and r + 2 < len(s):
                    s[r + 2] = "c"
                s[r], s[r + 1] = "w", "W"
            else:
                if s[r] == "w":
                    s[r + 1] = "c"
                s[r] = cat

        nxt = [a + size]
        A, B, C = F.get("A"), F.get("B"), F.get("C")
        cat_of = lambda t: "w" if t in ("J", "D") else ("r" if t[0] in "L[" else "i")
        if name == "nop":
            pass
        elif name.startswith("move") and not name.startswith(("move-result", "move-exception")):
            k = "w" if "wide" in name else ("r" if "object" in name else "i")
            if k == "i" and s[B] == "z":
                put(A, "z")
            elif k == "r" and s[B] == "z":
                put(A, "z")
            else:
                need(B, k)
                put(A, k)
        elif name.startswith("move-result"):
            k = "w" if "wide" in name else ("r" if "object" in name else "i")
            put(A, k)
        elif name == "move-exception":
            put(A, "r")
        elif name == "return-void":
            if ret != "V":
                raise DexError("%s@%d: return-void in non-void method" % (where, a))
            return []
        elif name in ("return", "return-wide", "return-object"):
            want = cat_of(ret) if ret != "V" else None
            k = {"return": "i", "return-wide": "w", "return-object": "r"}[name]
            if want != k:
                raise DexError("%s@%d: %s but method returns %s" % (where, a, name, ret))
            need(A, k)
            return []
        elif name.startswith("const-wide"):
            put(A, "w")
        elif name in ("const/4", "const/16", "const", "const/high16"):
            put(A, "z" if B == 0 else "i")
        elif name.startswith(("const-string", "const-class")):
            put(A, "r")
        elif name in ("monitor-enter", "monitor-exit", "throw"):
            need(A, "r")
            if name == "throw":
                return []
        elif name == "check-cast":
            need(A, "r")
        elif name == "instance-of":
            need(B, "r")
            put(A, "i")
        elif name == "array-length":
            need(B, "r")
            put(A, "i")
        elif name == "new-instance":
            put(A, "r")
        elif name == "new-array":
            need(B, "i")
            put(A, "r")
        elif name.startswith("goto"):
            return [a + A]
        elif name in ("packed-switch", "sparse-switch"):
            need(A, "i")
            return nxt + self.switch_targets(ci, a + B, a)
        elif name.startswith("cmp"):
            k = "w" if ("long" in name or "double" in name) else "i"
            need(B, k)
            need(C, k)
            put(A, "i")
        elif fmt == "22t":
            if s[A] in ("r",) or s[B] in ("r",):
                need(A, "r")
                need(B, "r")
            else:
                need(A, "i")
                need(B, "i")
            return nxt + [a + C]
        elif fmt == "21t":
            if s[A] not in ("i", "r", "z"):
                raise DexError("%s@%d %s: v%d undefined (%s)" % (where, a, name, A, s[A]))
            return nxt + [a + B]
        elif name.startswith(("aget", "aput")):
            need(B, "r")
            need(C, "i")
            k = "w" if "wide" in name else ("r" if "object" in name else "i")
            if name.startswith("aget"):
                put(A, k)
            else:
                need(A, k) if not (k in "ir" and s[A] == "z") else None
        elif name.startswith(("iget", "iput", "sget", "sput")):
            f = self.fields[C if fmt == "22c" else B]
            k = cat_of(f[2])
            if fmt == "22c":
                need(B, "r")
            if "get" in name:
                put(A, k)
            else:
                if not (k in "ir" and s[A] == "z"):
                    need(A, k)
            want = "w" if "wide" in name else ("r" if "object" in name else "i")
            if want != k:
                raise DexError("%s@%d: %s on field of type %s" % (where, a, name, f[2]))
        elif name.startswith("invoke"):
            mref = self.methods[B]
            regs = F["regs"]
            i = 0
            if "static" not in name:
                need(regs[0], "r")
                i = 1
            for t in mref[2][1]:
                k = cat_of(t)
                if k == "w":
                    need(regs[i], "w")
                    i += 2
                else:
                    if not s[regs[i]] == "z":
                        need(regs[i], k)
                    i += 1
        elif fmt == "12x" and ("-to-" in name or name.startswith(("neg", "not"))):
            src_t = name.split("-")[1] if name.startswith(("neg", "not")) else name.split("-to-")[0]
            dst_t = name.split("-")[1] if name.startswith(("neg", "not")) else name.split("-to-")[1]
            ks = "w" if src_t in ("long", "double") else "i"
            kd = "w" if dst_t in ("long", "double") else "i"
            need(B, ks)
            put(A, kd)
        elif fmt == "23x":
            t = name.split("-")[1]
            k = "w" if t in ("long", "double") else "i"
            need(B, k)
            need(C, "i" if name.split("-")[0] in ("shl", "shr", "ushr") else k)
            put(A, k)
        elif fmt == "12x" and name.endswith("/2addr"):
            t = name.split("-")[1].split("/")[0]
            k = "w" if t in ("long", "double") else "i"
            need(A, k)
            need(B, "i" if name.split("-")[0] in ("shl", "shr", "ushr") else k)
            put(A, k)
        elif fmt in ("22s", "22b"):
            need(B, "i")
            put(A, "i")
        else:
            raise DexError("%s@%d: type checker does not know %s" % (where, a, name))
        return nxt

    # ---------------------------------------------------------------- map
    def _check_map(self):
        b = self.b
        (n,) = struct.unpack_from("<I", b, self.map_off)
        items = [struct.unpack_from("<HHII", b, self.map_off + 4 + 12 * i) for i in range(n)]
        seen = set()
        prev = -1
        for (t, _, cnt, off) in items:
            if t in seen:
                self.err("map: duplicate type 0x%x" % t)
            seen.add(t)
            if off <= prev:
                self.err("map: items not in increasing offset order")
            prev = off
            if t >= 0x1000 and off < self.data_off:
                self.err("map: data item 0x%x before data section" % t)
        if items[0][0] != 0 or items[0][3] != 0:
            self.err("map: first item must be header")
        if 0x1000 not in seen:
            self.err("map: no map_list entry")

    # ---------------------------------------------------------------- dump
    def dump(self, out=sys.stdout):
        for c in self.classes:
            print("class %s extends %s implements %s  (0x%x)" % (c["desc"], c["super"], c["interfaces"],
                                                                   c["access"]), file=out)
            for (f, a) in c["static_fields"] + c["instance_fields"]:
                print("  field %s %s 0x%x" % (f[1], f[2], a), file=out)
            if c["static_values"]:
                print("  static values:", c["static_values"], file=out)
            for key in ("direct", "virtual"):
                for (m, a, ci) in c[key]:
                    print("  %s method %s(%s)%s 0x%x" % (key, m[1], "".join(m[2][1]), m[2][0], a), file=out)
                    if ci is None:
                        continue
                    print("    regs=%d ins=%d outs=%d" % (ci.regs, ci.ins, ci.outs), file=out)
                    for (a2, op, name, fmt, size, F) in self.insns(ci):
                        if name.endswith("payload"):
                            print("    %04x: %s" % (a2, name), file=out)
                            continue
                        args = ", ".join("%s=%s" % (k, v) for k, v in F.items())
                        print("    %04x: %-22s %s %s" % (a2, name, args, self.describe(op, F)), file=out)
                    for t in ci.tries:
                        print("    try %d..%d -> %s catchall=%s" % (t[0], t[0] + t[1], t[2], t[3]), file=out)


def main():
    data = open(sys.argv[1], "rb").read()
    d = DexFile(data)
    if "-d" in sys.argv:
        d.dump()
    if d.errors:
        print("%d ERRORS" % len(d.errors))
        for e in d.errors:
            print("  -", e)
        sys.exit(1)
    print("OK: %d classes, %d methods, %d strings" % (len(d.classes), len(d.methods), len(d.strings)))


if __name__ == "__main__":
    main()
