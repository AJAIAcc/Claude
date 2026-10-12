"""A small Dalvik interpreter for differential testing of the translator.

It executes *our* DEX output (not the original JVM bytecode) with a tiny
hand-written subset of java.lang / java.util, so any translation mistake shows
up as different program output compared with the real JVM.
Values in registers are raw 32/64-bit patterns exactly like on a device.
"""
import math
import struct
import sys

from . import dalvik as D
from .dexcheck import DexFile

WIDE_HI = object()
MASK32 = 0xFFFFFFFF
MASK64 = 0xFFFFFFFFFFFFFFFF


def s32(v):
    v &= MASK32
    return v - 0x100000000 if v & 0x80000000 else v


def s64(v):
    v &= MASK64
    return v - (1 << 64) if v >> 63 else v


def f2bits(x):
    try:
        return s32(struct.unpack("<I", struct.pack("<f", x))[0])
    except OverflowError:
        return f2bits(math.copysign(math.inf, x))


def bits2f(b):
    return struct.unpack("<f", struct.pack("<I", b & MASK32))[0]


def f32(x):
    return bits2f(f2bits(x))


def d2bits(x):
    return s64(struct.unpack("<Q", struct.pack("<d", x))[0])


def bits2d(b):
    return struct.unpack("<d", struct.pack("<Q", b & MASK64))[0]


def java_dtoa(d, is_float=False):
    if d != d:
        return "NaN"
    if d in (math.inf, -math.inf):
        return "Infinity" if d > 0 else "-Infinity"
    if d == 0:
        return "-0.0" if math.copysign(1, d) < 0 else "0.0"
    neg = d < 0
    a = abs(d)
    if is_float:
        for p in range(1, 10):
            s = "%.*e" % (p - 1, a)
            if f32(float(s)) == a:
                break
    else:
        s = repr(a)
        if "e" not in s:
            s = "%.*e" % (max(0, len(s.replace(".", "").lstrip("0").rstrip("0")) - 1), a)
            # ensure round trip
            if float(s) != a:
                s = "%.16e" % a
    mant, exp = s.split("e")
    exp = int(exp)
    digits = mant.replace(".", "").rstrip("0") or "0"
    if 1e-3 <= a < 1e7:
        # fixed
        point = exp + 1
        if point <= 0:
            txt = "0." + "0" * (-point) + digits
        elif point >= len(digits):
            txt = digits + "0" * (point - len(digits)) + ".0"
        else:
            txt = digits[:point] + "." + digits[point:]
    else:
        txt = digits[0] + "." + (digits[1:] or "0") + "E" + str(exp)
    return ("-" if neg else "") + txt


class JavaThrow(Exception):
    def __init__(self, obj):
        self.obj = obj


class JObject:
    __slots__ = ("cls", "fields", "nat", "__weakref__")

    def __init__(self, cls):
        self.cls = cls
        self.fields = {}
        self.nat = None


class JArray:
    __slots__ = ("desc", "data")

    def __init__(self, desc, data):
        self.desc = desc
        self.data = data


class JClass:
    __slots__ = ("desc",)

    def __init__(self, desc):
        self.desc = desc


LIB_SUPER = {
    "Ljava/lang/Throwable;": "Ljava/lang/Object;",
    "Ljava/lang/Exception;": "Ljava/lang/Throwable;",
    "Ljava/lang/Error;": "Ljava/lang/Throwable;",
    "Ljava/lang/RuntimeException;": "Ljava/lang/Exception;",
    "Ljava/lang/NullPointerException;": "Ljava/lang/RuntimeException;",
    "Ljava/lang/ArithmeticException;": "Ljava/lang/RuntimeException;",
    "Ljava/lang/IllegalStateException;": "Ljava/lang/RuntimeException;",
    "Ljava/lang/IllegalArgumentException;": "Ljava/lang/RuntimeException;",
    "Ljava/lang/NumberFormatException;": "Ljava/lang/IllegalArgumentException;",
    "Ljava/lang/ClassCastException;": "Ljava/lang/RuntimeException;",
    "Ljava/lang/UnsupportedOperationException;": "Ljava/lang/RuntimeException;",
    "Ljava/lang/IndexOutOfBoundsException;": "Ljava/lang/RuntimeException;",
    "Ljava/lang/ArrayIndexOutOfBoundsException;": "Ljava/lang/IndexOutOfBoundsException;",
    "Ljava/lang/StringIndexOutOfBoundsException;": "Ljava/lang/IndexOutOfBoundsException;",
    "Ljava/lang/NegativeArraySizeException;": "Ljava/lang/RuntimeException;",
    "Ljava/lang/NoSuchFieldError;": "Ljava/lang/Error;",
    "Ljava/lang/Enum;": "Ljava/lang/Object;",
    "Ljava/lang/Number;": "Ljava/lang/Object;",
    "Ljava/lang/Integer;": "Ljava/lang/Number;",
    "Ljava/lang/Long;": "Ljava/lang/Number;",
    "Ljava/lang/Double;": "Ljava/lang/Number;",
    "Ljava/lang/Float;": "Ljava/lang/Number;",
    "Ljava/lang/Short;": "Ljava/lang/Number;",
    "Ljava/lang/Byte;": "Ljava/lang/Number;",
    "Ljava/lang/Character;": "Ljava/lang/Object;",
    "Ljava/lang/Boolean;": "Ljava/lang/Object;",
    "Ljava/lang/String;": "Ljava/lang/Object;",
    "Ljava/lang/StringBuilder;": "Ljava/lang/Object;",
    "Ljava/util/ArrayList;": "Ljava/lang/Object;",
    "Ljava/util/HashMap;": "Ljava/lang/Object;",
    "Ljava/io/PrintStream;": "Ljava/lang/Object;",
    "Ljava/lang/Object;": None,
}
LIB_IFACES = {
    "Ljava/lang/String;": ["Ljava/lang/CharSequence;", "Ljava/lang/Comparable;"],
    "Ljava/lang/StringBuilder;": ["Ljava/lang/CharSequence;"],
    "Ljava/util/ArrayList;": ["Ljava/util/List;", "Ljava/util/Collection;", "Ljava/lang/Iterable;"],
    "Ljava/util/HashMap;": ["Ljava/util/Map;"],
    "Ljava/lang/Integer;": ["Ljava/lang/Comparable;"],
}

