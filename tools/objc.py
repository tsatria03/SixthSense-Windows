import struct, json, sys

import os
_HERE = os.path.dirname(os.path.abspath(__file__))
PATH = next((p for p in (os.environ.get('SIXTHSENSE_BINARY'),
                         os.path.join(os.path.dirname(_HERE), 'analysis', 'bin', 'sixsense_armv7'),
                         os.path.join(os.path.dirname(_HERE), 'game', 'sixsense'),
                         os.path.join(_HERE, 'sixsense')) if p and os.path.exists(p)), None)
data = open(PATH,'rb').read()
if struct.unpack('>I', data[:4])[0] == 0xcafebabe:        # fat: take the armv7 slice
    ct,cst,OFF,SIZE,align = struct.unpack('>5I', data[8:28])
    m = data[OFF:OFF+SIZE]
else:                                                     # already thin
    OFF, SIZE = 0, len(data)
    m = data

mag, cputype, cpusub, filetype, ncmds, sizeofcmds, flags = struct.unpack('<7I', m[0:28])
sections=[]   # (segname, sectname, addr, size, offset)
off=28
for i in range(ncmds):
    cmd, cmdsize = struct.unpack('<II', m[off:off+8])
    if cmd==0x1:
        segname = m[off+8:off+24].rstrip(b'\0').decode()
        nsects = struct.unpack('<I', m[off+48:off+52])[0]
        so=off+56
        for s in range(nsects):
            sn = m[so:so+16].rstrip(b'\0').decode()
            sg = m[so+16:so+32].rstrip(b'\0').decode()
            addr,size,offs = struct.unpack('<3I', m[so+32:so+44])
            sections.append((sg,sn,addr,size,offs))
            so+=68
    off+=cmdsize

def v2o(addr):
    for sg,sn,a,sz,o in sections:
        if a<=addr<a+sz:
            if sn=='__bss' or sn=='__common': return None
            return o + (addr-a)
    return None

def rd(addr,n):
    o=v2o(addr)
    if o is None: return None
    return m[o:o+n]

def u32(addr):
    b=rd(addr,4)
    return struct.unpack('<I',b)[0] if b else 0

def cstr(addr):
    if not addr: return ''
    o=v2o(addr)
    if o is None: return ''
    e=m.index(b'\0',o)
    return m[o:e].decode('utf-8',errors='replace')

def sect(name):
    for sg,sn,a,sz,o in sections:
        if sn==name: return a,sz,o
    return None

out={}

def parse_methods(addr, kind):
    res=[]
    if not addr: return res
    _b=rd(addr,8)
    if _b is None or len(_b)<8: return res
    entsize, count = struct.unpack('<II', _b)
    entsize&=0xFFFC
    if count>4000 or entsize==0: return res
    p = addr+8
    for i in range(count):
        b=rd(p,12)
        if b is None or len(b)<12: break
        name_p, types_p, imp = struct.unpack('<III', b)
        res.append({'name':cstr(name_p),'types':cstr(types_p),'imp':imp,'kind':kind})
        p+=entsize
    return res

def parse_ivars(addr):
    res=[]
    if not addr: return res
    _b=rd(addr,8)
    if _b is None or len(_b)<8: return res
    entsize,count = struct.unpack('<II', _b)
    entsize&=0xFFFC
    if count>4000 or entsize==0: return res
    p=addr+8
    for i in range(count):
        _c=rd(p,20)
        if _c is None or len(_c)<20: break
        offp, name_p, type_p, align, size = struct.unpack('<IIIII', _c)
        ofs = u32(offp) if offp else -1
        res.append({'name':cstr(name_p),'type':cstr(type_p),'offset':ofs,'size':size})
        p+=entsize
    return res

def parse_props(addr):
    res=[]
    if not addr: return res
    _b=rd(addr,8)
    if _b is None or len(_b)<8: return res
    entsize,count = struct.unpack('<II', _b)
    entsize&=0xFFFC
    if count>4000 or entsize==0: return res
    p=addr+8
    for i in range(count):
        _d=rd(p,8)
        if _d is None or len(_d)<8: break
        n,a = struct.unpack('<II', _d)
        res.append({'name':cstr(n),'attr':cstr(a)})
        p+=entsize
    return res

def parse_class(cls_addr):
    isa, superclass, cache, vtable, ro = struct.unpack('<IIIII', rd(cls_addr,20)); ro &= ~3
    flags, instanceStart, instanceSize, ivarLayout, name_p, baseMethods, baseProtocols, ivars, weakIvarLayout, baseProperties = struct.unpack('<10I', rd(ro,40))
    return {
      'addr':cls_addr,'isa':isa,'super':superclass,'flags':flags,
      'instanceStart':instanceStart,'instanceSize':instanceSize,
      'name':cstr(name_p),
      'methods':parse_methods(baseMethods,'-'),
      'ivars':parse_ivars(ivars),
      'props':parse_props(baseProperties),
    }

a,sz,o = sect('__objc_classlist')
classes=[]
for i in range(sz//4):
    ca = struct.unpack('<I', m[o+4*i:o+4*i+4])[0]
    c = parse_class(ca)
    # metaclass methods
    mc = parse_class(c['isa'])
    c['class_methods']=[dict(x,kind='+') for x in mc['methods']]
    classes.append(c)

# superclass name map via __objc_data addresses
byaddr={c['addr']:c['name'] for c in classes}
for c in classes:
    c['supername']=byaddr.get(c['super'],'?0x%x'%c['super'])

json.dump(classes, open(os.path.join(os.path.dirname(_HERE),
    'analysis', 'data', 'objc_classes.json'), 'w'), indent=1)
print("classes:", len(classes))
for c in classes:
    print("%-34s : %-24s size=0x%-4x methods=%d(+%d) ivars=%d" % (c['name'], c['supername'], c['instanceSize'], len(c['methods']), len(c['class_methods']), len(c['ivars'])))
