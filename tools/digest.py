# -*- coding: utf-8 -*-
import os, sys, json, re, struct
sys.path.insert(0,'.')
import mb as B
from capstone import *
from capstone.arm import *
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail=True

classes = json.load(open(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'analysis', 'data', 'objc_classes.json')))
byname={c['name']:c for c in classes}
IVOFF={}
for c in classes:
    for iv in c['ivars']: IVOFF.setdefault(c['name'],{})[iv['offset']]=iv['name']

FLOATC = {}
def fconst(v):
    try: return struct.unpack('<f', struct.pack('<I', v))[0]
    except: return None

def digest(start, end, clsname=None):
    a=start&~1
    code=B.m[B.v2o(a): B.v2o(a)+(end-a)]
    regs={}
    out=[]
    labels=set()
    for ins in md.disasm(code,a):
        ops=ins.operands; mn=ins.mnemonic
        if mn.startswith('b') and ops and ops[0].type==ARM_OP_IMM and mn not in ('bl','blx','bl.w','bic','bfi','bfc'):
            labels.add(ops[0].imm)
    for ins in md.disasm(code,a):
        ops=ins.operands; mn=ins.mnemonic; A=ins.address
        if A in labels: out.append("  L_%x:"%A)
        try:
            if mn in ('mov','mov.w','movs') and len(ops)==2 and ops[0].type==ARM_OP_REG and ops[1].type==ARM_OP_REG:
                if ops[1].reg in regs: regs[ops[0].reg]=regs[ops[1].reg]
                else: regs.pop(ops[0].reg,None)
                continue
            if mn in ('movw',) and ops[1].type==ARM_OP_IMM:
                regs[ops[0].reg]=ops[1].imm&0xFFFF; continue
            if mn=='movt':
                r=ops[0].reg; regs[r]=(regs.get(r,0)&0xFFFF)|((ops[1].imm&0xFFFF)<<16); continue
            if mn in ('mov','mov.w','movs') and ops[1].type==ARM_OP_IMM:
                regs[ops[0].reg]=ops[1].imm; continue
            if mn=='add' and len(ops)==2 and ops[1].type==ARM_OP_REG and ops[1].reg==ARM_REG_PC:
                r=ops[0].reg
                if r in regs: regs[r]=(regs[r]+A+4)&0xFFFFFFFF
                continue
            if mn=='add' and len(ops)==3 and ops[1].reg==ARM_REG_PC and ops[2].type==ARM_OP_REG:
                if ops[2].reg in regs: regs[ops[0].reg]=(regs[ops[2].reg]+A+4)&0xFFFFFFFF
                continue
            if mn in ('ldr','ldr.w') and len(ops)==2 and ops[1].type==ARM_OP_MEM:
                base=ops[1].mem.base; disp=ops[1].mem.disp; dst=ops[0].reg
                if base==ARM_REG_PC:
                    va=((A+4)&~3)+disp; val=B.u32(va)
                    if val is not None:
                        regs[dst]=val
                        if va in B.IVAROFFVAR:
                            out.append("  ; %s = OFFSETOF(%s.%s)"%(ins.reg_name(dst),B.IVAROFFVAR[va][0],B.IVAROFFVAR[va][1]))
                    continue
                if base in regs:
                    va=regs[base]+disp; val=B.u32(va)
                    if va in B.IVAROFFVAR:
                        out.append("  ; %s = OFFSETOF(%s.%s)"%(ins.reg_name(dst),B.IVAROFFVAR[va][0],B.IVAROFFVAR[va][1]))
                    if val is not None: regs[dst]=val
                    else: regs.pop(dst,None)
                    continue
                regs.pop(dst,None); continue
            if mn=='vldr' and len(ops)==2 and ops[1].type==ARM_OP_MEM and ops[1].mem.base==ARM_REG_PC:
                va=((A+4)&~3)+ops[1].mem.disp; val=B.u32(va)
                if val is not None: out.append("  ; %s = %r"%(ins.reg_name(ops[0].reg), fconst(val)))
                continue
            if mn in ('bl','blx','bl.w') and ops and ops[0].type==ARM_OP_IMM:
                t=ops[0].imm
                sy=B.stubs.get(t) or B.stubs.get(t|1) or B.IMP2NAME.get(t&~1)
                if sy and 'objc_msgSend' in sy:
                    selr=regs.get(ARM_REG_R1)
                    sel=B.SELREF.get(selr) or (B.cstr(selr) if selr else None)
                    if sel and len(sel)>90: sel=None
                    rcv=regs.get(ARM_REG_R0)
                    rn=''
                    if rcv is not None:
                        rn = B.CLSREF.get(rcv) or B.BIND.get(rcv) or ''
                        if not rn and rcv in B.CFSTR: rn='@"%s"'%B.CFSTR[rcv]
                    args=[]
                    for i,R in enumerate([ARM_REG_R2,ARM_REG_R3]):
                        v=regs.get(R)
                        if v is None: args.append('?')
                        elif v in B.CFSTR: args.append('@"%s"'%B.CFSTR[v])
                        elif v in B.BIND: args.append(B.BIND[v])
                        elif v in B.CLSREF and B.CLSREF[v]: args.append(B.CLSREF[v])
                        elif B.SELREF.get(v): args.append('@selector(%s)'%B.SELREF[v])
                        elif v<0x100000 and B.cstr(v) and any(s['addr']<=v<s['addr']+s['size'] and s['name'] in('__cstring','__objc_methname') for s in B.sections): args.append('"%s"'%B.cstr(v))
                        else: args.append(hex(v) if v>9 else str(v))
                    out.append("  0x%x: [%s %s]  args=(%s)"%(A, rn or 'r0', sel or '?', ', '.join(args)))
                elif sy:
                    out.append("  0x%x: call %s"%(A,sy))
                else:
                    out.append("  0x%x: call sub_%x"%(A,t))
                continue
            if mn in ('str','str.w','strb','strh','ldrb','ldrsb','ldrh') and len(ops)==2 and ops[1].type==ARM_OP_MEM:
                base=ops[1].mem.base
                idx=ops[1].mem.index
                if idx and idx in regs and clsname and regs[idx] in IVOFF.get(clsname,{}):
                    out.append("  0x%x: %s %s -> self.%s"%(A,mn,ins.reg_name(ops[0].reg),IVOFF[clsname][regs[idx]]))
                continue
            if mn in ('cmp','cmp.w') and len(ops)==2 and ops[1].type==ARM_OP_IMM:
                out.append("  0x%x: cmp %s, #%d"%(A,ins.reg_name(ops[0].reg),ops[1].imm))
                continue
            if mn.startswith('b') and mn not in('bl','blx','bl.w','bic','bfi','bfc','bkpt') and ops and ops[0].type==ARM_OP_IMM:
                out.append("  0x%x: %s L_%x"%(A,mn,ops[0].imm))
                continue
            if ops and ops[0].type==ARM_OP_REG:
                regs.pop(ops[0].reg,None)
        except Exception as e:
            pass
    return out

def methods_of(cn):
    c=byname[cn]
    ms=sorted(c['class_methods']+c['methods'], key=lambda x:x['imp'])
    res=[]
    allimps=sorted(B.IMP2NAME.keys())
    import bisect
    for mm in ms:
        s=mm['imp']&~1
        i=bisect.bisect_right(allimps,s)
        e=allimps[i] if i<len(allimps) else s+0x3000
        res.append((mm,s,e))
    return res

if __name__=='__main__':
    cn=sys.argv[1]
    filt=sys.argv[2] if len(sys.argv)>2 else None
    for mm,s,e in methods_of(cn):
        if filt and filt not in mm['name']: continue
        if re.match(r'^(set[A-Z]|[a-zA-Z_]\w*$)',mm['name']) and (e-s)<0x40 and mm['name'] not in ('dealloc',):
            continue
        print("\n//// %s%s  0x%x..0x%x  %s"%(mm['kind'],mm['name'],s,e,mm['types']))
        for l in digest(s,e,cn): print(l)
