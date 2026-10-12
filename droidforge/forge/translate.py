"""JVM bytecode -> Dalvik bytecode translator.

Strategy (register-mapped stack machine):
  * v0..v5 are scratch registers (always < 16, used to satisfy 4-bit operand
    formats and for shuffles),
  * JVM operand-stack slot i (in 32-bit units) lives in register v(6+i),
  * JVM locals follow, with the method parameters in the highest registers as
    Dalvik requires.
A type-flow analysis over the JVM code gives the category (int/float, wide,
reference) of every stack slot and local at every instruction, which selects
the right move/aget/iget/return variants.  Lambdas (invokedynamic with
LambdaMetafactory) are desugared into generated classes.
"""
import struct

from . import dalvik as D
from .classfile import (ACC_ABSTRACT, ACC_INTERFACE, ACC_NATIVE, ACC_PRIVATE, ACC_STATIC,
                        ACC_SYNCHRONIZED, ClassConst, MethodHandle, MethodType, StringConst,
                        internal_to_desc, parse_method_desc, words)
from .dexwriter import ACC_CONSTRUCTOR, ACC_DECLARED_SYNCHRONIZED, DexClass, DexCode, DexField, DexMethod

NS = 6  # scratch registers


class TranslateError(Exception):
    pass


# ----------------------------------------------------------------- JVM opcodes
JVM_NAMES = ("nop aconst_null iconst_m1 iconst_0 iconst_1 iconst_2 iconst_3 iconst_4 iconst_5 lconst_0 "
             "lconst_1 fconst_0 fconst_1 fconst_2 dconst_0 dconst_1 bipush sipush ldc ldc_w ldc2_w iload "
             "lload fload dload aload iload_0 iload_1 iload_2 iload_3 lload_0 lload_1 lload_2 lload_3 "
             "fload_0 fload_1 fload_2 fload_3 dload_0 dload_1 dload_2 dload_3 aload_0 aload_1 aload_2 "
             "aload_3 iaload laload faload daload aaload baload caload saload istore lstore fstore dstore "
             "astore istore_0 istore_1 istore_2 istore_3 lstore_0 lstore_1 lstore_2 lstore_3 fstore_0 "
             "fstore_1 fstore_2 fstore_3 dstore_0 dstore_1 dstore_2 dstore_3 astore_0 astore_1 astore_2 "
             "astore_3 iastore lastore fastore dastore aastore bastore castore sastore pop pop2 dup dup_x1 "
             "dup_x2 dup2 dup2_x1 dup2_x2 swap iadd ladd fadd dadd isub lsub fsub dsub imul lmul fmul dmul "
             "idiv ldiv fdiv ddiv irem lrem frem drem ineg lneg fneg dneg ishl lshl ishr lshr iushr lushr "
             "iand land ior lor ixor lxor iinc i2l i2f i2d l2i l2f l2d f2i f2l f2d d2i d2l d2f i2b i2c i2s "
             "lcmp fcmpl fcmpg dcmpl dcmpg ifeq ifne iflt ifge ifgt ifle if_icmpeq if_icmpne if_icmplt "
             "if_icmpge if_icmpgt if_icmple if_acmpeq if_acmpne goto jsr ret tableswitch lookupswitch "
             "ireturn lreturn freturn dreturn areturn return getstatic putstatic getfield putfield "
             "invokevirtual invokespecial invokestatic invokeinterface invokedynamic new newarray "
             "anewarray arraylength athrow checkcast instanceof monitorenter monitorexit wide "
             "multianewarray ifnull ifnonnull goto_w jsr_w").split()
assert len(JVM_NAMES) == 202
OPC = {n: i for i, n in enumerate(JVM_NAMES)}


class JIns:
    __slots__ = ("pc", "name", "a", "next", "targets")

    def __init__(self, pc, name, a, nxt):
        self.pc, self.name, self.a, self.next = pc, name, a, nxt
        self.targets = []

    def __repr__(self):
        return "%d:%s %s" % (self.pc, self.name, self.a)


def decode_jvm(code):
    out = []
    pc = 0
    n = len(code)

    def u1(p):
        return code[p]

    def s1(p):
        v = code[p]
        return v - 256 if v > 127 else v

    def u2(p):
        return (code[p] << 8) | code[p + 1]

    def s2(p):
        v = u2(p)
        return v - 65536 if v > 32767 else v

    def s4(p):
        return struct.unpack_from(">i", code, p)[0]

    while pc < n:
        op = code[pc]
        if op >= 202:
            raise TranslateError("unknown JVM opcode %d at pc %d" % (op, pc))
        name = JVM_NAMES[op]
        a = ()
        ln = 1
        if name in ("bipush",):
            a, ln = (s1(pc + 1),), 2
        elif name == "sipush":
            a, ln = (s2(pc + 1),), 3
        elif name == "ldc":
            a, ln = (u1(pc + 1),), 2
        elif name in ("ldc_w", "ldc2_w"):
            a, ln = (u2(pc + 1),), 3
        elif name in ("iload", "lload", "fload", "dload", "aload", "istore", "lstore", "fstore",
                      "dstore", "astore", "ret"):
            a, ln = (u1(pc + 1),), 2
        elif "_" in name and name.split("_")[0] in ("iload", "lload", "fload", "dload", "aload", "istore",
                                                    "lstore", "fstore", "dstore", "astore") \
                and name[-1].isdigit():
            base, idx = name.split("_")
            name, a = base, (int(idx),)
        elif name == "iinc":
            a, ln = (u1(pc + 1), s1(pc + 2)), 3
        elif name.startswith("if") or name in ("goto", "jsr"):
            a, ln = (pc + s2(pc + 1),), 3
        elif name in ("goto_w", "jsr_w"):
            name = name[:-2]
            a, ln = (pc + s4(pc + 1),), 5
        elif name == "tableswitch":
            p = (pc + 4) & ~3
            default, low, high = s4(p), s4(p + 4), s4(p + 8)
            offs = [pc + s4(p + 12 + 4 * i) for i in range(high - low + 1)]
            a = (pc + default, low, offs)
            ln = p + 12 + 4 * (high - low + 1) - pc
        elif name == "lookupswitch":
            p = (pc + 4) & ~3
            default, npairs = s4(p), s4(p + 4)
            pairs = [(s4(p + 8 + 8 * i), pc + s4(p + 12 + 8 * i)) for i in range(npairs)]
            a = (pc + default, pairs)
            ln = p + 8 + 8 * npairs - pc
        elif name in ("getstatic", "putstatic", "getfield", "putfield", "invokevirtual", "invokespecial",
                      "invokestatic", "new", "anewarray", "checkcast", "instanceof"):
            a, ln = (u2(pc + 1),), 3
        elif name in ("invokeinterface", "invokedynamic"):
            a, ln = (u2(pc + 1),), 5
        elif name == "newarray":
            a, ln = (u1(pc + 1),), 2
        elif name == "multianewarray":
            a, ln = (u2(pc + 1), u1(pc + 3)), 4
        elif name == "wide":
            op2 = JVM_NAMES[code[pc + 1]]
            if op2 == "iinc":
                name, a, ln = "iinc", (u2(pc + 2), s2(pc + 4)), 6
            else:
                name, a, ln = op2, (u2(pc + 2),), 4
        out.append(JIns(pc, name, a, pc + ln))
        pc += ln
    return out


