"""Java .class file parser (JVMS chapter 4), written from scratch.

Only what the DEX translator needs: constant pool, fields, methods,
Code attributes, exception tables, BootstrapMethods, SourceFile.
Strings are decoded from Java "modified UTF-8" into Python str where each
character is one UTF-16 code unit (lone surrogates preserved), which is
exactly the model DEX uses.
"""
import struct

ACC_PUBLIC = 0x0001
ACC_PRIVATE = 0x0002
ACC_PROTECTED = 0x0004
ACC_STATIC = 0x0008
ACC_FINAL = 0x0010
ACC_SYNCHRONIZED = 0x0020
ACC_SUPER = 0x0020
ACC_VOLATILE = 0x0040
ACC_BRIDGE = 0x0040
ACC_TRANSIENT = 0x0080
ACC_VARARGS = 0x0080
ACC_NATIVE = 0x0100
ACC_INTERFACE = 0x0200
ACC_ABSTRACT = 0x0400
ACC_STRICT = 0x0800
ACC_SYNTHETIC = 0x1000
ACC_ANNOTATION = 0x2000
ACC_ENUM = 0x4000
ACC_MODULE = 0x8000


def decode_mutf8(b):
    """Modified UTF-8 -> str of UTF-16 code units."""
    out = []
    i = 0
    n = len(b)
    while i < n:
        c = b[i]
        if c < 0x80:
            out.append(chr(c))
            i += 1
        elif (c & 0xE0) == 0xC0:
            out.append(chr(((c & 0x1F) << 6) | (b[i + 1] & 0x3F)))
            i += 2
        elif (c & 0xF0) == 0xE0:
            out.append(chr(((c & 0x0F) << 12) | ((b[i + 1] & 0x3F) << 6) | (b[i + 2] & 0x3F)))
            i += 3
        else:
            raise ValueError("bad modified UTF-8 byte 0x%02x" % c)
    return "".join(out)


def encode_mutf8(s):
    out = bytearray()
    for ch in s:
        c = ord(ch)
        if c != 0 and c < 0x80:
            out.append(c)
        elif c < 0x800:
            out.append(0xC0 | (c >> 6))
            out.append(0x80 | (c & 0x3F))
        elif c <= 0xFFFF:
            out.append(0xE0 | (c >> 12))
            out.append(0x80 | ((c >> 6) & 0x3F))
            out.append(0x80 | (c & 0x3F))
        else:  # astral char in a normal Python str: split to surrogates
            c -= 0x10000
            for u in (0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF)):
                out.append(0xE0 | (u >> 12))
                out.append(0x80 | ((u >> 6) & 0x3F))
                out.append(0x80 | (u & 0x3F))
    return bytes(out)


def to_code_units(s):
    """Normalise a Python str so each char is a single UTF-16 code unit."""
    if all(ord(c) <= 0xFFFF for c in s):
        return s
    out = []
    for ch in s:
        c = ord(ch)
        if c > 0xFFFF:
            c -= 0x10000
            out.append(chr(0xD800 + (c >> 10)))
            out.append(chr(0xDC00 + (c & 0x3FF)))
        else:
            out.append(ch)
    return "".join(out)