BOXES = {"Ljava/lang/Integer;": "I", "Ljava/lang/Long;": "J", "Ljava/lang/Double;": "D",
         "Ljava/lang/Float;": "F", "Ljava/lang/Boolean;": "Z", "Ljava/lang/Character;": "C",
         "Ljava/lang/Short;": "S", "Ljava/lang/Byte;": "B"}


# registers that must hold references for these opcodes -> treat int 0 as null
REFOPS = {0x1d: "A", 0x1e: "A", 0x1f: "A", 0x20: "B", 0x21: "B", 0x27: "A", 0x4d: "AB"}
for _o in range(0x44, 0x52):
    REFOPS.setdefault(_o, "B")
for _o in range(0x52, 0x60):
    REFOPS[_o] = "B"
REFOPS[0x5b] = "AB"
REFOPS[0x69] = "A"


class Frame:
    __slots__ = ("regs", "exc")


class VM:
    def __init__(self, dex_bytes):
        self.dex = DexFile(dex_bytes)
        if self.dex.errors:
            raise RuntimeError("dex has errors: %s" % self.dex.errors[:5])
        self.classes = {}
        for c in self.dex.classes:
            methods = {}
            for key in ("direct", "virtual"):
                for (m, acc, code) in c[key]:
                    methods[(m[1], m[2][1], m[2][0])] = (acc, code, c["desc"])
            c["mtab"] = methods
            self.classes[c["desc"]] = c
        self.statics = {}
        self.inited = set()
        self.out = []
        self.decoded = {}
        self.steps = 0

    # ------------------------------------------------------------ classes
    def super_of(self, desc):
        if desc in self.classes:
            return self.classes[desc]["super"]
        return LIB_SUPER.get(desc, "Ljava/lang/Object;" if desc != "Ljava/lang/Object;" else None)

    def ifaces_of(self, desc):
        if desc in self.classes:
            return self.classes[desc]["interfaces"]
        return LIB_IFACES.get(desc, [])

    def is_subclass(self, sub, sup):
        if sup == "Ljava/lang/Object;":
            return True
        if sub.startswith("["):
            if not sup.startswith("["):
                return sup in ("Ljava/lang/Cloneable;", "Ljava/io/Serializable;")
            se, pe = sub[1:], sup[1:]
            if se[0] in "L[" and pe[0] in "L[":
                return self.is_subclass(se, pe)
            return se == pe
        todo = [sub]
        seen = set()
        while todo:
            c = todo.pop()
            if c is None or c in seen:
                continue
            seen.add(c)
            if c == sup:
                return True
            todo.append(self.super_of(c))
            todo.extend(self.ifaces_of(c))
        return False

    def runtime_class(self, v):
        if isinstance(v, str):
            return "Ljava/lang/String;"
        if isinstance(v, JArray):
            return v.desc
        if isinstance(v, JClass):
            return "Ljava/lang/Class;"
        return v.cls

    def instance_of(self, v, desc):
        return v is not None and self.is_subclass(self.runtime_class(v), desc)

    def init_class(self, desc):
        if desc in self.inited or desc not in self.classes:
            return
        self.inited.add(desc)
        c = self.classes[desc]
        if c["super"]:
            self.init_class(c["super"])
        st = self.statics.setdefault(desc, {})
        for i, (f, acc) in enumerate(c["static_fields"]):
            if i < len(c["static_values"]):
                kind, v = c["static_values"][i]
                st[f[1]] = self.raw_from_encoded(kind, v)
            else:
                st[f[1]] = self.default(f[2])
        key = ("<clinit>", (), "V")
        if key in c["mtab"]:
            self.execute(desc, c["mtab"][key], [])

    def raw_from_encoded(self, kind, v):
        if kind in ("int", "short", "byte", "char"):
            return s32(v)
        if kind == "boolean":
            return 1 if v else 0
        if kind == "long":
            return s64(v)
        if kind == "float":
            return f2bits(v)
        if kind == "double":
            return d2bits(v)
        return v  # string / null

    @staticmethod
    def default(t):
        if t in ("J", "D"):
            return 0
        if t[0] in "L[":
            return None
        return 0

    def new_object(self, desc):
        self.init_class(desc)
        o = JObject(desc)
        c = desc
        while c in self.classes:
            for (f, acc) in self.classes[c]["instance_fields"]:
                o.fields[(c, f[1])] = self.default(f[2])
            c = self.classes[c]["super"]
        return o

    def field_owner(self, desc, name, static):
        c = desc
        while c in self.classes:
            lst = self.classes[c]["static_fields" if static else "instance_fields"]
            for (f, acc) in lst:
                if f[1] == name:
                    return c
            if static:
                for i in self.classes[c]["interfaces"]:
                    if i in self.classes:
                        return self.field_owner(i, name, static) or c
            c = self.classes[c]["super"]
        return None

    # ------------------------------------------------------------ exceptions
    def throw(self, desc, msg=None):
        o = JObject(desc)
        o.nat = {"msg": msg}
        raise JavaThrow(o)

    # ------------------------------------------------------------ invocation
    def find_virtual(self, desc, key):
        c = desc
        while c is not None:
            if c in self.classes:
                m = self.classes[c]["mtab"].get(key)
                if m and not m[0] & 0x8 and key[0] != "<init>":
                    return ("dex", c, m)
            else:
                nat = NATIVES.get((c,) + key)
                if nat:
                    return ("nat", c, nat)
            c = self.super_of(c)
        # default methods from (transitive) interfaces
        todo, seen = [desc], set()
        while todo:
            c = todo.pop(0)
            if c is None or c in seen:
                continue
            seen.add(c)
            if c in self.classes and self.classes[c]["access"] & 0x200:
                m = self.classes[c]["mtab"].get(key)
                if m and m[1] is not None and not m[0] & 0x8:
                    return ("dex", c, m)
            todo.append(self.super_of(c))
            todo.extend(self.ifaces_of(c))
        nat = NATIVES.get(("Ljava/lang/Object;",) + key)
        if nat:
            return ("nat", "Ljava/lang/Object;", nat)
        return None

    def call(self, kind, mref, args, caller):
        cls, name, proto = mref[0], mref[1], mref[2]
        key = (name, proto[1], proto[0])
        if kind in ("virtual", "interface"):
            recv = args[0]
            if recv is None:
                self.throw("Ljava/lang/NullPointerException;", "null receiver for " + name)
            rc = self.runtime_class(recv)
            tgt = self.find_virtual(rc, key)
            if tgt is None:
                if rc.startswith("[") and name == "clone":
                    return JArray(recv.desc, list(recv.data))
                raise RuntimeError("no method %s%s on %s" % (name, key, rc))
        elif kind == "super":
            sup = self.classes[caller]["super"]
            tgt = self.find_virtual(sup, key)
            if tgt is None:
                raise RuntimeError("no super method %s on %s" % (name, sup))
        else:  # direct / static
            if kind == "static":
                self.init_class(cls)
            tgt = None
            c = cls
            while c is not None:
                if c in self.classes:
                    m = self.classes[c]["mtab"].get(key)
                    if m:
                        tgt = ("dex", c, m)
                        break
                else:
                    nat = NATIVES.get((c,) + key)
                    if nat:
                        tgt = ("nat", c, nat)
                        break
                c = self.super_of(c)
            if tgt is None:
                raise RuntimeError("no method %s->%s%s" % (cls, name, key))
        if tgt[0] == "dex":
            return self.execute(tgt[1], tgt[2], args, proto[1], kind != "static")
        # native: decode args
        params = proto[1]
        dec = []
        i = 0
        if kind != "static":
            dec.append(args[0])
            i = 1
        for t in params:
            dec.append(self.decode(args[i], t))
            i += 1
        r = tgt[2](self, *dec)
        return self.encode(r, proto[0])

    @staticmethod
    def decode(v, t):
        if t == "F":
            return bits2f(v)
        if t == "D":
            return bits2d(v)
        return v

    @staticmethod
    def encode(v, t):
        if t == "V":
            return None
        if t == "F":
            return f2bits(v)
        if t == "D":
            return d2bits(v)
        if t == "Z":
            return 1 if v else 0
        if t in ("I", "S", "B", "C"):
            return s32(v)
        if t == "J":
            return s64(v)
        return v

    # ------------------------------------------------------------ interpreter
    def execute(self, cls, m, args, params=(), has_this=False):
        acc, code, _ = m
        if code is None:
            raise RuntimeError("no code for method in %s" % cls)
        ins = self.decoded.get(id(code))
        if ins is None:
            ins = {a: (op, name, fmt, size, F) for (a, op, name, fmt, size, F) in self.dex.insns(code)}
            self.decoded[id(code)] = ins
        regs = [None] * code.regs
        p = code.regs - code.ins
        # args already in raw form; wide args occupy 2 regs
        types = (["L"] if has_this else []) + list(params)
        for v, t in zip(args, types):
            regs[p] = v
            if t in ("J", "D"):
                regs[p + 1] = WIDE_HI
                p += 2
            else:
                p += 1
        return self.run_code(cls, code, ins, regs)

    def run_code(self, cls, code, ins, R):
        pc = 0
        result = None
        exc = None
        dex = self.dex
        while True:
            self.steps += 1
            if self.steps > 50_000_000:
                raise RuntimeError("step limit")
            op, name, fmt, size, F = ins[pc]
            A, B, C = F.get("A"), F.get("B"), F.get("C")
            if op in REFOPS:
                for key in REFOPS[op]:
                    v = R[F[key]]
                    if isinstance(v, int) and v == 0:
                        R[F[key]] = None
            nxt = pc + size
            try:
                if op <= 0x09 and op >= 0x01:
                    if op in (4, 5, 6):
                        R[A] = R[B]
                        R[A + 1] = WIDE_HI
                    else:
                        R[A] = R[B]
                elif op == 0x0a or op == 0x0c:
                    R[A] = result
                elif op == 0x0b:
                    R[A] = result
                    R[A + 1] = WIDE_HI
                elif op == 0x0d:
                    R[A] = exc
                elif op == 0x0e:
                    return None
                elif op in (0x0f, 0x10):
                    return R[A]
                elif op == 0x11:
                    return None if isinstance(R[A], int) else R[A]
                elif op in (0x12, 0x13, 0x14):
                    R[A] = s32(B)
                elif op == 0x15:
                    R[A] = s32(B << 16)
                elif op in (0x16, 0x17, 0x18):
                    R[A] = s64(B)
                    R[A + 1] = WIDE_HI
                elif op == 0x19:
                    R[A] = s64(B << 48)
                    R[A + 1] = WIDE_HI
                elif op in (0x1a, 0x1b):
                    R[A] = dex.strings[B]
                elif op == 0x1c:
                    R[A] = JClass(dex.types[B])
                elif op in (0x1d, 0x1e):
                    if R[A] is None:
                        self.throw("Ljava/lang/NullPointerException;")
                elif op == 0x1f:
                    t = dex.types[B]
                    if R[A] is not None and not self.instance_of(R[A], t):
                        self.throw("Ljava/lang/ClassCastException;",
                                   "%s cannot be cast to %s" % (self.runtime_class(R[A]), t))
                elif op == 0x20:
                    R[A] = 1 if self.instance_of(R[B], dex.types[C]) else 0
                elif op == 0x21:
                    if R[B] is None:
                        self.throw("Ljava/lang/NullPointerException;")
                    R[A] = len(R[B].data)
                elif op == 0x22:
                    R[A] = self.new_object(dex.types[B])
                elif op == 0x23:
                    n = R[B]
                    if n < 0:
                        self.throw("Ljava/lang/NegativeArraySizeException;", str(n))
                    t = dex.types[C]
                    R[A] = JArray(t, [self.default(t[1:])] * n)
                elif op == 0x27:
                    if R[A] is None:
                        self.throw("Ljava/lang/NullPointerException;")
                    raise JavaThrow(R[A])
                elif op in (0x28, 0x29, 0x2a):
                    nxt = pc + A
                elif op in (0x2b, 0x2c):
                    key = R[A]
                    pa = pc + B
                    u = code.units
                    n = u[pa + 1]
                    if op == 0x2b:
                        first = s32(u[pa + 2] | (u[pa + 3] << 16))
                        i = key - first
                        if 0 <= i < n:
                            nxt = pc + s32(u[pa + 4 + 2 * i] | (u[pa + 5 + 2 * i] << 16))
                    else:
                        for i in range(n):
                            k = s32(u[pa + 2 + 2 * i] | (u[pa + 3 + 2 * i] << 16))
                            if k == key:
                                nxt = pc + s32(u[pa + 2 + 2 * n + 2 * i] | (u[pa + 3 + 2 * n + 2 * i] << 16))
                                break
                elif 0x2d <= op <= 0x31:
                    if op == 0x31:
                        x, y = R[B], R[C]
                        R[A] = (x > y) - (x < y)
                    else:
                        if op <= 0x2e:
                            x, y = bits2f(R[B]), bits2f(R[C])
                        else:
                            x, y = bits2d(R[B]), bits2d(R[C])
                        if x != x or y != y:
                            R[A] = -1 if op in (0x2d, 0x2f) else 1
                        else:
                            R[A] = (x > y) - (x < y)
                elif 0x32 <= op <= 0x37:
                    x, y = R[A], R[B]
                    if op in (0x32, 0x33):
                        if isinstance(x, int) and isinstance(y, int):
                            eq = x == y
                        else:
                            nx = None if isinstance(x, int) and x == 0 else x
                            ny = None if isinstance(y, int) and y == 0 else y
                            eq = nx is ny
                        c = eq if op == 0x32 else not eq
                    else:
                        c = {0x34: x < y, 0x35: x >= y, 0x36: x > y, 0x37: x <= y}[op]
                    if c:
                        nxt = pc + C
                elif 0x38 <= op <= 0x3d:
                    x = R[A]
                    if not isinstance(x, int):
                        x = 0 if x is None else 1
                    c = {0x38: x == 0, 0x39: x != 0, 0x3a: x < 0, 0x3b: x >= 0, 0x3c: x > 0, 0x3d: x <= 0}[op]
                    if c:
                        nxt = pc + B
                elif 0x44 <= op <= 0x51:
                    arr, idx = R[B], R[C]
                    if arr is None:
                        self.throw("Ljava/lang/NullPointerException;")
                    if not 0 <= idx < len(arr.data):
                        self.throw("Ljava/lang/ArrayIndexOutOfBoundsException;",
                                   "length=%d; index=%d" % (len(arr.data), idx))
                    et = arr.desc[1:]
                    if op <= 0x4a:
                        R[A] = arr.data[idx]
                        if op == 0x45:
                            R[A + 1] = WIDE_HI
                    else:
                        v = R[A]
                        if op == 0x4d and v is not None and not self.instance_of(v, et):
                            self.throw("Ljava/lang/ArrayStoreException;")
                        if et == "B":
                            v = ((v + 128) & 0xFF) - 128
                        elif et == "C":
                            v &= 0xFFFF
                        elif et == "S":
                            v = ((v + 32768) & 0xFFFF) - 32768
                        elif et == "Z":
                            v &= 1
                        arr.data[idx] = v
                elif 0x52 <= op <= 0x5f:
                    f = dex.fields[C]
                    obj = R[B]
                    if obj is None:
                        self.throw("Ljava/lang/NullPointerException;", "field " + f[1])
                    owner = self.field_owner(f[0], f[1], False)
                    k = (owner, f[1])
                    if op <= 0x58:
                        R[A] = obj.fields[k]
                        if op == 0x53:
                            R[A + 1] = WIDE_HI
                    else:
                        obj.fields[k] = self.narrow(R[A], f[2])
                elif 0x60 <= op <= 0x6d:
                    f = dex.fields[B]
                    owner = self.field_owner(f[0], f[1], True)
                    if owner is None:
                        # library static
                        R[A] = LIB_STATICS[(f[0], f[1])](self)
                    else:
                        self.init_class(owner)
                        st = self.statics[owner]
                        if op <= 0x66:
                            R[A] = st[f[1]]
                            if op == 0x61:
                                R[A + 1] = WIDE_HI
                        else:
                            st[f[1]] = self.narrow(R[A], f[2])
                elif 0x74 <= op <= 0x78 or 0x6e <= op <= 0x72:
                    kind = D.OPS[op][0].split("-")[1].split("/")[0]
                    mref = dex.methods[B]
                    regs = F["regs"]
                    # collect args (wide args take the low register only)
                    args = []
                    i = 0
                    if kind != "static":
                        args.append(R[regs[0]])
                        i = 1
                    if args and args[0] == 0 and isinstance(args[0], int):
                        args[0] = None
                    for t in mref[2][1]:
                        v = R[regs[i]]
                        if t[0] in "L[" and isinstance(v, int):
                            v = None
                        args.append(v)
                        i += 2 if t in ("J", "D") else 1
                    result = self.call(kind, mref, args, cls)
                elif 0x7b <= op <= 0x8f:
                    R[A] = self.unop(op, R[B])
                    if op in (0x7d, 0x7e, 0x80, 0x81, 0x83, 0x86, 0x88, 0x89, 0x8b):
                        R[A + 1] = WIDE_HI
                elif 0x90 <= op <= 0xaf:
                    R[A] = self.binop(op - 0x90, R[B], R[C])
                    if 0x9b <= op <= 0xa5 or 0xab <= op <= 0xaf:
                        R[A + 1] = WIDE_HI
                elif 0xb0 <= op <= 0xcf:
                    R[A] = self.binop(op - 0xb0, R[A], R[B])
                    if 0xbb <= op <= 0xc5 or 0xcb <= op <= 0xcf:
                        R[A + 1] = WIDE_HI
                elif 0xd0 <= op <= 0xe2:
                    lit = C
                    if op <= 0xd7:
                        sub = ["add", "rsub", "mul", "div", "rem", "and", "or", "xor"][op - 0xd0]
                    else:
                        sub = ["add", "rsub", "mul", "div", "rem", "and", "or", "xor", "shl", "shr",
                               "ushr"][op - 0xd8]
                    x = R[B]
                    if sub == "rsub":
                        R[A] = s32(lit - x)
                    else:
                        R[A] = self.binop(["add", "sub", "mul", "div", "rem", "and", "or", "xor", "shl",
                                           "shr", "ushr"].index(sub), x, s32(lit))
                elif op == 0:
                    pass
                else:
                    raise RuntimeError("interpreter: unsupported %s" % name)
            except JavaThrow as t:
                handler = None
                for (start, cnt, hl, ca) in code.tries:
                    if start <= pc < start + cnt:
                        for (ty, addr) in hl:
                            if self.instance_of(t.obj, ty):
                                handler = addr
                                break
                        if handler is None and ca is not None:
                            handler = ca
                        break
                if handler is None:
                    raise
                exc = t.obj
                nxt = handler
            pc = nxt

    @staticmethod
    def narrow(v, t):
        if t == "B":
            return ((v + 128) & 0xFF) - 128
        if t == "C":
            return v & 0xFFFF
        if t == "S":
            return ((v + 32768) & 0xFFFF) - 32768
        if t == "Z":
            return v & 1
        return v

    def unop(self, op, x):
        if op == 0x7b:
            return s32(-x)
        if op == 0x7c:
            return s32(~x)
        if op == 0x7d:
            return s64(-x)
        if op == 0x7e:
            return s64(~x)
        if op == 0x7f:
            return f2bits(-bits2f(x))
        if op == 0x80:
            return d2bits(-bits2d(x))
        if op == 0x81:
            return x
        if op == 0x82:
            return f2bits(float(x))
        if op == 0x83:
            return d2bits(float(x))
        if op == 0x84:
            return s32(x)
        if op == 0x85:
            return f2bits(float(x))
        if op == 0x86:
            return d2bits(float(x))
        if op in (0x87, 0x88, 0x8a, 0x8b):
            v = bits2f(x) if op in (0x87, 0x88) else bits2d(x)
            lo, hi = (-(1 << 31), (1 << 31) - 1) if op in (0x87, 0x8a) else (-(1 << 63), (1 << 63) - 1)
            if v != v:
                return 0
            if v >= hi:
                return hi
            if v <= lo:
                return lo
            return int(v)
        if op == 0x89:
            return d2bits(bits2f(x))
        if op == 0x8c:
            return f2bits(bits2d(x))
        if op == 0x8d:
            return ((x + 128) & 0xFF) - 128
        if op == 0x8e:
            return x & 0xFFFF
        if op == 0x8f:
            return ((x + 32768) & 0xFFFF) - 32768
        raise RuntimeError("unop %x" % op)

    def binop(self, i, x, y):
        grp, sub = (0, i) if i < 11 else ((1, i - 11) if i < 22 else ((2, i - 22) if i < 27 else (3, i - 27)))
        if grp in (0, 1):
            wrap = s32 if grp == 0 else s64
            bits = 31 if grp == 0 else 63
            if sub == 0:
                return wrap(x + y)
            if sub == 1:
                return wrap(x - y)
            if sub == 2:
                return wrap(x * y)
            if sub in (3, 4):
                if y == 0:
                    self.throw("Ljava/lang/ArithmeticException;", "/ by zero")
                q = abs(x) // abs(y)
                if (x < 0) != (y < 0):
                    q = -q
                return wrap(q) if sub == 3 else wrap(x - q * y)
            if sub == 5:
                return wrap(x & y)
            if sub == 6:
                return wrap(x | y)
            if sub == 7:
                return wrap(x ^ y)
            sh = y & bits
            if sub == 8:
                return wrap(x << sh)
            if sub == 9:
                return wrap(x >> sh)
            if sub == 10:
                return wrap((x & (MASK32 if grp == 0 else MASK64)) >> sh)
        if grp == 2:
            a, b = bits2f(x), bits2f(y)
            r = self.fop(sub, a, b)
            return f2bits(r)
        a, b = bits2d(x), bits2d(y)
        return d2bits(self.fop(sub, a, b))

    @staticmethod
    def fop(sub, a, b):
        try:
            if sub == 0:
                return a + b
            if sub == 1:
                return a - b
            if sub == 2:
                return a * b
            if sub == 3:
                if b == 0:
                    if a != a or a == 0:
                        return math.nan
                    return math.copysign(math.inf, a) * math.copysign(1, b)
                return a / b
            if sub == 4:
                if b == 0 or a != a or b != b or a in (math.inf, -math.inf):
                    return math.nan
                return math.fmod(a, b)
        except OverflowError:
            return math.inf

    # ------------------------------------------------------------ helpers for natives
    def to_string(self, v):
        if v is None:
            return "null"
        if isinstance(v, str):
            return v
        r = self.call("virtual", ("Ljava/lang/Object;", "toString", ("Ljava/lang/String;", ())), [v], None)
        return r

    def run_main(self, cls_desc):
        self.init_class(cls_desc)
        m = self.classes[cls_desc]["mtab"][("main", ("[Ljava/lang/String;",), "V")]
        try:
            self.execute(cls_desc, m, [JArray("[Ljava/lang/String;", [])], ("[Ljava/lang/String;",), False)
        except JavaThrow as t:
            self.out.append("UNCAUGHT %s: %s\n" % (t.obj.cls, (t.obj.nat or {}).get("msg")))
        return "".join(self.out)


