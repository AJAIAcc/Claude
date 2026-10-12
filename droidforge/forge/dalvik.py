"""Dalvik bytecode: opcode table, IR, assembler and disassembler.

Written from the Dalvik bytecode / instruction-format specification.
"""
import struct

# opcode -> (mnemonic, format)
OPS = {}


def _def(op, name, fmt):
    OPS[op] = (name, fmt)


_def(0x00, "nop", "10x")
for _o, _n, _f in [(1, "move", "12x"), (2, "move/from16", "22x"), (3, "move/16", "32x"),
                   (4, "move-wide", "12x"), (5, "move-wide/from16", "22x"), (6, "move-wide/16", "32x"),
                   (7, "move-object", "12x"), (8, "move-object/from16", "22x"), (9, "move-object/16", "32x"),
                   (0x0a, "move-result", "11x"), (0x0b, "move-result-wide", "11x"),
                   (0x0c, "move-result-object", "11x"), (0x0d, "move-exception", "11x"),
                   (0x0e, "return-void", "10x"), (0x0f, "return", "11x"), (0x10, "return-wide", "11x"),
                   (0x11, "return-object", "11x"), (0x12, "const/4", "11n"), (0x13, "const/16", "21s"),
                   (0x14, "const", "31i"), (0x15, "const/high16", "21h"), (0x16, "const-wide/16", "21s"),
                   (0x17, "const-wide/32", "31i"), (0x18, "const-wide", "51l"),
                   (0x19, "const-wide/high16", "21h"), (0x1a, "const-string", "21c"),
                   (0x1b, "const-string/jumbo", "31c"), (0x1c, "const-class", "21c"),
                   (0x1d, "monitor-enter", "11x"), (0x1e, "monitor-exit", "11x"),
                   (0x1f, "check-cast", "21c"), (0x20, "instance-of", "22c"), (0x21, "array-length", "12x"),
                   (0x22, "new-instance", "21c"), (0x23, "new-array", "22c"),
                   (0x24, "filled-new-array", "35c"), (0x25, "filled-new-array/range", "3rc"),
                   (0x26, "fill-array-data", "31t"), (0x27, "throw", "11x"), (0x28, "goto", "10t"),
                   (0x29, "goto/16", "20t"), (0x2a, "goto/32", "30t"), (0x2b, "packed-switch", "31t"),
                   (0x2c, "sparse-switch", "31t"), (0x2d, "cmpl-float", "23x"), (0x2e, "cmpg-float", "23x"),
                   (0x2f, "cmpl-double", "23x"), (0x30, "cmpg-double", "23x"), (0x31, "cmp-long", "23x")]:
    _def(_o, _n, _f)
for _i, _n in enumerate(["eq", "ne", "lt", "ge", "gt", "le"]):
    _def(0x32 + _i, "if-" + _n, "22t")
    _def(0x38 + _i, "if-%sz" % _n, "21t")
_SUF = ["", "-wide", "-object", "-boolean", "-byte", "-char", "-short"]
for _i, _s in enumerate(_SUF):
    _def(0x44 + _i, "aget" + _s, "23x")
    _def(0x4b + _i, "aput" + _s, "23x")
    _def(0x52 + _i, "iget" + _s, "22c")
    _def(0x59 + _i, "iput" + _s, "22c")
    _def(0x60 + _i, "sget" + _s, "21c")
    _def(0x67 + _i, "sput" + _s, "21c")
for _i, _n in enumerate(["virtual", "super", "direct", "static", "interface"]):
    _def(0x6e + _i, "invoke-" + _n, "35c")
    _def(0x74 + _i, "invoke-%s/range" % _n, "3rc")
for _i, _n in enumerate(["neg-int", "not-int", "neg-long", "not-long", "neg-float", "neg-double",
                         "int-to-long", "int-to-float", "int-to-double", "long-to-int", "long-to-float",
                         "long-to-double", "float-to-int", "float-to-long", "float-to-double",
                         "double-to-int", "double-to-long", "double-to-float", "int-to-byte",
                         "int-to-char", "int-to-short"]):
    _def(0x7b + _i, _n, "12x")
_BIN = []
for _t, _ops in [("int", ["add", "sub", "mul", "div", "rem", "and", "or", "xor", "shl", "shr", "ushr"]),
                 ("long", ["add", "sub", "mul", "div", "rem", "and", "or", "xor", "shl", "shr", "ushr"]),
                 ("float", ["add", "sub", "mul", "div", "rem"]),
                 ("double", ["add", "sub", "mul", "div", "rem"])]:
    for _o in _ops:
        _BIN.append("%s-%s" % (_o, _t))
