# -*- coding: utf-8 -*-
"""Symbolic annotator for the SixthSense armv7 Thumb binary."""
import os, sys, json, re, struct, bisect
sys.path.insert(0, '.')
import mb as B
from capstone import *
from capstone.arm import *

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True

classes = json.load(open(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'analysis', 'data', 'objc_classes.json')))
byname = {c['name']: c for c in classes}
ALLIMPS = sorted(B.IMP2NAME.keys())

BRANCHES = ('b', 'beq', 'bne', 'blt', 'bgt', 'ble', 'bge', 'bhi', 'bls',
            'blo', 'bhs', 'bmi', 'bpl', 'bvs', 'bvc')


def _disasm_resync(code, addr):
    """Disassemble past the tbb/tbh jump tables the compiler drops inline.

    Capstone stops at the first byte it cannot decode - the branch table itself - and
    everything after would be lost.  Skip two bytes and start again.
    """
    pos, n = 0, len(code)
    while pos < n:
        progressed = False
        for ins in md.disasm(code[pos:], addr + pos):
            progressed = True
            yield ins
            pos = ins.address - addr + ins.size
        if not progressed:
            pos += 2


def f32(v):
    try:
        return struct.unpack('<f', struct.pack('<I', v & 0xFFFFFFFF))[0]
    except Exception:
        return None


class Sym(object):
    __slots__ = ('kind', 'val', 'txt')

    def __init__(self, kind, val=None, txt=None):
        self.kind = kind
        self.val = val
        self.txt = txt


def describe_const(v):
    if v in B.CFSTR:
        return 'CFSTR(' + repr(B.CFSTR[v]) + ')'
    if v in B.BIND:
        return B.BIND[v].replace('_OBJC_CLASS_$_', '')
    if v in B.CLSREF and B.CLSREF[v]:
        return B.CLSREF[v]
    if v in B.SELREF:
        return 'SEL(' + B.SELREF[v] + ')'
    if v in B.IVAROFFVAR:
        return 'IVOFF(' + B.IVAROFFVAR[v][1] + ')'
    s = B.cstr(v)
    if s is not None:
        for sc in B.sections:
            if sc['addr'] <= v < sc['addr'] + sc['size'] and sc['name'] in (
                    '__cstring', '__objc_methname', '__objc_classname'):
                return repr(s)
    if v in B.stubs:
        return B.stubs[v]
    return None


