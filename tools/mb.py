import struct, json, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
# The thin armv7 slice sits in analysis/bin/; the fat binary in game/ works too, the
# parser takes either.  SIXTHSENSE_BINARY overrides both.
_CANDIDATES = [
    os.environ.get('SIXTHSENSE_BINARY'),
    os.path.join(_ROOT, 'analysis', 'bin', 'sixsense_armv7'),
    os.path.join(_ROOT, 'game', 'sixsense'),
    os.path.join(_HERE, 'sixsense'),
]
PATH = next((p for p in _CANDIDATES if p and os.path.exists(p)), None)
if PATH is None:
    raise SystemExit('No SixthSense binary found. Tried: '
                     + ', '.join(p for p in _CANDIDATES if p))
_data = open(PATH,'rb').read()
if struct.unpack('>I', _data[:4])[0] == 0xcafebabe:          # fat: take the armv7 slice
    _ct,_cst,OFF,SIZE,_al = struct.unpack('>5I', _data[8:28])
    m = _data[OFF:OFF+SIZE]
else:                                                        # already thin
    OFF, SIZE = 0, len(_data)
    m = _data
ncmds = struct.unpack('<I', m[16:20])[0]

sections=[]; cmds=[]
off=28
for i in range(ncmds):
    cmd, cmdsize = struct.unpack('<II', m[off:off+8])
    cmds.append((cmd,off,cmdsize))
    if cmd==0x1:
        nsects = struct.unpack('<I', m[off+48:off+52])[0]
        so=off+56
        for s in range(nsects):
            sn = m[so:so+16].rstrip(b'\0').decode()
            sg = m[so+16:so+32].rstrip(b'\0').decode()
            addr,size,offs,align,reloff,nreloc,flags = struct.unpack('<7I', m[so+32:so+60])
            res1,res2 = struct.unpack('<II', m[so+60:so+68])
            sections.append(dict(seg=sg,name=sn,addr=addr,size=size,off=offs,flags=flags,r1=res1,r2=res2))
            so+=68
    off+=cmdsize

def sect(n):
    for s in sections:
        if s['name']==n: return s
    return None

def v2o(a):
    for s in sections:
        if s['addr']<=a<s['addr']+s['size']:
            if s['name'] in ('__bss','__common'): return None
            return s['off'] + (a-s['addr'])
    return None

def rd(a,n):
    o=v2o(a)
    if o is None: return None
    return m[o:o+n]

def u32(a):
    b=rd(a,4)
    return struct.unpack('<I',b)[0] if b else None

def cstr(a):
    if not a: return None
    o=v2o(a)
    if o is None: return None
    e=m.find(b'\0',o)
    return m[o:e].decode('utf-8',errors='replace')

# ---- symtab ----
symtab={}
for cmd,o,sz in cmds:
    if cmd==0x2:
        symoff,nsyms,stroff,strsize = struct.unpack('<4I', m[o+8:o+24])
        for i in range(nsyms):
            p=symoff+12*i
            strx,typ,sect_,desc,value = struct.unpack('<IBBHI', m[p:p+12])
            e=m.find(b'\0', stroff+strx)
            name=m[stroff+strx:e].decode(errors='replace')
            symtab[i]=(name,typ,sect_,value)
    if cmd==0xb:
        d=struct.unpack('<18I', m[o+8:o+80])
        indirectsymoff, nindirectsyms = d[12], d[13]

# indirect symbols -> stub addresses
INDIRECT=[]
for i in range(nindirectsyms):
    INDIRECT.append(struct.unpack('<I', m[indirectsymoff+4*i:indirectsymoff+4*i+4])[0])

stubs={}   # addr -> symbol name
for s in sections:
    t = s['flags'] & 0xff
    if t in (0x8,0x9):   # S_SYMBOL_STUBS
        stride = s['r2'] or 12
        n = s['size']//stride
        for i in range(n):
            idx = INDIRECT[s['r1']+i]
            nm = symtab.get(idx,('?',))[0]
            stubs[s['addr']+i*stride] = nm
    if t in (0x6,0x7):   # LAZY / NON_LAZY pointers
        n=s['size']//4
        for i in range(n):
            idx = INDIRECT[s['r1']+i]
            nm = symtab.get(idx,('?',))[0]
            stubs.setdefault(s['addr']+i*4, nm)

# ---- objc metadata ----
_CLASSES_JSON = os.path.join(_ROOT, 'analysis', 'data', 'objc_classes.json')
classes = json.load(open(_CLASSES_JSON)) if os.path.exists(_CLASSES_JSON) else []
IMP2NAME={}
IVAR={}       # offset-var-address -> name ; also (class,offset)->name
CLS_BY_IVAROFF={}
for c in classes:
    for mm in c['methods']+c['class_methods']:
        IMP2NAME[mm['imp'] & ~1] = "[%s %s%s]"%(c['name'], mm['kind'], mm['name'])
    for iv in c['ivars']:
        CLS_BY_IVAROFF.setdefault(c['name'],{})[iv['offset']] = (iv['name'], iv['type'])