# ----------------------------------------------------------------- types
OBJ = "Ljava/lang/Object;"
THROWABLE = "Ljava/lang/Throwable;"


def norm(t):
    return "I" if t in ("Z", "B", "C", "S", "I") else t


def is_ref(t):
    return t[0] in "L[NU"


def kind(t):
    if t in ("I", "F"):
        return "I"
    if t in ("J", "D"):
        return "W"
    if t in ("T", "h"):
        return None
    return "A"


def merge_t(a, b):
    if a == b:
        return a
    if is_ref(a) and is_ref(b):
        if a == "N":
            return b
        if b == "N":
            return a
        if a[0] == "U" or b[0] == "U":
            return "T"
        return OBJ
    return "T"


def push_t(stack, t):
    t = norm(t)
    stack.append(t)
    if t in ("J", "D"):
        stack.append("h")


BOX = {"Z": "Ljava/lang/Boolean;", "B": "Ljava/lang/Byte;", "C": "Ljava/lang/Character;",
       "S": "Ljava/lang/Short;", "I": "Ljava/lang/Integer;", "J": "Ljava/lang/Long;",
       "F": "Ljava/lang/Float;", "D": "Ljava/lang/Double;"}
UNBOX_NAME = {"Z": "booleanValue", "B": "byteValue", "C": "charValue", "S": "shortValue",
              "I": "intValue", "J": "longValue", "F": "floatValue", "D": "doubleValue"}

FIELD_SUFFIX = {"I": 0, "F": 0, "J": 1, "D": 1, "Z": 3, "B": 4, "C": 5, "S": 6}


def field_variant(t):
    return FIELD_SUFFIX.get(t, 2)


NEWARRAY_T = {4: "[Z", 5: "[C", 6: "[F", 7: "[D", 8: "[B", 9: "[S", 10: "[I", 11: "[J"}


# ----------------------------------------------------------------- emitter
class Emitter:
    def __init__(self):
        self.items = []
        self.outs = 0

    def I(self, op, *args):
        ins = D.Insn(op, *args)
        self.items.append(ins)
        return ins

    def label(self, lbl):
        self.items.append(lbl)

    def mv(self, dst, src, k):
        if dst == src or k is None:
            return
        base = {"I": 0x01, "W": 0x04, "A": 0x07}[k]
        hi = 1 if k == "W" else 0
        if dst + hi < 16 and src + hi < 16:
            self.I(base, dst, src)
        elif dst + hi < 256:
            self.I(base + 1, dst, src)
        else:
            self.I(base + 2, dst, src)

    def src(self, reg, k, limit, scratch):
        """Return a register <= limit holding the value of reg (moving via scratch)."""
        if reg + (1 if k == "W" else 0) <= limit:
            return reg
        self.mv(scratch, reg, k)
        return scratch

    def dst(self, reg, k, limit, scratch, fn):
        if reg + (1 if k == "W" else 0) <= limit:
            fn(reg)
        else:
            fn(scratch)
            self.mv(reg, scratch, k)

    def const32(self, dst, v, k="I"):
        v = ((v + 0x80000000) & 0xFFFFFFFF) - 0x80000000

        def f(r):
            if r < 16 and -8 <= v <= 7:
                self.I(0x12, r, v)
            elif -32768 <= v <= 32767:
                self.I(0x13, r, v)
            elif v & 0xFFFF == 0:
                self.I(0x15, r, v >> 16)
            else:
                self.I(0x14, r, v)
        self.dst(dst, k, 255, 0, f)

    def const64(self, dst, v):
        v = ((v + (1 << 63)) & ((1 << 64) - 1)) - (1 << 63)

        def f(r):
            if -32768 <= v <= 32767:
                self.I(0x16, r, v)
            elif -(1 << 31) <= v < (1 << 31):
                self.I(0x17, r, v)
            elif v & 0xFFFFFFFFFFFF == 0:
                self.I(0x19, r, v >> 48)
            else:
                self.I(0x18, r, v)
        self.dst(dst, "W", 255, 0, f)

    def invoke(self, op_range, first, count, key):
        self.I(op_range, first if count else 0, count, key)
        self.outs = max(self.outs, count)

    def move_result(self, reg, t):
        k = kind(norm(t))
        op = {"I": 0x0a, "W": 0x0b, "A": 0x0c}[k]
        self.dst(reg, k, 255, 0, lambda r: self.I(op, r))


def mkey(ref):
    params, ret = parse_method_desc(ref.desc)
    return (ref.owner, ref.name, tuple(params), ret)