def run(start, end, clsname=None, show_all=False):
    a = start & ~1
    o = B.v2o(a)
    code = B.m[o:o + (end - a)]
    R = {}
    out = []
    targets = set()
    insns = list(_disasm_resync(code, a))
    for ins in insns:
        bb = ins.mnemonic.replace('.w', '')
        if bb in BRANCHES or bb in ('cbz', 'cbnz'):
            for op in ins.operands:
                if op.type == ARM_OP_IMM:
                    targets.add(op.imm)
    if not insns:
        return out
    rn = insns[0].reg_name

    def sv(reg, default=None):
        s = R.get(reg)
        if s is None:
            return default if default else rn(reg)
        if s.txt:
            return s.txt
        if s.kind == 'c':
            return str(s.val)
        return default if default else rn(reg)

    for ins in insns:
        A = ins.address
        mn = ins.mnemonic
        ops = ins.operands
        base = mn.replace('.w', '')
        if A in targets:
            out.append('L_%x:' % A)
        try:
            if base == 'movw' and ops[1].type == ARM_OP_IMM:
                R[ops[0].reg] = Sym('c', ops[1].imm & 0xFFFF)
                continue
            if base == 'movt':
                r = ops[0].reg
                cur = R.get(r)
                v = (cur.val & 0xFFFF) if (cur and cur.kind == 'c') else 0
                R[r] = Sym('c', v | ((ops[1].imm & 0xFFFF) << 16))
                continue
            if base in ('mov', 'movs') and len(ops) == 2 and ops[1].type == ARM_OP_IMM:
                R[ops[0].reg] = Sym('c', ops[1].imm)
                out.append('  %04x  %s = %d' % (A, rn(ops[0].reg), ops[1].imm))
                continue
            if base == 'mvn' and len(ops) == 2 and ops[1].type == ARM_OP_IMM:
                R[ops[0].reg] = Sym('c', (~ops[1].imm) & 0xFFFFFFFF)
                out.append('  %04x  %s = %d' % (A, rn(ops[0].reg), -(ops[1].imm + 1)))
                continue
            if base in ('mov', 'movs') and len(ops) == 2 and ops[1].type == ARM_OP_REG:
                s = R.get(ops[1].reg)
                if s:
                    R[ops[0].reg] = s
                else:
                    R.pop(ops[0].reg, None)
                continue
            if base == 'add' and len(ops) == 2 and ops[1].type == ARM_OP_REG and ops[1].reg == ARM_REG_PC:
                r = ops[0].reg
                s = R.get(r)
                if s and s.kind == 'c':
                    v = (s.val + A + 4) & 0xFFFFFFFF
                    d = describe_const(v)
                    R[r] = Sym('c', v, d)
                    if d:
                        out.append('  %04x  %s = %s' % (A, rn(r), d))
                continue
            if base == 'add' and len(ops) == 3 and ops[1].type == ARM_OP_REG and \
                    ops[1].reg == ARM_REG_PC and ops[2].type == ARM_OP_REG:
                s = R.get(ops[2].reg)
                if s and s.kind == 'c':
                    v = (s.val + A + 4) & 0xFFFFFFFF
                    d = describe_const(v)
                    R[ops[0].reg] = Sym('c', v, d)
                    if d:
                        out.append('  %04x  %s = %s' % (A, rn(ops[0].reg), d))
                continue
            if base == 'ldr' and len(ops) == 2 and ops[1].type == ARM_OP_MEM:
                dst = ops[0].reg
                mem = ops[1].mem
                if mem.base == ARM_REG_PC:
                    va = ((A + 4) & ~3) + mem.disp
                    val = B.u32(va)
                    if val is not None:
                        if va in B.IVAROFFVAR:
                            nm = B.IVAROFFVAR[va][1]
                            R[dst] = Sym('ivoff', val, nm)
                            out.append('  %04x  %s = IVOFF(%s)' % (A, rn(dst), nm))
                        else:
                            d = describe_const(val)
                            R[dst] = Sym('c', val, d)
                            if d:
                                out.append('  %04x  %s = %s' % (A, rn(dst), d))
                    continue
                bs = R.get(mem.base)
                if bs and bs.kind == 'c' and mem.index == 0:
                    va = bs.val + mem.disp
                    if va in B.IVAROFFVAR:
                        nm = B.IVAROFFVAR[va][1]
                        R[dst] = Sym('ivoff', val=B.u32(va), txt=nm)
                        R[dst].kind = 'ivoff'
                        out.append('  %04x  %s = IVOFF(%s)' % (A, rn(dst), nm))
                        continue
                    val = B.u32(va)
                    if val is not None:
                        d = describe_const(va) or describe_const(val)
                        R[dst] = Sym('c', val, d)
                        if d:
                            out.append('  %04x  %s = %s' % (A, rn(dst), d))
                        continue
                if mem.index:
                    isym = R.get(mem.index)
                    if isym and isym.kind == 'ivoff':
                        R[dst] = Sym('v', None, 'self->' + isym.txt)
                        out.append('  %04x  %s = self->%s' % (A, rn(dst), isym.txt))
                        continue
                R.pop(dst, None)
                continue
            if base in ('ldrb', 'ldrsb', 'ldrh', 'ldrsh') and len(ops) == 2 and \
                    ops[1].type == ARM_OP_MEM and ops[1].mem.index:
                isym = R.get(ops[1].mem.index)
                if isym and isym.kind == 'ivoff':
                    R[ops[0].reg] = Sym('v', None, 'self->' + isym.txt)
                    out.append('  %04x  %s = self->%s' % (A, rn(ops[0].reg), isym.txt))
                    continue
                R.pop(ops[0].reg, None)
                continue
            if base in ('str', 'strb', 'strh') and len(ops) == 2 and \
                    ops[1].type == ARM_OP_MEM and ops[1].mem.index:
                isym = R.get(ops[1].mem.index)
                if isym and isym.kind == 'ivoff':
                    out.append('  %04x  self->%s = %s' % (A, isym.txt, sv(ops[0].reg)))
                continue
            if base == 'vldr' and len(ops) == 2 and ops[1].type == ARM_OP_MEM and \
                    ops[1].mem.base == ARM_REG_PC:
                va = ((A + 4) & ~3) + ops[1].mem.disp
                r = rn(ops[0].reg)
                if r.startswith('d'):
                    b = B.rd(va, 8)
                    if b:
                        out.append('  %04x  %s = %g' % (A, r, struct.unpack('<d', b)[0]))
                else:
                    b = B.rd(va, 4)
                    if b:
                        out.append('  %04x  %s = %g' % (A, r, struct.unpack('<f', b)[0]))
                continue
            if base == 'vmov' and len(ops) == 2 and ops[1].type == ARM_OP_REG:
                s = R.get(ops[1].reg)
                if s and s.kind == 'c':
                    out.append('  %04x  %s = float(%g)' % (A, rn(ops[0].reg), f32(s.val) or 0.0))
                continue
            if base in ('bl', 'blx') and ops and ops[0].type == ARM_OP_IMM:
                t = ops[0].imm
                sy = B.stubs.get(t) or B.stubs.get(t | 1) or B.IMP2NAME.get(t & ~1)
                if sy and 'objc_msgSend' in sy:
                    s1 = R.get(ARM_REG_R1)
                    sel = None
                    if s1 and s1.kind == 'c':
                        sel = B.SELREF.get(s1.val) or B.cstr(s1.val)
                        if sel and len(sel) > 90:
                            sel = None
                    r0 = R.get(ARM_REG_R0)
                    recv = (r0.txt if (r0 and r0.txt) else 'r0')
                    args = []
                    for RG in (ARM_REG_R2, ARM_REG_R3):
                        s = R.get(RG)
                        if s is None:
                            args.append('?')
                        elif s.txt:
                            args.append(s.txt)
                        elif s.kind == 'c':
                            if abs(s.val) < 100000:
                                args.append(str(s.val))
                            else:
                                args.append('0x%x/f%g' % (s.val, f32(s.val) or 0.0))
                        else:
                            args.append('?')
                    tag = ' SUPER' if 'Super' in sy else ''
                    out.append('  %04x  r0 = [%s %s](%s)%s' % (A, recv, sel or '??', ', '.join(args), tag))
                elif sy:
                    out.append('  %04x  call %s' % (A, sy))
                else:
                    out.append('  %04x  call sub_%x' % (A, t))
                for RG in (ARM_REG_R0, ARM_REG_R1, ARM_REG_R2, ARM_REG_R3, ARM_REG_R12):
                    R.pop(RG, None)
                R[ARM_REG_R0] = Sym('ret')
                continue
            if base in ('cmp', 'cmn') and len(ops) == 2:
                lhs = sv(ops[0].reg)
                if ops[1].type == ARM_OP_IMM:
                    v = ops[1].imm if base == 'cmp' else -ops[1].imm
                    out.append('  %04x  cmp %s, %d' % (A, lhs, v))
                else:
                    out.append('  %04x  cmp %s, %s' % (A, lhs, sv(ops[1].reg)))
                continue
            if base in BRANCHES and ops and ops[0].type == ARM_OP_IMM:
                out.append('  %04x  %s L_%x' % (A, base, ops[0].imm))
                continue
            if base in ('cbz', 'cbnz'):
                out.append('  %04x  %s %s -> L_%x' % (A, base, sv(ops[0].reg), ops[1].imm))
                continue
            if base in ('adds', 'add', 'subs', 'sub', 'muls', 'mul', 'lsls', 'lsrs',
                        'asrs', 'and', 'orr', 'eor', 'rsb', 'sdiv', 'udiv', 'mla', 'rsbs'):
                if ops and ops[0].type == ARM_OP_REG:
                    out.append('  %04x  %s %s' % (A, mn, ins.op_str))
                    R.pop(ops[0].reg, None)
                continue
            if base in ('it', 'ite', 'itt', 'itte', 'ittt', 'nop'):
                continue
            if base.startswith('v'):
                out.append('  %04x  %s %s' % (A, mn, ins.op_str))
                continue
            if base in ('pop', 'push', 'bx'):
                if base == 'pop' and 'pc' in ins.op_str:
                    out.append('  %04x  return' % A)
                continue
            if ops and ops[0].type == ARM_OP_REG:
                R.pop(ops[0].reg, None)
            if show_all:
                out.append('  %04x  %s %s' % (A, mn, ins.op_str))
        except Exception as e:
            out.append('  %04x  ERR %s (%s %s)' % (A, e, mn, ins.op_str))
    return out


def bounds(imp):
    s = imp & ~1
    i = bisect.bisect_right(ALLIMPS, s)
    return s, (ALLIMPS[i] if i < len(ALLIMPS) else s + 0x3000)


if __name__ == '__main__':
    cn = sys.argv[1]
    sel = sys.argv[2] if len(sys.argv) > 2 else None
    c = byname[cn]
    for mm in sorted(c['class_methods'] + c['methods'], key=lambda x: x['imp']):
        if sel and mm['name'] != sel and sel not in mm['name']:
            continue
        s, e = bounds(mm['imp'])
        print('\n//// %s[%s %s]  0x%x..0x%x  %s' % (mm['kind'], cn, mm['name'], s, e, mm['types']))
        for l in run(s, e, cn):
            print(l)