class Reader:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def u1(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def u2(self):
        v = struct.unpack_from(">H", self.d, self.p)[0]
        self.p += 2
        return v

    def s2(self):
        v = struct.unpack_from(">h", self.d, self.p)[0]
        self.p += 2
        return v

    def u4(self):
        v = struct.unpack_from(">I", self.d, self.p)[0]
        self.p += 4
        return v

    def s4(self):
        v = struct.unpack_from(">i", self.d, self.p)[0]
        self.p += 4
        return v

    def bytes(self, n):
        v = self.d[self.p:self.p + n]
        self.p += n
        return v


def internal_to_desc(name):
    """'java/lang/String' -> 'Ljava/lang/String;'; array names are already descriptors."""
    if name.startswith("["):
        return name
    return "L" + name + ";"


def parse_method_desc(desc):
    """'(IJLjava/lang/String;)V' -> (['I','J','Ljava/lang/String;'], 'V')"""
    assert desc[0] == "("
    params = []
    i = 1
    while desc[i] != ")":
        j = i
        while desc[j] == "[":
            j += 1
        if desc[j] == "L":
            j = desc.index(";", j)
        params.append(desc[i:j + 1])
        i = j + 1
    return params, desc[i + 1:]


def words(t):
    return 2 if t in ("J", "D") else 1


class MemberRef:
    __slots__ = ("owner", "name", "desc", "is_interface")

    def __init__(self, owner, name, desc, is_interface=False):
        self.owner = owner        # type descriptor of the owner class
        self.name = name
        self.desc = desc
        self.is_interface = is_interface

    def __repr__(self):
        return "%s->%s:%s" % (self.owner, self.name, self.desc)


class MethodHandle:
    __slots__ = ("kind", "ref")

    def __init__(self, kind, ref):
        self.kind = kind
        self.ref = ref


class MethodType:
    __slots__ = ("desc",)

    def __init__(self, desc):
        self.desc = desc


class IndyRef:
    __slots__ = ("bsm_index", "name", "desc")

    def __init__(self, bsm_index, name, desc):
        self.bsm_index = bsm_index
        self.name = name
        self.desc = desc


class ClassConst:
    __slots__ = ("desc",)

    def __init__(self, desc):
        self.desc = desc


class StringConst:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class Code:
    def __init__(self):
        self.max_stack = 0
        self.max_locals = 0
        self.code = b""
        self.handlers = []   # (start_pc, end_pc, handler_pc, catch_desc or None)
        self.line_numbers = []  # (start_pc, line)


class Field:
    def __init__(self, access, name, desc):
        self.access = access
        self.name = name
        self.desc = desc
        self.const_value = None  # python value for ConstantValue attribute


class Method:
    def __init__(self, access, name, desc):
        self.access = access
        self.name = name
        self.desc = desc
        self.code = None


class ClassFile:
    def __init__(self, data):
        r = Reader(data)
        if r.u4() != 0xCAFEBABE:
            raise ValueError("not a class file")
        self.minor = r.u2()
        self.major = r.u2()
        n = r.u2()
        self.cp = [None] * n
        raw = [None] * n
        i = 1
        while i < n:
            tag = r.u1()
            if tag == 1:
                ln = r.u2()
                raw[i] = (1, decode_mutf8(r.bytes(ln)))
            elif tag == 3:
                raw[i] = (3, r.s4())
            elif tag == 4:
                raw[i] = (4, r.u4())  # keep raw bits
            elif tag == 5:
                hi = r.u4()
                lo = r.u4()
                v = (hi << 32) | lo
                if v >= 1 << 63:
                    v -= 1 << 64
                raw[i] = (5, v)
                i += 1
            elif tag == 6:
                hi = r.u4()
                lo = r.u4()
                raw[i] = (6, (hi << 32) | lo)  # raw bits
                i += 1
            elif tag in (7, 8, 16, 19, 20):
                raw[i] = (tag, r.u2())
            elif tag in (9, 10, 11, 12, 17, 18):
                raw[i] = (tag, r.u2(), r.u2())
            elif tag == 15:
                raw[i] = (15, r.u1(), r.u2())
            else:
                raise ValueError("unknown constant pool tag %d" % tag)
            i += 1
        self._raw = raw

        self.access = r.u2()
        self.name = self.class_name(r.u2())
        sidx = r.u2()
        self.super_name = self.class_name(sidx) if sidx else None
        self.interfaces = [self.class_name(r.u2()) for _ in range(r.u2())]
        self.fields = []
        for _ in range(r.u2()):
            f = Field(r.u2(), self.utf8(r.u2()), self.utf8(r.u2()))
            for _ in range(r.u2()):
                an = self.utf8(r.u2())
                alen = r.u4()
                body = r.bytes(alen)
                if an == "ConstantValue":
                    f.const_value = self.const(struct.unpack(">H", body)[0])
            self.fields.append(f)
        self.methods = []
        for _ in range(r.u2()):
            m = Method(r.u2(), self.utf8(r.u2()), self.utf8(r.u2()))
            for _ in range(r.u2()):
                an = self.utf8(r.u2())
                alen = r.u4()
                body = r.bytes(alen)
                if an == "Code":
                    m.code = self._parse_code(body)
            self.methods.append(m)
        self.source_file = None
        self.bootstrap = []
        for _ in range(r.u2()):
            an = self.utf8(r.u2())
            alen = r.u4()
            body = r.bytes(alen)
            if an == "SourceFile":
                self.source_file = self.utf8(struct.unpack(">H", body)[0])
            elif an == "BootstrapMethods":
                br = Reader(body)
                for _ in range(br.u2()):
                    mh = br.u2()
                    args = [br.u2() for _ in range(br.u2())]
                    self.bootstrap.append((mh, args))

    # ---- constant pool helpers
    def utf8(self, i):
        t = self._raw[i]
        assert t[0] == 1
        return t[1]

    def class_name(self, i):
        t = self._raw[i]
        assert t[0] == 7, t
        return self.utf8(t[1])

    def class_desc(self, i):
        return internal_to_desc(self.class_name(i))

    def member(self, i):
        t = self._raw[i]
        assert t[0] in (9, 10, 11), t
        owner = self.class_desc(t[1])
        nt = self._raw[t[2]]
        return MemberRef(owner, self.utf8(nt[1]), self.utf8(nt[2]), t[0] == 11)

    def const(self, i):
        """Loadable constant -> ('I', int) | ('F', bits) | ('J', int) | ('D', bits)
        | StringConst | ClassConst | MethodType | MethodHandle"""
        t = self._raw[i]
        tag = t[0]
        if tag == 3:
            return ("I", t[1])
        if tag == 4:
            return ("F", t[1])
        if tag == 5:
            return ("J", t[1])
        if tag == 6:
            return ("D", t[1])
        if tag == 8:
            return StringConst(self.utf8(t[1]))
        if tag == 7:
            return ClassConst(self.class_desc(i))
        if tag == 16:
            return MethodType(self.utf8(t[1]))
        if tag == 15:
            return MethodHandle(t[1], self.member(t[2]))
        raise ValueError("unsupported constant tag %d" % tag)

    def indy(self, i):
        t = self._raw[i]
        if t[0] != 18:
            raise ValueError("expected InvokeDynamic constant")
        nt = self._raw[t[2]]
        return IndyRef(t[1], self.utf8(nt[1]), self.utf8(nt[2]))

    def _parse_code(self, body):
        r = Reader(body)
        c = Code()
        c.max_stack = r.u2()
        c.max_locals = r.u2()
        c.code = r.bytes(r.u4())
        for _ in range(r.u2()):
            s, e, h, t = r.u2(), r.u2(), r.u2(), r.u2()
            c.handlers.append((s, e, h, self.class_desc(t) if t else None))
        for _ in range(r.u2()):
            an = self.utf8(r.u2())
            alen = r.u4()
            ab = r.bytes(alen)
            if an == "LineNumberTable":
                ar = Reader(ab)
                for _ in range(ar.u2()):
                    c.line_numbers.append((ar.u2(), ar.u2()))
        return c