for _i, _n in enumerate(_BIN):
    _def(0x90 + _i, _n, "23x")
    _def(0xb0 + _i, _n + "/2addr", "12x")
for _i, _n in enumerate(["add", "rsub", "mul", "div", "rem", "and", "or", "xor"]):
    _def(0xd0 + _i, ("%s-int/lit16" % _n) if _n != "rsub" else "rsub-int", "22s")
for _i, _n in enumerate(["add", "rsub", "mul", "div", "rem", "and", "or", "xor", "shl", "shr", "ushr"]):
    _def(0xd8 + _i, "%s-int/lit8" % _n, "22b")
_def(0xfa, "invoke-polymorphic", "45cc")
_def(0xfb, "invoke-polymorphic/range", "4rcc")
_def(0xfc, "invoke-custom", "35c")
_def(0xfd, "invoke-custom/range", "3rc")
_def(0xfe, "const-method-handle", "21c")
_def(0xff, "const-method-type", "21c")

NAME_TO_OP = {v[0]: k for k, v in OPS.items()}

FMT_SIZE = {"10x": 1, "12x": 1, "11n": 1, "11x": 1, "10t": 1, "20t": 2, "22x": 2, "21t": 2, "21s": 2,
            "21h": 2, "21c": 2, "23x": 2, "22b": 2, "22t": 2, "22s": 2, "22c": 2, "32x": 3, "30t": 3,
            "31i": 3, "31t": 3, "31c": 3, "35c": 3, "3rc": 3, "51l": 5, "45cc": 4, "4rcc": 4}

# which instructions reference which pool
REF_KIND = {}
for _o, (_n, _f) in OPS.items():
    if _n in ("const-string", "const-string/jumbo"):
        REF_KIND[_o] = "string"
    elif _n in ("const-class", "check-cast", "instance-of", "new-instance", "new-array",
                "filled-new-array", "filled-new-array/range"):
        REF_KIND[_o] = "type"
    elif _n.startswith(("iget", "iput", "sget", "sput")):
        REF_KIND[_o] = "field"
    elif _n.startswith("invoke-") and "custom" not in _n and "polymorphic" not in _n:
        REF_KIND[_o] = "method"


class Label:
    __slots__ = ("pos", "name")

    def __init__(self, name=None):
        self.pos = None
        self.name = name

    def __repr__(self):
        return "L%s@%s" % (self.name or id(self) % 10000, self.pos)


class Insn:
    __slots__ = ("op", "args", "pos")

    def __init__(self, op, *args):
        self.op = op
        self.args = list(args)
        self.pos = None

    @property
    def name(self):
        return OPS[self.op][0]

    @property
    def fmt(self):
        return OPS[self.op][1]

    def __repr__(self):
        return "%s %s" % (self.name, ", ".join(map(str, self.args)))


class SwitchPayload:
    """packed (keys contiguous) or sparse switch payload."""
    __slots__ = ("packed", "keys", "targets", "switch", "pos")

    def __init__(self, packed, keys, targets):
        self.packed = packed
        self.keys = keys
        self.targets = targets
        self.switch = None
        self.pos = None

    def size(self):
        n = len(self.targets)
        return 4 + 2 * n if self.packed else 2 + 4 * n


class TryRegion:
    __slots__ = ("start", "end", "handlers", "catch_all")

    def __init__(self, start, end, handlers, catch_all):
        self.start = start          # Label
        self.end = end              # Label (exclusive)
        self.handlers = handlers    # [(type_desc, Label)]
        self.catch_all = catch_all  # Label or None


class AsmError(Exception):
    pass


def _chk(v, bits, what, signed=False):
    if signed:
        lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    else:
        lo, hi = 0, (1 << bits) - 1
    if not (lo <= v <= hi):
        raise AsmError("%s value %d does not fit in %d bits" % (what, v, bits))
    return v & ((1 << bits) - 1)