# ============================================================ native library
NATIVES = {}


def native(cls, name, desc):
    params, ret = _parse(desc)

    def deco(fn):
        NATIVES[(cls, name, tuple(params), ret)] = fn
        return fn
    return deco


def _parse(desc):
    from .classfile import parse_method_desc
    return parse_method_desc(desc)


O = "Ljava/lang/Object;"
S = "Ljava/lang/String;"
SB = "Ljava/lang/StringBuilder;"
PS = "Ljava/io/PrintStream;"


def jstr(vm, v, t):
    if t == "Z":
        return "true" if v else "false"
    if t == "C":
        return chr(v & 0xFFFF)
    if t in ("I", "J", "S", "B"):
        return str(v)
    if t == "F":
        return java_dtoa(v, True)
    if t == "D":
        return java_dtoa(v)
    if t == "[C":
        return "".join(chr(c) for c in v.data)
    return vm.to_string(v)


@native(O, "<init>", "()V")
def _o_init(vm, this):
    return None


@native(O, "toString", "()Ljava/lang/String;")
def _o_tostr(vm, this):
    if isinstance(this, str):
        return this
    if this.cls in BOXES:
        return jstr(vm, this.nat, BOXES[this.cls])
    if isinstance(this.nat, dict) and "msg" in this.nat and vm.is_subclass(this.cls, "Ljava/lang/Throwable;"):
        n = this.cls[1:-1].replace("/", ".")
        return n if this.nat["msg"] is None else n + ": " + this.nat["msg"]
    if isinstance(this.nat, dict) and "enum_name" in this.nat:
        return this.nat["enum_name"]
    if this.cls == SB:
        return "".join(this.nat)
    return this.cls[1:-1].replace("/", ".") + "@" + format(id(this) & 0xFFFFFF, "x")