# selref addr -> selector string
SELREF={}
s=sect('__objc_selrefs')
if s:
    for i in range(s['size']//4):
        a=s['addr']+4*i
        SELREF[a]=cstr(u32(a))
# classref
CLSREF={}
s=sect('__objc_classrefs')
byaddr={c['addr']:c['name'] for c in classes}
if s:
    for i in range(s['size']//4):
        a=s['addr']+4*i
        v=u32(a)
        CLSREF[a]=byaddr.get(v)
SUPERREF={}
s=sect('__objc_superrefs')
if s:
    for i in range(s['size']//4):
        a=s['addr']+4*i
        SUPERREF[a]=byaddr.get(u32(a))

# cfstrings
CFSTR={}
s=sect('__cfstring')
if s:
    for i in range(s['size']//16):
        a=s['addr']+16*i
        isa,flags,dp,ln = struct.unpack('<4I', rd(a,16))
        CFSTR[a]=cstr(dp)

# ivar offset variables: __objc_ivar section holds uint32 offsets; ivar struct's first field points here
IVAROFFVAR={}
for c in classes:
    for iv in c['ivars']:
        pass
# rebuild: need pointer addresses; re-parse ivar lists
def ivar_offset_vars():
    res={}
    for c in classes:
        # find ro
        isa,sup,cache,vt,ro = struct.unpack('<5I', rd(c['addr'],20)); ro&=~3
        flags,istart,isize,ivl,namep,bm,bp,ivars,wil,props = struct.unpack('<10I', rd(ro,40))
        if not ivars: continue
        es,cnt = struct.unpack('<II', rd(ivars,8))
        p=ivars+8
        for i in range(cnt):
            offp,namep2,typep,al,sz = struct.unpack('<5I', rd(p,20))
            res[offp]=(c['name'], cstr(namep2), cstr(typep))
            p+=es
    return res
IVAROFFVAR = ivar_offset_vars() if classes else {}

# ---- dyld bind info: address -> bound symbol ----
BIND={}
def _uleb(b,i):
    r=0; s=0
    while True:
        c=b[i]; i+=1
        r |= (c&0x7f)<<s
        if not (c&0x80): break
        s+=7
    return r,i
def _sleb(b,i):
    r=0; s=0
    while True:
        c=b[i]; i+=1
        r |= (c&0x7f)<<s; s+=7
        if not (c&0x80):
            if c&0x40: r -= (1<<s)
            break
    return r,i

_segs=[]
_off=28
for _i in range(ncmds):
    _c,_cs = struct.unpack('<II', m[_off:_off+8])
    if _c==0x1:
        _sn=m[_off+8:_off+24].rstrip(b'\0').decode()
        _vm=struct.unpack('<I', m[_off+24:_off+28])[0]
        _segs.append((_sn,_vm))
    _off+=_cs

def _parse_bind(blob):
    i=0; sym=''; seg=0; addr=0; typ=1; libord=0; add=0
    n=len(blob)
    while i<n:
        op=blob[i]; imm=op&0x0F; opc=op&0xF0; i+=1
        if opc==0x00: break
        elif opc==0x10: libord=imm
        elif opc==0x20: libord,i=_uleb(blob,i)
        elif opc==0x30: libord=imm
        elif opc==0x40:
            e=blob.index(b'\0',i); sym=blob[i:e].decode(); i=e+1
        elif opc==0x50: typ=imm
        elif opc==0x60: add,i=_sleb(blob,i)
        elif opc==0x70:
            seg=imm; off,i=_uleb(blob,i); addr=_segs[seg][1]+off
        elif opc==0x80:
            off,i=_uleb(blob,i); addr=(addr+off)&0xFFFFFFFF
        elif opc==0x90:
            addr&=0xFFFFFFFF; BIND[addr]=sym; addr+=4
        elif opc==0xA0:
            addr&=0xFFFFFFFF; BIND[addr]=sym; off,i=_uleb(blob,i); addr+=4+off
        elif opc==0xB0:
            addr&=0xFFFFFFFF; BIND[addr]=sym; addr+=4+imm*4
        elif opc==0xC0:
            cnt,i=_uleb(blob,i); skip,i=_uleb(blob,i)
            for _ in range(cnt):
                addr&=0xFFFFFFFF; BIND[addr]=sym; addr+=4+skip
        else: break

for _c,_o,_sz in cmds:
    if _c in (0x22,0x80000022):
        rb,rs,bo,bs,wo,ws,lo,ls,eo,es = struct.unpack('<10I', m[_o+8:_o+48])
        for (o_,s_) in ((bo,bs),(wo,ws),(lo,ls)):
            if s_: _parse_bind(m[o_:o_+s_])