def assemble(items, index_of):
    """items: list of Insn / Label.  index_of(kind, ref) -> pool index.
    Returns list of 16-bit code units.  Payloads are appended at the end."""
    # Fix jumbo const-string choice (only size-changing decision).
    for it in items:
        if isinstance(it, Insn) and it.op == 0x1a and index_of("string", it.args[1]) > 0xFFFF:
            it.op = 0x1b
    pos = 0
    payloads = []
    for it in items:
        if isinstance(it, Label):
            it.pos = pos
        else:
            it.pos = pos
            pos += FMT_SIZE[it.fmt]
            if it.fmt == "31t":
                p = it.args[1]
                p.switch = it
                payloads.append(p)
    for p in payloads:
        if pos % 2:
            pos += 1  # nop padding, keep payload 4-byte aligned
        p.pos = pos
        pos += p.size()
    total = pos

    units = []

    def emit(*us):
        for u in us:
            units.append(u & 0xFFFF)

    for it in items:
        if isinstance(it, Label):
            continue
        op, a, f = it.op, it.args, it.fmt
        assert len(units) == it.pos
        if f == "10x":
            emit(op)
        elif f == "12x":
            emit(op | (_chk(a[0], 4, "vA") << 8) | (_chk(a[1], 4, "vB") << 12))
        elif f == "11n":
            emit(op | (_chk(a[0], 4, "vA") << 8) | (_chk(a[1], 4, "lit4", True) << 12))
        elif f == "11x":
            emit(op | (_chk(a[0], 8, "vAA") << 8))
        elif f == "10t":
            emit(op | (_chk(a[0].pos - it.pos, 8, "branch", True) << 8))
        elif f == "20t":
            emit(op, _chk(a[0].pos - it.pos, 16, "branch", True))
        elif f == "30t":
            off = (a[0].pos - it.pos) & 0xFFFFFFFF
            emit(op, off & 0xFFFF, off >> 16)
        elif f == "22x":
            emit(op | (_chk(a[0], 8, "vAA") << 8), _chk(a[1], 16, "vBBBB"))
        elif f == "32x":
            emit(op, _chk(a[0], 16, "vAAAA"), _chk(a[1], 16, "vBBBB"))
        elif f == "21t":
            emit(op | (_chk(a[0], 8, "vAA") << 8), _chk(a[1].pos - it.pos, 16, "branch", True))
        elif f in ("21s", "21h"):
            emit(op | (_chk(a[0], 8, "vAA") << 8), _chk(a[1], 16, "lit16", True))
        elif f == "21c":
            kind = REF_KIND[op]
            emit(op | (_chk(a[0], 8, "vAA") << 8), _chk(index_of(kind, a[1]), 16, kind + " index"))
        elif f == "31c":
            idx = index_of(REF_KIND[op], a[1])
            emit(op | (_chk(a[0], 8, "vAA") << 8), idx & 0xFFFF, idx >> 16)
        elif f == "23x":
            emit(op | (_chk(a[0], 8, "vAA") << 8), _chk(a[1], 8, "vBB") | (_chk(a[2], 8, "vCC") << 8))
        elif f == "22b":
            emit(op | (_chk(a[0], 8, "vAA") << 8), _chk(a[1], 8, "vBB") | (_chk(a[2], 8, "lit8", True) << 8))
        elif f == "22t":
            emit(op | (_chk(a[0], 4, "vA") << 8) | (_chk(a[1], 4, "vB") << 12),
                 _chk(a[2].pos - it.pos, 16, "branch", True))
        elif f == "22s":
            emit(op | (_chk(a[0], 4, "vA") << 8) | (_chk(a[1], 4, "vB") << 12), _chk(a[2], 16, "lit16", True))
        elif f == "22c":
            kind = REF_KIND[op]
            emit(op | (_chk(a[0], 4, "vA") << 8) | (_chk(a[1], 4, "vB") << 12),
                 _chk(index_of(kind, a[2]), 16, kind + " index"))
        elif f == "31i":
            v = _chk(a[1], 32, "lit32", True)
            emit(op | (_chk(a[0], 8, "vAA") << 8), v & 0xFFFF, v >> 16)
        elif f == "31t":
            off = (a[1].pos - it.pos) & 0xFFFFFFFF
            emit(op | (_chk(a[0], 8, "vAA") << 8), off & 0xFFFF, off >> 16)
        elif f == "3rc":
            first, count, ref = a
            emit(op | (_chk(count, 8, "arg count") << 8),
                 _chk(index_of(REF_KIND[op], ref), 16, "method index"), _chk(first, 16, "first reg"))
        elif f == "51l":
            v = a[1] & 0xFFFFFFFFFFFFFFFF
            emit(op | (_chk(a[0], 8, "vAA") << 8), v & 0xFFFF, (v >> 16) & 0xFFFF, (v >> 32) & 0xFFFF, v >> 48)
        else:
            raise AsmError("format %s not supported by assembler" % f)
    for p in payloads:
        while len(units) < p.pos:
            emit(0)  # nop
        base = p.switch.pos
        n = len(p.targets)
        if p.packed:
            k = p.keys[0] & 0xFFFFFFFF
            emit(0x0100, n, k & 0xFFFF, k >> 16)
            for t in p.targets:
                off = (t.pos - base) & 0xFFFFFFFF
                emit(off & 0xFFFF, off >> 16)
        else:
            emit(0x0200, n)
            for k in p.keys:
                k &= 0xFFFFFFFF
                emit(k & 0xFFFF, k >> 16)
            for t in p.targets:
                off = (t.pos - base) & 0xFFFFFFFF
                emit(off & 0xFFFF, off >> 16)
    assert len(units) == total, (len(units), total)
    return units


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def s32(v):
    return v - 0x100000000 if v & 0x80000000 else v