@native(O, "hashCode", "()I")
def _o_hash(vm, this):
    if isinstance(this, str):
        h = 0
        for ch in this:
            h = s32(31 * h + ord(ch))
        return h
    if this.cls in BOXES:
        v = this.nat
        t = BOXES[this.cls]
        if t == "J":
            return s32(v ^ ((v & MASK64) >> 32))
        if t == "Z":
            return 1231 if v else 1237
        if t == "D":
            b = d2bits(v)
            return s32(b ^ ((b & MASK64) >> 32))
        if t == "F":
            return f2bits(v)
        return v
    return id(this) & 0x7FFFFFFF


@native(O, "equals", "(Ljava/lang/Object;)Z")
def _o_eq(vm, this, other):
    if isinstance(this, str):
        return isinstance(other, str) and this == other
    if isinstance(this, JObject) and this.cls in BOXES:
        return isinstance(other, JObject) and other.cls == this.cls and other.nat == this.nat
    return this is other


@native(O, "getClass", "()Ljava/lang/Class;")
def _o_getclass(vm, this):
    return JClass(vm.runtime_class(this))


# --- String
for _n, _d, _f in [
    ("length", "()I", lambda vm, s: len(s)),
    ("charAt", "(I)C", lambda vm, s, i: ord(s[i]) if 0 <= i < len(s) else vm.throw(
        "Ljava/lang/StringIndexOutOfBoundsException;", "index " + str(i))),
    ("isEmpty", "()Z", lambda vm, s: len(s) == 0),
    ("substring", "(I)Ljava/lang/String;", lambda vm, s, a: s[a:]),
    ("substring", "(II)Ljava/lang/String;", lambda vm, s, a, b: s[a:b]),
    ("indexOf", "(Ljava/lang/String;)I", lambda vm, s, t: s.find(t)),
    ("indexOf", "(I)I", lambda vm, s, c: s.find(chr(c))),
    ("contains", "(Ljava/lang/CharSequence;)Z", lambda vm, s, t: vm.to_string(t) in s),
    ("toUpperCase", "()Ljava/lang/String;", lambda vm, s: s.upper()),
    ("toLowerCase", "()Ljava/lang/String;", lambda vm, s: s.lower()),
    ("trim", "()Ljava/lang/String;", lambda vm, s: s.strip(" \t\n\r")),
    ("startsWith", "(Ljava/lang/String;)Z", lambda vm, s, t: s.startswith(t)),
    ("endsWith", "(Ljava/lang/String;)Z", lambda vm, s, t: s.endswith(t)),
    ("concat", "(Ljava/lang/String;)Ljava/lang/String;", lambda vm, s, t: s + t),
    ("equalsIgnoreCase", "(Ljava/lang/String;)Z", lambda vm, s, t: t is not None and s.lower() == t.lower()),
    ("compareTo", "(Ljava/lang/String;)I", lambda vm, s, t: _cmp_str(s, t)),
    ("toCharArray", "()[C", lambda vm, s: JArray("[C", [ord(c) for c in s])),
    ("replace", "(CC)Ljava/lang/String;", lambda vm, s, a, b: s.replace(chr(a), chr(b))),
    ("replace", "(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Ljava/lang/String;",
     lambda vm, s, a, b: s.replace(vm.to_string(a), vm.to_string(b))),
    ("toString", "()Ljava/lang/String;", lambda vm, s: s),
    ("repeat", "(I)Ljava/lang/String;", lambda vm, s, n: s * n),
]:
    native(S, _n, _d)(_f)


