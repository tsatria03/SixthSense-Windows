# -*- coding: utf-8 -*-
import sys, struct, re
sys.path.insert(0,'.')
import mb as B
from capstone import *
from capstone.arm import *

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
md.detail = True

def _disasm_resync(code, addr):
    """Disassemble, stepping over the tbb/tbh jump tables the compiler drops inline.

    Capstone stops at the first byte it cannot decode - which is the branch table
    itself - and everything after it would be lost.  When that happens, skip two bytes
    and start again, so the code past the table still comes out.
    """
    pos = 0
    n = len(code)
    while pos < n:
        progressed = False
        for ins in md.disasm(code[pos:], addr + pos):
            progressed = True
            yield ins
            pos = ins.address - addr + ins.size
        if not progressed:
            pos += 2                     # a table byte pair; try the next halfword


def sym_for(addr):
    a = addr & ~1
    if a in B.IMP2NAME: return B.IMP2NAME[a]
    if addr in B.stubs: return B.stubs[addr]
    if a in B.stubs: return B.stubs[a]
    return None

def describe_ptr(v):
    """Return annotation for a data address."""
    outs=[]
    if v in B.SELREF: outs.append('selref@"%s"'%B.SELREF[v])
    if v in B.CLSREF and B.CLSREF[v]: outs.append('classref:%s'%B.CLSREF[v])
    if v in B.SUPERREF and B.SUPERREF[v]: outs.append('superref:%s'%B.SUPERREF[v])
    if v in B.CFSTR: outs.append('@"%s"'%B.CFSTR[v])
    if v in B.IVAROFFVAR:
        c,n,t = B.IVAROFFVAR[v]; outs.append('OFFSETOF(%s.%s)'%(c,n))
    if v in B.BIND: outs.append('BIND:%s'%B.BIND[v])
    if not outs:
        s = B.cstr(v)
        if s is not None and 1 <= len(s) <= 120 and all(32<=ord(ch)<127 or ord(ch)>127 for ch in s):
            # only if it lives in a string section
            for sc in B.sections:
                if sc['addr']<=v<sc['addr']+sc['size'] and sc['name'] in ('__cstring','__objc_methname','__objc_classname','__objc_methtype'):
                    outs.append('"%s"'%s); break
    sy = sym_for(v)
    if sy: outs.append(sy)
    return ' '.join(outs)

def func_end(start, limit=0x4000):
    """Find end by next known imp or by 0x4000 cap."""
    imps = sorted(B.IMP2NAME.keys())
    import bisect
    i = bisect.bisect_right(imps, start & ~1)
    if i < len(imps):
        return min(imps[i], (start&~1)+limit)
    return (start&~1)+limit