def decode(units, i):
    """Decode instruction at unit index i.  Returns (op, name, fmt, size, fields dict).
    Payload pseudo-instructions are reported with name 'packed-switch-payload' etc."""
    u = units[i]
    op = u & 0xFF
    if op == 0 and u != 0:
        ident = u
        if ident == 0x0100:
            n = units[i + 1]
            return (0, "packed-switch-payload", None, 4 + 2 * n, {"n": n})
        if ident == 0x0200:
            n = units[i + 1]
            return (0, "sparse-switch-payload", None, 2 + 4 * n, {"n": n})
        if ident == 0x0300:
            w = units[i + 1]
            n = units[i + 2] | (units[i + 3] << 16)
            return (0, "fill-array-data-payload", None, 4 + (w * n + 1) // 2, {"n": n})
        raise AsmError("bad pseudo-instruction ident 0x%04x" % ident)
    if op not in OPS:
        raise AsmError("unused opcode 0x%02x" % op)
    name, f = OPS[op]
    size = FMT_SIZE[f]
    hi = u >> 8
    F = {}
    if f == "12x" or f == "11n":
        F["A"] = hi & 0xF
        F["B"] = hi >> 4
        if f == "11n" and F["B"] & 8:
            F["B"] -= 16
    elif f in ("11x", "10t"):
        F["A"] = hi if f == "11x" else (hi - 256 if hi & 0x80 else hi)
    elif f == "20t":
        F["A"] = s16(units[i + 1])
    elif f in ("22x", "21t", "21s", "21h", "21c"):
        F["A"] = hi
        F["B"] = units[i + 1] if f in ("22x", "21c") else s16(units[i + 1])
    elif f == "23x" or f == "22b":
        F["A"] = hi
        F["B"] = units[i + 1] & 0xFF
        c = units[i + 1] >> 8
        F["C"] = (c - 256 if c & 0x80 else c) if f == "22b" else c
    elif f in ("22t", "22s", "22c"):
        F["A"] = hi & 0xF
        F["B"] = hi >> 4
        F["C"] = units[i + 1] if f == "22c" else s16(units[i + 1])
    elif f == "32x":
        F["A"] = units[i + 1]
        F["B"] = units[i + 2]
    elif f == "30t":
        F["A"] = s32(units[i + 1] | (units[i + 2] << 16))
    elif f in ("31i", "31t", "31c"):
        F["A"] = hi
        v = units[i + 1] | (units[i + 2] << 16)
        F["B"] = s32(v) if f != "31c" else v
    elif f == "35c":
        F["count"] = hi >> 4
        g = hi & 0xF
        F["B"] = units[i + 1]
        cdef = units[i + 2]
        regs = [cdef & 0xF, (cdef >> 4) & 0xF, (cdef >> 8) & 0xF, cdef >> 12, g]
        F["regs"] = regs[:F["count"]]
    elif f == "3rc":
        F["count"] = hi
        F["B"] = units[i + 1]
        F["C"] = units[i + 2]
        F["regs"] = list(range(F["C"], F["C"] + hi))
    elif f == "51l":
        F["A"] = hi
        v = units[i + 1] | (units[i + 2] << 16) | (units[i + 3] << 32) | (units[i + 4] << 48)
        F["B"] = v - (1 << 64) if v >> 63 else v
    elif f == "10x":
        pass
    else:
        raise AsmError("cannot decode format " + f)
    return (op, name, f, size, F)