def _cmp_str(a, b):
    for x, y in zip(a, b):
        if x != y:
            return ord(x) - ord(y)
    return len(a) - len(b)


for _t in ["Z", "C", "I", "J", "F", "D", "Ljava/lang/Object;", "[C"]:
    native(S, "valueOf", "(%s)Ljava/lang/String;" % _t)(lambda vm, v, _t=_t: jstr(vm, v, _t))


@native(S, "<init>", "([C)V")
def _s_init(vm, this, arr):
    raise RuntimeError("new String(char[]) unsupported in test VM")


# --- StringBuilder
@native(SB, "<init>", "()V")
def _sb_init(vm, this):
    this.nat = []


@native(SB, "<init>", "(I)V")
def _sb_init_i(vm, this, n):
    this.nat = []


@native(SB, "<init>", "(Ljava/lang/String;)V")
def _sb_init_s(vm, this, s):
    this.nat = [s]


for _t in ["Z", "C", "I", "J", "F", "D", "Ljava/lang/Object;", "Ljava/lang/String;",
           "Ljava/lang/CharSequence;", "[C"]:
    def _app(vm, this, v, _t=_t):
        this.nat.append(jstr(vm, v, _t))
        return this
    native(SB, "append", "(%s)Ljava/lang/StringBuilder;" % _t)(_app)