def disasm(start, end=None, show_raw=False):
    a = start & ~1
    if end is None: end = func_end(start)
    off = B.v2o(a)
    code = B.m[off: off + (end-a)]
    regs = {}   # reg -> const value
    lines=[]
    pending_pc_add = {}
    for ins in _disasm_resync(code, a):
        txt = "%-8s %s" % (ins.mnemonic, ins.op_str)
        ann = ''
        ops = ins.operands
        mn = ins.mnemonic
        # track constants
        try:
            if mn in ('mov','mov.w','movs') and len(ops)==2 and ops[0].type==ARM_OP_REG and ops[1].type==ARM_OP_REG:
                if ops[1].reg in regs: regs[ops[0].reg]=regs[ops[1].reg]
                else: regs.pop(ops[0].reg,None)
            elif mn in ('movw','mov.w','mov','movs') and len(ops)==2 and ops[0].type==ARM_OP_REG and ops[1].type==ARM_OP_IMM:
                regs[ops[0].reg] = ops[1].imm & 0xFFFF if mn=='movw' else ops[1].imm
            elif mn=='movt' and len(ops)==2 and ops[1].type==ARM_OP_IMM:
                r=ops[0].reg
                regs[r] = (regs.get(r,0) & 0xFFFF) | ((ops[1].imm & 0xFFFF)<<16)
            elif mn=='add' and len(ops)==2 and ops[0].type==ARM_OP_REG and ops[1].type==ARM_OP_REG and ops[1].reg==ARM_REG_PC:
                r=ops[0].reg
                if r in regs:
                    pc = ins.address + 4
                    regs[r] = (regs[r] + pc) & 0xFFFFFFFF
                    ann = '; =0x%x %s' % (regs[r], describe_ptr(regs[r]))
            elif mn=='add' and len(ops)==3 and ops[1].type==ARM_OP_REG and ops[1].reg==ARM_REG_PC and ops[2].type==ARM_OP_REG:
                r=ops[0].reg; src=ops[2].reg
                if src in regs:
                    pc = ins.address + 4
                    regs[r] = (regs[src] + pc) & 0xFFFFFFFF
                    ann = '; =0x%x %s' % (regs[r], describe_ptr(regs[r]))
            elif mn in ('ldr','ldr.w') and len(ops)==2 and ops[1].type==ARM_OP_MEM:
                base = ops[1].mem.base; disp = ops[1].mem.disp
                dst = ops[0].reg
                if base==ARM_REG_PC:
                    pcv = (ins.address + 4) & ~3
                    va = pcv + disp
                    val = B.u32(va)
                    if val is not None:
                        regs[dst]=val
                        ann = '; =0x%x %s' % (val, describe_ptr(val))
                elif base in regs and ops[1].mem.index==0:
                    va = regs[base]+disp
                    val = B.u32(va)
                    if val is not None:
                        regs[dst]=val
                        d = describe_ptr(va)
                        ann = '; [0x%x]=0x%x %s' % (va, val, d)
                    else:
                        regs.pop(dst,None)
                else:
                    regs.pop(dst,None)
            elif mn=='vldr' and len(ops)==2 and ops[1].type==ARM_OP_MEM and ops[1].mem.base==ARM_REG_PC:
                va=((ins.address+4)&~3)+ops[1].mem.disp
                rn=ins.reg_name(ops[0].reg)
                if rn.startswith('d'):
                    b=B.rd(va,8)
                    if b: ann='; %s = %r  (double @0x%x)'%(rn, struct.unpack('<d',b)[0], va)
                else:
                    b=B.rd(va,4)
                    if b: ann='; %s = %r  (float @0x%x)'%(rn, struct.unpack('<f',b)[0], va)
            elif mn in ('bl','blx','b','b.w','bl.w') and ops and ops[0].type==ARM_OP_IMM:
                t = ops[0].imm
                sy = sym_for(t) or sym_for(t|1)
                if sy: ann = '; -> %s' % sy
                if sy and 'objc_msgSend' in sy:
                    selr = regs.get(ARM_REG_R1)
                    sel = None
                    if selr is not None:
                        sel = B.SELREF.get(selr) or B.cstr(selr)
                    if sel is not None and len(sel)>80: sel=None
                    rcv = regs.get(ARM_REG_R0)
                    rd_ = ''
                    if rcv is not None:
                        rd_ = describe_ptr(rcv) or ('0x%x'%rcv)
                    ann = '; -> %s   SEL=%s  RECV=%s' % (sy, sel, rd_)
            else:
                # invalidate written reg
                if ops and ops[0].type==ARM_OP_REG and mn not in ('cmp','cmn','tst','teq','str','strb','strh','push','stm','stmdb','vstr','b','bl','blx','bx','it'):
                    regs.pop(ops[0].reg,None)
        except Exception as e:
            ann += ' ;;ERR %s'%e
        # str to ivar detection
        if mn.startswith('str') and len(ops)==2 and ops[1].type==ARM_OP_MEM:
            pass
        raw = ' '.join('%02x'%c for c in ins.bytes) if show_raw else ''
        lines.append("0x%06x  %-12s %-40s %s" % (ins.address, raw, txt, ann))
    return lines

if __name__=='__main__':
    arg=sys.argv[1]
    if arg.startswith('0x'):
        s=int(arg,16); e=int(sys.argv[2],16) if len(sys.argv)>2 else None
    else:
        # by name "[Class -sel]"
        s=None
        for a,n in B.IMP2NAME.items():
            if n==arg: s=a; break
        if s is None:
            for a,n in B.IMP2NAME.items():
                if arg in n: s=a; print("// matched",n); break
        e=None
    print("// ==== %s  (0x%x) ====" % (B.IMP2NAME.get(s&~1,'?'), s))
    for l in disasm(s,e): print(l)