# ----------------------------------------------------------------- method translation
class MethodTranslator:
    def __init__(self, ctx, cf, m):
        self.ctx, self.cf, self.m = ctx, cf, m
        self.cls = internal_to_desc(cf.name)
        c = m.code
        self.code = c
        self.L = c.max_locals
        self.S = c.max_stack
        params, ret = parse_method_desc(m.desc)
        self.params, self.ret = params, ret
        self.static = bool(m.access & ACC_STATIC)
        self.P = sum(words(p) for p in params) + (0 if self.static else 1)
        if self.L < self.P:
            raise TranslateError("max_locals < parameter words")
        self.sync = bool(m.access & ACC_SYNCHRONIZED)
        self.X = 1 if self.sync else 0     # extra registers (lock holder)
        self.lockreg = NS + self.S
        self.nregs = NS + self.S + self.X + self.L

    def st(self, i):
        return NS + i

    def loc(self, j):
        if j < self.P:
            return NS + self.S + self.X + (self.L - self.P) + j
        return NS + self.S + self.X + (j - self.P)

    def src_lock(self, E):
        return E.src(self.lockreg, "A", 255, 5)

    # -------------------------------------------------- analysis
    def initial_state(self):
        loc = ["T"] * self.L
        i = 0
        if not self.static:
            if self.m.name == "<init>" and self.cls != OBJ:
                loc[0] = "Uthis"
            else:
                loc[0] = self.cls
            i = 1
        for p in self.params:
            t = norm(p)
            loc[i] = t
            if t in ("J", "D"):
                loc[i + 1] = "h"
            i += words(p)
        return (loc, [])

    def run(self):
        code = self.code
        insns = decode_jvm(code.code)
        self.insns = insns
        by_pc = {ins.pc: ins for ins in insns}
        self.by_pc = by_pc
        # handler lists per pc
        hl = {}
        for ins in insns:
            lst = []
            seen_types = set()
            for (s, e, h, t) in code.handlers:
                if s <= ins.pc < e:
                    if t in seen_types:
                        continue
                    seen_types.add(t)
                    lst.append((t, h))
                    if t is None:
                        break
            hl[ins.pc] = tuple(lst)
        self.hlist = hl
        self.handler_pcs = {h for (_, _, h, _) in code.handlers}

        # dataflow
        states = {}
        work = []

        def flow(pc, st):
            if pc not in by_pc:
                raise TranslateError("branch to invalid pc %d" % pc)
            loc, stk = st
            old = states.get(pc)
            if old is None:
                states[pc] = (list(loc), list(stk))
                work.append(pc)
                return
            oloc, ostk = old
            if len(ostk) != len(stk):
                raise TranslateError("stack height mismatch at pc %d" % pc)
            changed = False
            for arr_o, arr_n in ((oloc, loc), (ostk, stk)):
                for i in range(len(arr_o)):
                    mt = merge_t(arr_o[i], arr_n[i])
                    if mt != arr_o[i]:
                        arr_o[i] = mt
                        changed = True
            if changed:
                work.append(pc)

        flow(0, self.initial_state())
        while work:
            pc = work.pop()
            ins = by_pc[pc]
            loc, stk = states[pc]
            for (t, h) in hl[pc]:
                flow(h, (loc, [t or THROWABLE]))
            outs = self.step(ins, list(loc), list(stk), None)
            for (tpc, st) in outs:
                flow(tpc, st)
        self.states = states

        # emission
        E = Emitter()
        self.E = E
        labels = {ins.pc: D.Label(str(ins.pc)) for ins in insns}
        end_label = D.Label("end")
        self.labels = labels
        lines = dict(code.line_numbers)
        line_entries = []
        targets = set(self.handler_pcs)
        for ins in insns:
            if ins.name.startswith("if") or ins.name == "goto":
                targets.add(ins.a[0])
            elif ins.name == "tableswitch":
                targets.update([ins.a[0]] + list(ins.a[2]))
            elif ins.name == "lookupswitch":
                targets.update([ins.a[0]] + [t for _, t in ins.a[1]])
        self.prev = []
        sync_handler = D.Label("sync")
        if self.sync:
            if self.static:
                E.I(0x1c, self.lockreg, self.cls)
            else:
                E.mv(self.lockreg, self.loc(0), "A")
            E.I(0x1d, self.src_lock(E))
        for ins in insns:
            E.label(labels[ins.pc])
            if ins.pc in targets:
                self.prev = []
            if ins.pc not in states:
                self.prev = []
                continue
            if ins.pc in lines:
                line_entries.append((labels[ins.pc], lines[ins.pc]))
            loc, stk = states[ins.pc]
            if ins.pc in self.handler_pcs:
                E.I(0x0d, self.st(0))  # move-exception
            self.step(ins, list(loc), list(stk), E)
            self.prev = (self.prev + [ins])[-2:]
        E.label(end_label)
        if self.sync:
            E.label(sync_handler)
            E.I(0x0d, 0)
            E.I(0x1e, self.src_lock(E))
            E.I(0x27, 0)

        # try regions
        tries = []
        run_start = None
        run_h = ()
        order = [ins for ins in insns]
        if self.sync:
            labels["SYNC"] = sync_handler
        for idx, ins in enumerate(order):
            h = hl[ins.pc] if ins.pc in states else ()
            if self.sync and ins.pc in states and not (h and h[-1][0] is None):
                h = h + ((None, "SYNC"),)
            if h != run_h:
                if run_h:
                    tries.append((run_start, labels[ins.pc], run_h))
                run_start, run_h = labels[ins.pc], h
        if run_h:
            tries.append((run_start, end_label, run_h))
        regions = []
        for (s, e, h) in tries:
            typed = [(t, labels[hp]) for (t, hp) in h if t is not None]
            ca = [labels[hp] for (t, hp) in h if t is None]
            regions.append(D.TryRegion(s, e, typed, ca[0] if ca else None))
        return DexCode(self.nregs, self.P, E.outs, E.items, regions, line_entries)

    # -------------------------------------------------- the big step
    def step(self, ins, loc, stk, E):
        """Apply ins to (loc, stk); emit Dalvik code if E.  Returns successors."""
        n = ins.name
        a = ins.a
        d = len(stk)
        st = self.st
        cf = self.cf
        nxt = ins.next

        def fall():
            return [(nxt, (loc, stk))]

        def pop(nunits):
            del stk[len(stk) - nunits:]

        # ---- constants
        if n == "nop":
            return fall()
        if n == "aconst_null":
            if E:
                E.const32(st(d), 0, "A")
            stk.append("N")
            return fall()
        if n.startswith("iconst_") or n in ("bipush", "sipush"):
            v = a[0] if a else (-1 if n == "iconst_m1" else int(n[-1]))
            if E:
                E.const32(st(d), v)
            stk.append("I")
            return fall()
        if n.startswith("fconst_"):
            v = struct.unpack(">I", struct.pack(">f", float(n[-1])))[0]
            if E:
                E.const32(st(d), v)
            stk.append("F")
            return fall()
        if n.startswith("lconst_") or n.startswith("dconst_"):
            if n[0] == "l":
                v, t = int(n[-1]), "J"
            else:
                v, t = struct.unpack(">Q", struct.pack(">d", float(n[-1])))[0], "D"
            if E:
                E.const64(st(d), v)
            push_t(stk, t)
            return fall()
        if n in ("ldc", "ldc_w", "ldc2_w"):
            c = cf.const(a[0])
            if isinstance(c, tuple):
                t, v = c
                if E:
                    if t in ("I", "F"):
                        E.const32(st(d), v)
                    else:
                        E.const64(st(d), v)
                push_t(stk, t)
            elif isinstance(c, StringConst):
                if E:
                    E.dst(st(d), "A", 255, 0, lambda r: E.I(0x1a, r, c.value))
                stk.append("Ljava/lang/String;")
            elif isinstance(c, ClassConst):
                if E:
                    E.dst(st(d), "A", 255, 0, lambda r: E.I(0x1c, r, c.desc))
                stk.append("Ljava/lang/Class;")
            else:
                raise TranslateError("ldc of MethodHandle/MethodType is not supported")
            return fall()

        # ---- locals
        if n in ("iload", "fload", "aload", "lload", "dload"):
            j = a[0]
            t = loc[j]
            if n == "aload" and t != "T" and not is_ref(t):
                raise TranslateError("aload of non-reference local %d (%s) at pc %d" % (j, t, ins.pc))
            if E:
                E.mv(st(d), self.loc(j), kind(t) if t != "T" else {"i": "I", "f": "I", "a": "A"}.get(n[0], "W"))
            if t in ("J", "D"):
                stk += [t, "h"]
            elif t == "T":
                push_t(stk, {"i": "I", "f": "F", "a": OBJ, "l": "J", "d": "D"}[n[0]])
            else:
                stk.append(t)
            return fall()
        if n in ("istore", "fstore", "astore", "lstore", "dstore"):
            j = a[0]
            wide = n[0] in "ld"
            t = stk[-2] if wide else stk[-1]
            if E:
                E.mv(self.loc(j), st(d - (2 if wide else 1)), kind(t) or ("W" if wide else "I"))
            # invalidate halves of wide locals we overwrite
            if j > 0 and loc[j - 1] in ("J", "D"):
                loc[j - 1] = "T"
            if loc[j] in ("J", "D") and j + 1 < self.L:
                loc[j + 1] = "T"
            if wide:
                if loc[j + 1] in ("J", "D") and j + 2 < self.L:
                    loc[j + 2] = "T"
                loc[j], loc[j + 1] = t, "h"
                pop(2)
            else:
                loc[j] = t
                pop(1)
            return fall()
        if n == "iinc":
            j, c = a
            if E:
                r = self.loc(j)
                if r < 256 and -128 <= c <= 127:
                    E.I(0xd8, r, r, c)
                elif r < 16:
                    E.I(0xd0, r, r, c)
                else:
                    E.const32(0, c)
                    rr = E.src(r, "I", 255, 1)
                    E.I(0x90, rr, rr, 0)
                    E.mv(r, rr, "I")
            return fall()

        # ---- arrays
        if n in ("iaload", "laload", "faload", "daload", "aaload", "baload", "caload", "saload"):
            arr_t = stk[-2]
            if n == "aaload":
                rt = arr_t[1:] if arr_t.startswith("[") else OBJ
                var = 2
            else:
                rt = {"i": "I", "l": "J", "f": "F", "d": "D", "b": "I", "c": "I", "s": "I"}[n[0]]
                var = {"i": 0, "l": 1, "f": 0, "d": 1, "c": 5, "s": 6}.get(n[0])
                if n[0] == "b":
                    var = 3 if arr_t == "[Z" else 4
            if E:
                ra = E.src(st(d - 2), "A", 255, 2)
                ri = E.src(st(d - 1), "I", 255, 3)
                E.dst(st(d - 2), kind(norm(rt)), 255, 0, lambda r: E.I(0x44 + var, r, ra, ri))
            pop(2)
            push_t(stk, rt)
            return fall()
        if n in ("iastore", "lastore", "fastore", "dastore", "aastore", "bastore", "castore", "sastore"):
            wide = n[0] in "ld"
            vw = 2 if wide else 1
            arr_t = stk[-1 - vw - 1]
            var = {"i": 0, "l": 1, "f": 0, "d": 1, "a": 2, "c": 5, "s": 6}.get(n[0])
            if n[0] == "b":
                var = 3 if arr_t == "[Z" else 4
            if E:
                vk = "W" if wide else ("A" if n[0] == "a" else "I")
                rv = E.src(st(d - vw), vk, 255, 0)
                ri = E.src(st(d - vw - 1), "I", 255, 2)
                ra = E.src(st(d - vw - 2), "A", 255, 3)
                E.I(0x4b + var, rv, ra, ri)
            pop(vw + 2)
            return fall()
        if n == "arraylength":
            if E:
                rs = E.src(st(d - 1), "A", 15, 1)
                E.dst(st(d - 1), "I", 15, 0, lambda r: E.I(0x21, r, rs))
            pop(1)
            stk.append("I")
            return fall()
        if n in ("newarray", "anewarray"):
            if n == "newarray":
                at = NEWARRAY_T[a[0]]
            else:
                at = "[" + cf.class_desc(a[0])
            if E:
                rs = E.src(st(d - 1), "I", 15, 1)
                E.dst(st(d - 1), "A", 15, 0, lambda r: E.I(0x23, r, rs, at))
            pop(1)
            stk.append(at)
            return fall()
        if n == "multianewarray":
            at = cf.class_desc(a[0])
            dims = a[1]
            if E:
                E.const32(0, dims)
                E.I(0x23, 1, 0, "[I")
                for i in range(dims):
                    E.const32(0, i)
                    rv = E.src(st(d - dims + i), "I", 255, 2)
                    E.I(0x4b, rv, 1, 0)
                comp = at[dims:]
                if comp in BOX:
                    E.I(0x62, 0, (BOX[comp], "TYPE", "Ljava/lang/Class;"))
                else:
                    E.I(0x1c, 0, comp)
                E.invoke(0x77, 0, 2, ("Ljava/lang/reflect/Array;", "newInstance",
                                      ("Ljava/lang/Class;", "[I"), OBJ))
                E.I(0x0c, 0)
                E.I(0x1f, 0, at)
                E.mv(st(d - dims), 0, "A")
            pop(dims)
            stk.append(at)
            return fall()

        # ---- stack manipulation
        if n in ("pop", "pop2"):
            pop(1 if n == "pop" else 2)
            return fall()
        if n in ("dup", "dup_x1", "dup_x2", "dup2", "dup2_x1", "dup2_x2", "swap"):
            # entries from top: list of (type, width)
            ents = []
            i = len(stk)
            while i > 0 and len(ents) < 4:
                if stk[i - 1] == "h":
                    ents.append((stk[i - 2], 2))
                    i -= 2
                else:
                    ents.append((stk[i - 1], 1))
                    i -= 1
            # ents[0] is top.  Build patterns in terms of entry indices (bottom..top).
            w = [e[1] for e in ents]
            if n == "dup":
                take, out = 1, [0, 0]
            elif n == "dup_x1":
                take, out = 2, [0, 1, 0]
            elif n == "dup_x2":
                take, out = (3, [0, 2, 1, 0]) if w[1] == 1 else (2, [0, 1, 0])
            elif n == "dup2":
                take, out = (2, [1, 0, 1, 0]) if w[0] == 1 else (1, [0, 0])
            elif n == "dup2_x1":
                take, out = (3, [1, 0, 2, 1, 0]) if w[0] == 1 else (2, [0, 1, 0])
            elif n == "dup2_x2":
                if w[0] == 1 and w[1] == 1 and w[2] == 1:
                    take, out = 4, [1, 0, 3, 2, 1, 0]
                elif w[0] == 2 and w[1] == 1:
                    take, out = 3, [0, 2, 1, 0]
                elif w[0] == 1 and w[1] == 1 and w[2] == 2:
                    take, out = 3, [1, 0, 2, 1, 0]
                else:
                    take, out = 2, [0, 1, 0]
            else:  # swap
                take, out = 2, [0, 1]
            # 'out' lists entry indices (0 = top) from bottom to top of result
            taken = ents[:take]
            base = len(stk) - sum(e[1] for e in taken)
            if E:
                if n == "dup" and taken[0][1] == 1:
                    E.mv(st(d), st(d - 1), kind(taken[0][0]))
                else:
                    # copy taken entries into scratch v0.. (bottom first)
                    sp = {}
                    pos = base
                    s = 0
                    for idx in reversed(range(take)):
                        t, wd = taken[idx]
                        E.mv(s, st(pos), kind(t))
                        sp[idx] = s
                        s += wd
                        pos += wd
                    pos = base
                    for idx in out:
                        t, wd = taken[idx]
                        E.mv(st(pos), sp[idx], kind(t))
                        pos += wd
            del stk[base:]
            for idx in out:
                t, wd = taken[idx]
                stk.append(t)
                if wd == 2:
                    stk.append("h")
            return fall()

        # ---- arithmetic
        ARITH = {"add": 0, "sub": 1, "mul": 2, "div": 3, "rem": 4, "and": 5, "or": 6, "xor": 7,
                 "shl": 8, "shr": 9, "ushr": 10}
        if n[1:] in ARITH and n[0] in "ilfd":
            t = {"i": "I", "l": "J", "f": "F", "d": "D"}[n[0]]
            opi = ARITH[n[1:]]
            base = {"I": 0x90, "J": 0x9b, "F": 0xa6, "D": 0xab}[t]
            op = base + opi
            if t == "J" and opi >= 8:  # long shift: long, int
                ra_, rb_, rd_ = d - 3, d - 1, d - 3
                ka, kb = "W", "I"
                npop = 3
            elif t in ("J", "D"):
                ra_, rb_, rd_ = d - 4, d - 2, d - 4
                ka = kb = "W"
                npop = 4
            else:
                ra_, rb_, rd_ = d - 2, d - 1, d - 2
                ka = kb = "I"
                npop = 2
            if E:
                rA = E.src(st(ra_), ka, 255, 0)
                rB = E.src(st(rb_), kb, 255, 2)
                E.dst(st(rd_), ka, 255, 4, lambda r: E.I(op, r, rA, rB))
            pop(npop)
            push_t(stk, t)
            return fall()
        if n in ("ineg", "lneg", "fneg", "dneg"):
            t = n[0].upper()
            t = {"I": "I", "L": "J", "F": "F", "D": "D"}[t]
            op = {"I": 0x7b, "J": 0x7d, "F": 0x7f, "D": 0x80}[t]
            k = kind(t)
            if E:
                w1 = 2 if k == "W" else 1
                rs = E.src(st(d - w1), k, 15, 2)
                E.dst(st(d - w1), k, 15, 0, lambda r: E.I(op, r, rs))
            return fall()
        CONV = {"i2l": (0x81, "I", "J"), "i2f": (0x82, "I", "F"), "i2d": (0x83, "I", "D"),
                "l2i": (0x84, "J", "I"), "l2f": (0x85, "J", "F"), "l2d": (0x86, "J", "D"),
                "f2i": (0x87, "F", "I"), "f2l": (0x88, "F", "J"), "f2d": (0x89, "F", "D"),
                "d2i": (0x8a, "D", "I"), "d2l": (0x8b, "D", "J"), "d2f": (0x8c, "D", "F"),
                "i2b": (0x8d, "I", "I"), "i2c": (0x8e, "I", "I"), "i2s": (0x8f, "I", "I")}
        if n in CONV:
            op, ft, tt = CONV[n]
            fw, tw = words(ft), words(tt)
            if E:
                rs = E.src(st(d - fw), kind(ft), 15, 2)
                E.dst(st(d - fw), kind(tt), 15, 0, lambda r: E.I(op, r, rs))
            pop(fw)
            push_t(stk, tt)
            return fall()
        if n in ("lcmp", "fcmpl", "fcmpg", "dcmpl", "dcmpg"):
            op = {"lcmp": 0x31, "fcmpl": 0x2d, "fcmpg": 0x2e, "dcmpl": 0x2f, "dcmpg": 0x30}[n]
            wide = n[0] in "ld"
            w1 = 2 if wide else 1
            k = "W" if wide else "I"
            if E:
                rA = E.src(st(d - 2 * w1), k, 255, 0)
                rB = E.src(st(d - w1), k, 255, 2)
                E.dst(st(d - 2 * w1), "I", 255, 4, lambda r: E.I(op, r, rA, rB))
            pop(2 * w1)
            stk.append("I")
            return fall()

        # ---- branches
        ZOPS = {"ifeq": 0x38, "ifne": 0x39, "iflt": 0x3a, "ifge": 0x3b, "ifgt": 0x3c, "ifle": 0x3d,
                "ifnull": 0x38, "ifnonnull": 0x39}
        COPS = {"if_icmpeq": 0x32, "if_icmpne": 0x33, "if_icmplt": 0x34, "if_icmpge": 0x35,
                "if_icmpgt": 0x36, "if_icmple": 0x37, "if_acmpeq": 0x32, "if_acmpne": 0x33}
        if n in ZOPS:
            k = "A" if "null" in n else "I"
            if E:
                r = E.src(st(d - 1), k, 255, 0)
                E.I(ZOPS[n], r, self.labels[a[0]])
            pop(1)
            return [(nxt, (loc, stk)), (a[0], (list(loc), list(stk)))]
        if n in COPS:
            k = "A" if "acmp" in n else "I"
            if E:
                rA = E.src(st(d - 2), k, 15, 0)
                rB = E.src(st(d - 1), k, 15, 1)
                E.I(COPS[n], rA, rB, self.labels[a[0]])
            pop(2)
            return [(nxt, (loc, stk)), (a[0], (list(loc), list(stk)))]
        if n == "goto":
            if E:
                E.I(0x2a, self.labels[a[0]])
            return [(a[0], (loc, stk))]
        if n in ("jsr", "ret"):
            raise TranslateError("jsr/ret (pre-Java-6 subroutines) are not supported")
        if n in ("tableswitch", "lookupswitch"):
            default = a[0]
            if n == "tableswitch":
                low, offs = a[1], a[2]
                keys = list(range(low, low + len(offs)))
                targets = offs
                packed = True
            else:
                pairs = sorted(a[1])
                keys = [k for k, _ in pairs]
                targets = [t for _, t in pairs]
                packed = False
            if E:
                r = E.src(st(d - 1), "I", 255, 0)
                if keys:
                    pl = D.SwitchPayload(packed, keys, [self.labels[t] for t in targets])
                    E.I(0x2b if packed else 0x2c, r, pl)
                E.I(0x2a, self.labels[default])
            pop(1)
            return [(t, (list(loc), list(stk))) for t in set(targets + [default])]

        # ---- returns / throw / monitors
        if n in ("ireturn", "lreturn", "freturn", "dreturn", "areturn", "return"):
            if E and self.sync:
                E.I(0x1e, self.src_lock(E))
            if E:
                if n == "return":
                    E.I(0x0e)
                else:
                    k = {"i": "I", "f": "I", "l": "W", "d": "W", "a": "A"}[n[0]]
                    w1 = 2 if k == "W" else 1
                    r = E.src(st(d - w1), k, 255, 0)
                    E.I({"I": 0x0f, "W": 0x10, "A": 0x11}[k], r)
            return []
        if n == "athrow":
            if E:
                E.I(0x27, E.src(st(d - 1), "A", 255, 0))
            return []
        if n in ("monitorenter", "monitorexit"):
            if E:
                reg = st(d - 1)
                # Lock through the local javac keeps the monitor in, so ART's lock
                # verifier sees enter/exit on the same (aliased) register.
                pv = self.prev
                if n == "monitorenter" and len(pv) == 2 and pv[0].name == "dup" and pv[1].name == "astore":
                    reg = self.loc(pv[1].a[0])
                elif n == "monitorexit" and pv and pv[-1].name == "aload":
                    reg = self.loc(pv[-1].a[0])
                E.I(0x1d if n == "monitorenter" else 0x1e, E.src(reg, "A", 255, 0))
            pop(1)
            return fall()

        # ---- fields
        if n in ("getstatic", "putstatic", "getfield", "putfield"):
            ref = cf.member(a[0])
            ft = ref.desc
            key = (ref.owner, ref.name, ft)
            var = field_variant(ft)
            k = kind(norm(ft))
            fw = words(ft)
            if n == "getstatic":
                if E:
                    E.dst(st(d), k, 255, 0, lambda r: E.I(0x60 + var, r, key))
                push_t(stk, ft)
            elif n == "putstatic":
                if E:
                    E.I(0x67 + var, E.src(st(d - fw), k, 255, 0), key)
                pop(fw)
            elif n == "getfield":
                if E:
                    ro = E.src(st(d - 1), "A", 15, 2)
                    E.dst(st(d - 1), k, 15, 0, lambda r: E.I(0x52 + var, r, ro, key))
                pop(1)
                push_t(stk, ft)
            else:
                if E:
                    rv = E.src(st(d - fw), k, 15, 0)
                    ro = E.src(st(d - fw - 1), "A", 15, 2)
                    E.I(0x59 + var, rv, ro, key)
                pop(fw + 1)
            return fall()

        # ---- invokes
        if n in ("invokevirtual", "invokespecial", "invokestatic", "invokeinterface"):
            ref = cf.member(a[0])
            params, ret = parse_method_desc(ref.desc)
            aw = sum(words(p) for p in params) + (0 if n == "invokestatic" else 1)
            key = (ref.owner, ref.name, tuple(params), ret)
            if n == "invokestatic":
                op = 0x77
            elif n == "invokeinterface":
                op = 0x78
            elif n == "invokevirtual":
                op = 0x74
                if ref.owner == self.cls and self.ctx.is_private_method(cf, ref.name, ref.desc):
                    op = 0x76
            else:
                if ref.name == "<init>" or ref.owner == self.cls:
                    op = 0x76
                else:
                    op = 0x75
            recv_t = stk[d - aw] if n != "invokestatic" else None
            if E:
                E.invoke(op, st(d - aw), aw, key)
            pop(aw)
            if ref.name == "<init>" and recv_t and recv_t.startswith("U"):
                newt = self.cls if recv_t == "Uthis" else recv_t.split(":", 1)[1]
                for arr in (loc, stk):
                    for i in range(len(arr)):
                        if arr[i] == recv_t:
                            arr[i] = newt
            if ret != "V":
                if E:
                    E.move_result(st(d - aw), ret)
                push_t(stk, ret)
            return fall()
        if n == "invokedynamic":
            indy = cf.indy(a[0])
            cparams, iface = parse_method_desc(indy.desc)
            aw = sum(words(p) for p in cparams)
            create_key = self.ctx.lambda_class(cf, indy)
            if E:
                E.invoke(0x77, st(d - aw), aw, create_key)
                E.move_result(st(d - aw), iface)
            pop(aw)
            stk.append(iface)
            return fall()

        # ---- objects
        if n == "new":
            desc = cf.class_desc(a[0])
            if E:
                E.dst(st(d), "A", 255, 0, lambda r: E.I(0x22, r, desc))
            stk.append("U%d:%s" % (ins.pc, desc))
            return fall()
        if n == "checkcast":
            desc = cf.class_desc(a[0])
            if E:
                r = st(d - 1)
                if r < 256:
                    E.I(0x1f, r, desc)
                else:
                    E.mv(0, r, "A")
                    E.I(0x1f, 0, desc)
                    E.mv(r, 0, "A")
            stk[-1] = desc
            return fall()
        if n == "instanceof":
            desc = cf.class_desc(a[0])
            if E:
                rs = E.src(st(d - 1), "A", 15, 1)
                E.dst(st(d - 1), "I", 15, 0, lambda r: E.I(0x20, r, rs, desc))
            stk[-1] = "I"
            return fall()

        raise TranslateError("unsupported JVM instruction %s" % n)