native(SB, "toString", "()Ljava/lang/String;")(lambda vm, this: "".join(this.nat))
native(SB, "length", "()I")(lambda vm, this: len("".join(this.nat)))
native(SB, "reverse", "()Ljava/lang/StringBuilder;")(
    lambda vm, this: (this.nat.__setitem__(slice(None), ["".join(this.nat)[::-1]]), this)[1])
native(SB, "charAt", "(I)C")(lambda vm, this, i: ord("".join(this.nat)[i]))


# --- PrintStream
def _ps_print(nl, t):
    def f(vm, this, v=None):
        vm.out.append(("" if t is None else jstr(vm, v, t)) + ("\n" if nl else ""))
    return f


native(PS, "println", "()V")(_ps_print(True, None))
for _t in ["Z", "C", "I", "J", "F", "D", "Ljava/lang/Object;", "Ljava/lang/String;", "[C"]:
    native(PS, "println", "(%s)V" % _t)(_ps_print(True, _t))
    native(PS, "print", "(%s)V" % _t)(_ps_print(False, _t))

LIB_STATICS = {
    ("Ljava/lang/System;", "out"): lambda vm: vm.__dict__.setdefault("_sysout", JObject(PS)),
}
for _b, _p in BOXES.items():
    LIB_STATICS[(_b, "TYPE")] = (lambda vm, _p=_p: JClass(_p))


# --- boxes
def _box(desc, prim):
    def valueOf(vm, v):
        o = JObject(desc)
        o.nat = v
        return o
    native(desc, "valueOf", "(%s)%s" % (prim, desc))(valueOf)
    native(desc, {"I": "intValue", "J": "longValue", "D": "doubleValue", "F": "floatValue",
                  "Z": "booleanValue", "C": "charValue", "S": "shortValue", "B": "byteValue"}[prim],
           "()" + prim)(lambda vm, this: this.nat)


for _b, _p in BOXES.items():
    _box(_b, _p)
native("Ljava/lang/Integer;", "parseInt", "(Ljava/lang/String;)I")(lambda vm, s: _parse_int(vm, s))
native("Ljava/lang/Integer;", "toString", "(I)Ljava/lang/String;")(lambda vm, v: str(v))
native("Ljava/lang/Integer;", "compare", "(II)I")(lambda vm, a, b: (a > b) - (a < b))
native("Ljava/lang/Number;", "intValue", "()I")(lambda vm, this: int(this.nat))
native("Ljava/lang/Character;", "isDigit", "(C)Z")(lambda vm, c: chr(c).isdigit())
native("Ljava/lang/Character;", "isLetter", "(C)Z")(lambda vm, c: chr(c).isalpha())
native("Ljava/lang/Character;", "toUpperCase", "(C)C")(lambda vm, c: ord(chr(c).upper()))


def _parse_int(vm, s):
    try:
        v = int(s, 10)
        if not -(1 << 31) <= v < (1 << 31) or s.strip() != s or "_" in s:
            raise ValueError
        return v
    except (ValueError, TypeError):
        vm.throw("Ljava/lang/NumberFormatException;", 'For input string: "%s"' % s)


# --- Math
M = "Ljava/lang/Math;"
native(M, "abs", "(I)I")(lambda vm, v: s32(abs(v)))
native(M, "abs", "(J)J")(lambda vm, v: s64(abs(v)))
native(M, "abs", "(D)D")(lambda vm, v: abs(v))
native(M, "abs", "(F)F")(lambda vm, v: abs(v))
native(M, "max", "(II)I")(lambda vm, a, b: max(a, b))
native(M, "min", "(II)I")(lambda vm, a, b: min(a, b))
native(M, "max", "(JJ)J")(lambda vm, a, b: max(a, b))
native(M, "max", "(DD)D")(lambda vm, a, b: max(a, b))
native(M, "min", "(DD)D")(lambda vm, a, b: min(a, b))
native(M, "max", "(FF)F")(lambda vm, a, b: max(a, b))
native(M, "sqrt", "(D)D")(lambda vm, v: math.sqrt(v) if v >= 0 else math.nan)
native(M, "pow", "(DD)D")(lambda vm, a, b: math.pow(a, b))
native(M, "floor", "(D)D")(lambda vm, v: float(math.floor(v)))
native(M, "round", "(D)J")(lambda vm, v: int(math.floor(v + 0.5)))
native(M, "round", "(F)I")(lambda vm, v: int(math.floor(v + 0.5)))

# --- System
native("Ljava/lang/System;", "arraycopy", "(Ljava/lang/Object;ILjava/lang/Object;II)V")(
    lambda vm, src, sp, dst, dp, n: dst.data.__setitem__(slice(dp, dp + n), src.data[sp:sp + n]))