# ----------------------------------------------------------------- class translation
LMF = "Ljava/lang/invoke/LambdaMetafactory;"


class Context:
    """Holds all classes being translated; generates lambda classes."""

    def __init__(self):
        self.classfiles = {}
        self.out_classes = []
        self._lambda_cache = {}
        self._lambda_count = {}
        self._host_extra = {}   # host desc -> list of extra DexMethod (bridges)

    def is_private_method(self, cf, name, desc):
        for m in cf.methods:
            if m.name == name and m.desc == desc:
                return bool(m.access & ACC_PRIVATE)
        return False

    # -- lambdas
    def lambda_class(self, cf, indy):
        host = internal_to_desc(cf.name)
        ck = (host, indy.bsm_index, indy.name, indy.desc)
        if ck in self._lambda_cache:
            return self._lambda_cache[ck]
        mh_idx, args = cf.bootstrap[indy.bsm_index]
        bsm = cf.const(mh_idx)
        if not isinstance(bsm, MethodHandle) or bsm.ref.owner != LMF:
            what = bsm.ref.owner + "." + bsm.ref.name if isinstance(bsm, MethodHandle) else "?"
            if "StringConcatFactory" in what:
                raise TranslateError("string concatenation via invokedynamic: compile with --release 8")
            raise TranslateError("unsupported invokedynamic bootstrap %s" % what)
        cargs = [cf.const(i) for i in args]
        sam = cargs[0].desc
        impl = cargs[1]
        inst = cargs[2].desc
        markers, bridges = [], []
        if bsm.ref.name == "altMetafactory":
            flags = cargs[3][1]
            i = 4
            if flags & 2:
                cnt = cargs[i][1]
                markers = [c.desc for c in cargs[i + 1:i + 1 + cnt]]
                i += 1 + cnt
            if flags & 4:
                cnt = cargs[i][1]
                bridges = [c.desc for c in cargs[i + 1:i + 1 + cnt]]
                i += 1 + cnt
        n = self._lambda_count.get(host, 0)
        self._lambda_count[host] = n + 1
        lc = host[:-1] + "$$Lambda$%d;" % n
        cparams, iface = parse_method_desc(indy.desc)

        # resolve implementation call
        K, R = impl.kind, impl.ref
        ip, ir = parse_method_desc(R.desc)
        if K == 8:
            target = ("new", (R.owner, "<init>", tuple(ip), "V"), list(ip), R.owner)
        else:
            if K == 6:
                ta = list(ip)
                op = 0x77
            elif K in (5, 9, 7):
                ta = [R.owner] + list(ip)
                op = 0x78 if K == 9 else (0x76 if K == 7 else 0x74)
            else:
                raise TranslateError("unsupported lambda method handle kind %d" % K)
            key = (R.owner, R.name, tuple(ip), ir)
            if R.owner == host and self.is_private_method(cf, R.name, R.desc):
                # bridge in host so the lambda class may call it
                bparams = ([] if K == 6 else [host]) + list(ip)
                bname = "lambda$bridge$%d" % n
                bkey = (host, bname, tuple(bparams), ir)
                self._host_extra.setdefault(host, []).append(
                    self._make_bridge(host, bname, bparams, ir, 0x77 if K == 6 else 0x76, key))
                key = bkey
                op = 0x77
                ta = bparams
            elif K == 7:
                raise TranslateError("lambda invokespecial on non-private method %s" % R)
            target = (op, key, ta, ir)

        dc = DexClass(lc, 0x1010, OBJ, [iface] + [m for m in markers if m != iface], None)
        for i, t in enumerate(cparams):
            dc.fields.append(DexField(lc, "f%d" % i, t, 0x12))
        dc.methods.append(self._make_lambda_init(lc, cparams))
        create = DexMethod(lc, "create", cparams, iface, 0x1009, None)
        cw = sum(words(p) for p in cparams)
        E = Emitter()
        E.I(0x22, 0, lc)
        E.invoke(0x76, 0, 1 + cw, (lc, "<init>", tuple(cparams), "V"))
        E.I(0x11, 0)
        create.code = DexCode(1 + cw, cw, E.outs, E.items)
        dc.methods.append(create)
        sp_inst, _ = parse_method_desc(inst)
        seen = set()
        for desc in [sam] + bridges:
            if desc in seen:
                continue
            seen.add(desc)
            dc.methods.append(self._make_sam(lc, indy.name, desc, cparams, sp_inst, target))
        self.out_classes.append(dc)
        k = (lc, "create", tuple(cparams), iface)
        self._lambda_cache[ck] = k
        return k

    def _make_bridge(self, host, name, params, ret, op, key):
        ins = sum(words(p) for p in params)
        E = Emitter()
        E.invoke(op, 2, ins, key)
        if ret == "V":
            E.I(0x0e)
        else:
            k = kind(norm(ret))
            E.move_result(0, ret)
            E.I({"I": 0x0f, "W": 0x10, "A": 0x11}[k], 0)
        m = DexMethod(host, name, params, ret, 0x1008, None)
        m.code = DexCode(2 + ins, ins, E.outs, E.items)
        return m

    def _make_lambda_init(self, lc, cparams):
        cw = sum(words(p) for p in cparams)
        E = Emitter()
        this = 3
        E.invoke(0x76, this, 1, (OBJ, "<init>", (), "V"))
        r = this + 1
        for i, t in enumerate(cparams):
            k = kind(norm(t))
            rv = E.src(r, k, 15, 0)
            E.I(0x59 + field_variant(t), rv, this, (lc, "f%d" % i, t))
            r += words(t)
        E.I(0x0e)
        m = DexMethod(lc, "<init>", cparams, "V", 0x0002 | ACC_CONSTRUCTOR, None)
        m.code = DexCode(3 + 1 + cw, 1 + cw, E.outs, E.items)
        return m

    def _make_sam(self, lc, name, desc, cparams, sp_inst, target):
        sp, sr = parse_method_desc(desc)
        op, key, ta, ir = target
        if len(cparams) + len(sp) != len(ta):
            raise TranslateError("lambda arity mismatch for %s%s" % (name, desc))
        is_new = op == "new"
        ow = sum(words(t) for t in ta) + (1 if is_new else 0)
        ins = 1 + sum(words(t) for t in sp)
        oa = 3
        this = oa + ow
        E = Emitter()
        # source list
        srcs = [("f", i, t, t) for i, t in enumerate(cparams)]
        r = this + 1
        for j, t in enumerate(sp):
            it = sp_inst[j] if j < len(sp_inst) else t
            srcs.append(("p", r, t, it))
            r += words(t)
        tr = oa + (1 if is_new else 0)
        for (tt, (sk, sref, stype, itype)) in zip(ta, srcs):
            ns, nt = norm(stype), norm(tt)
            boxing = not is_ref(ns) and is_ref(nt)
            lr = 0 if boxing else tr
            k = kind(ns)
            if sk == "f":
                ro = E.src(this, "A", 15, 2)
                E.dst(lr, k, 15, 0, lambda rr, ro=ro, sref=sref, stype=stype:
                      E.I(0x52 + field_variant(stype), rr, ro, (lc, "f%d" % sref, stype)))
                cur = stype
            else:
                E.mv(lr, sref, k)
                cur = stype
                if is_ref(ns) and is_ref(norm(itype)) and itype != stype and itype != OBJ:
                    E.I(0x1f, lr, itype)
                    cur = itype
            if boxing:
                self._box(E, 0, cur, 0)
                E.mv(tr, 0, "A")
            else:
                self._adapt(E, tr, cur, tt)
            tr += words(tt)
        if is_new:
            E.I(0x22, oa, key[0])
            E.invoke(0x76, oa, ow, key)
            rt = key[0]
            E.mv(0, oa, "A")
        else:
            E.invoke(op, oa, ow, key)
            rt = ir
            if ir != "V" and sr != "V":
                E.move_result(0, ir)
        if sr == "V":
            E.I(0x0e)
        else:
            if rt == "V":
                raise TranslateError("lambda returns void but interface expects a value")
            nr, ns = norm(rt), norm(sr)
            if is_ref(nr) and not is_ref(ns):
                self._unbox(E, 0, rt, sr)
            elif not is_ref(nr) and is_ref(ns):
                self._box(E, 0, rt, 0)
            elif not is_ref(nr) and kind(nr) != kind(ns):
                raise TranslateError("unsupported primitive return adaptation %s -> %s" % (rt, sr))
            k = kind(ns)
            E.I({"I": 0x0f, "W": 0x10, "A": 0x11}[k], 0)
        m = DexMethod(lc, name, sp, sr, 0x0001 | 0x1000, None)
        m.code = DexCode(this + ins, ins, max(E.outs, 2), E.items)
        return m

    def _box(self, E, dst, prim, _scratch):
        # value is in register dst (prim); result object into dst
        E.invoke(0x77, dst, words(prim), (BOX[prim], "valueOf", (prim,), BOX[prim]))
        E.I(0x0c, dst)

    def _unbox(self, E, reg, from_t, prim):
        box = BOX[prim]
        if from_t != box:
            E.I(0x1f, reg, box)
        E.invoke(0x74, reg, 1, (box, UNBOX_NAME[prim], (), prim))
        E.move_result(reg, prim)

    def _adapt(self, E, reg, cur, target):
        nc, nt = norm(cur), norm(target)
        if cur == target:
            return
        if is_ref(nc) and is_ref(nt):
            if target != OBJ:
                E.I(0x1f, reg, target)
            return
        if is_ref(nc) and not is_ref(nt):
            # unbox; if target is wide the register pair reg..reg+1 is reserved
            self._unbox(E, reg, cur, target)
            return
        if not is_ref(nc) and is_ref(nt):
            # primitive in reg -> box.  Use scratch v0 for the call.
            E.mv(0, reg, kind(nc))
            self._box(E, 0, cur, 0)
            E.mv(reg, 0, "A")
            return
        if kind(nc) == kind(nt) and nc == nt:
            return
        raise TranslateError("unsupported lambda primitive adaptation %s -> %s" % (cur, target))

    # -- classes
    def translate(self, cf):
        desc = internal_to_desc(cf.name)
        acc = cf.access & (0x0001 | 0x0010 | 0x0200 | 0x0400 | 0x1000 | 0x2000 | 0x4000)
        dc = DexClass(desc, acc, internal_to_desc(cf.super_name) if cf.super_name else None,
                      [internal_to_desc(i) for i in cf.interfaces], cf.source_file)
        for f in cf.fields:
            fa = f.access & 0x50DF
            sv = None
            if (f.access & ACC_STATIC) and f.const_value is not None:
                cv = f.const_value
                if isinstance(cv, StringConst):
                    sv = cv.value
                else:
                    sv = cv[1]
            dc.fields.append(DexField(desc, f.name, f.desc, fa, sv))
        for m in cf.methods:
            params, ret = parse_method_desc(m.desc)
            ma = m.access & 0x1DFF
            if m.name in ("<init>", "<clinit>"):
                ma |= ACC_CONSTRUCTOR
            if (m.access & ACC_SYNCHRONIZED) and not (m.access & ACC_NATIVE):
                ma = (ma & ~ACC_SYNCHRONIZED) | ACC_DECLARED_SYNCHRONIZED
            dm = DexMethod(desc, m.name, params, ret, ma, None)
            if m.code is not None and not (m.access & (ACC_ABSTRACT | ACC_NATIVE)):
                try:
                    dm.code = MethodTranslator(self, cf, m).run()
                except TranslateError as e:
                    raise TranslateError("%s.%s%s: %s" % (cf.name, m.name, m.desc, e))
            dc.methods.append(dm)
        dc.methods.extend(self._host_extra.pop(desc, []))
        self.out_classes.append(dc)
        return dc


def translate_classes(classfiles):
    ctx = Context()
    for cf in classfiles:
        ctx.classfiles[cf.name] = cf
    for cf in classfiles:
        ctx.translate(cf)
    return ctx.out_classes