native("Ljava/util/Objects;", "requireNonNull", "(Ljava/lang/Object;)Ljava/lang/Object;")(
    lambda vm, o: o if o is not None else vm.throw("Ljava/lang/NullPointerException;"))


# --- Throwable family
@native("Ljava/lang/Throwable;", "<init>", "()V")
def _t_init(vm, this):
    this.nat = {"msg": None}


@native("Ljava/lang/Throwable;", "<init>", "(Ljava/lang/String;)V")
def _t_init_s(vm, this, msg):
    this.nat = {"msg": msg}


@native("Ljava/lang/Throwable;", "<init>", "(Ljava/lang/String;Ljava/lang/Throwable;)V")
def _t_init_sc(vm, this, msg, cause):
    this.nat = {"msg": msg, "cause": cause}


native("Ljava/lang/Throwable;", "getMessage", "()Ljava/lang/String;")(lambda vm, this: this.nat.get("msg"))
native("Ljava/lang/Throwable;", "getCause", "()Ljava/lang/Throwable;")(lambda vm, this: this.nat.get("cause"))
native("Ljava/lang/Throwable;", "addSuppressed", "(Ljava/lang/Throwable;)V")(lambda vm, this, o: None)
for _e in ["Ljava/lang/Exception;", "Ljava/lang/RuntimeException;", "Ljava/lang/IllegalStateException;",
           "Ljava/lang/IllegalArgumentException;", "Ljava/lang/ArithmeticException;", "Ljava/lang/Error;",
           "Ljava/lang/UnsupportedOperationException;", "Ljava/lang/NullPointerException;"]:
    NATIVES[(_e, "<init>", (), "V")] = _t_init
    NATIVES[(_e, "<init>", (S,), "V")] = _t_init_s
    NATIVES[(_e, "<init>", (S, "Ljava/lang/Throwable;"), "V")] = _t_init_sc


# --- Enum
@native("Ljava/lang/Enum;", "<init>", "(Ljava/lang/String;I)V")
def _enum_init(vm, this, name, ordinal):
    this.nat = {"enum_name": name, "ordinal": ordinal}


native("Ljava/lang/Enum;", "ordinal", "()I")(lambda vm, this: this.nat["ordinal"])
native("Ljava/lang/Enum;", "name", "()Ljava/lang/String;")(lambda vm, this: this.nat["enum_name"])


@native("Ljava/lang/Enum;", "valueOf", "(Ljava/lang/Class;Ljava/lang/String;)Ljava/lang/Enum;")
def _enum_valueof(vm, cls, name):
    vm.init_class(cls.desc)
    for v in vm.statics[cls.desc].values():
        if isinstance(v, JObject) and isinstance(v.nat, dict) and v.nat.get("enum_name") == name:
            return v
    vm.throw("Ljava/lang/IllegalArgumentException;", "No enum constant " + name)


# --- ArrayList / Iterator / HashMap (minimal)
AL = "Ljava/util/ArrayList;"


@native(AL, "<init>", "()V")
def _al_init(vm, this):
    this.nat = []


def _al_get(vm, this, i):
    if not 0 <= i < len(this.nat):
        vm.throw("Ljava/lang/IndexOutOfBoundsException;", "Index %d out of bounds for length %d" % (i, len(this.nat)))
    return this.nat[i]


native(AL, "add", "(Ljava/lang/Object;)Z")(lambda vm, this, o: (this.nat.append(o), True)[1])
native(AL, "get", "(I)Ljava/lang/Object;")(_al_get)
native(AL, "size", "()I")(lambda vm, this: len(this.nat))
native(AL, "isEmpty", "()Z")(lambda vm, this: not this.nat)
native(AL, "set", "(ILjava/lang/Object;)Ljava/lang/Object;")(
    lambda vm, this, i, o: (this.nat[i], this.nat.__setitem__(i, o))[0])
native(AL, "remove", "(I)Ljava/lang/Object;")(lambda vm, this, i: this.nat.pop(i))


@native(AL, "iterator", "()Ljava/util/Iterator;")
def _al_iter(vm, this):
    it = JObject("Ljava/util/ArrayList$Itr;")
    it.nat = [this.nat, 0]
    return it


LIB_SUPER["Ljava/util/ArrayList$Itr;"] = O
LIB_IFACES["Ljava/util/ArrayList$Itr;"] = ["Ljava/util/Iterator;"]
native("Ljava/util/ArrayList$Itr;", "hasNext", "()Z")(lambda vm, this: this.nat[1] < len(this.nat[0]))


@native("Ljava/util/ArrayList$Itr;", "next", "()Ljava/lang/Object;")
def _it_next(vm, this):
    v = this.nat[0][this.nat[1]]
    this.nat[1] += 1
    return v


def run_dex(dex_bytes, main_class):
    vm = VM(dex_bytes)
    return vm.run_main(main_class)


@native("Ljava/lang/reflect/Array;", "newInstance", "(Ljava/lang/Class;[I)Ljava/lang/Object;")
def _array_new(vm, comp, dims):
    ds = dims.data

    def build(level, elem):
        t = "[" * (len(ds) - level) + elem
        n = ds[level]
        if level == len(ds) - 1:
            return JArray(t, [VM.default(elem)] * n)
        return JArray(t, [build(level + 1, elem) for _ in range(n)])
    return build(0, comp.desc)


native(S, "compareTo", "(Ljava/lang/Object;)I")(lambda vm, s, t: _cmp_str(s, t))
native("Ljava/lang/Integer;", "compareTo", "(Ljava/lang/Object;)I")(
    lambda vm, a, b: (a.nat > b.nat) - (a.nat < b.nat))
native("Ljava/lang/Integer;", "compareTo", "(Ljava/lang/Integer;)I")(
    lambda vm, a, b: (a.nat > b.nat) - (a.nat < b.nat))
