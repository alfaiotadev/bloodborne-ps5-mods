"""Offline helpers (xrefs, strings, function starts) over a flat memory image of the game's eboot.
Environment: PS5_EBOOT_DUMP = path of the image (required), PS5_EBOOT_BASE = virtual address of its first byte (default 0x400000).
Needs numpy + capstone."""
import numpy as np, re, sys, os
from capstone import *
d=open(os.environ["PS5_EBOOT_DUMP"],'rb').read(); B=int(os.environ.get("PS5_EBOOT_BASE","0x400000"),0)
arr=np.frombuffer(d,dtype=np.uint8); a32=arr.astype(np.uint32)
N=0x54dc000-B
disp=(a32[:N]|(a32[1:N+1]<<8)|(a32[2:N+2]<<16)|(a32[3:N+3]<<24)).astype(np.uint32).view(np.int32).astype(np.int64)
pos=np.arange(N,dtype=np.int64)+B
md=Cs(CS_ARCH_X86,CS_MODE_64)
def strs(rx):
    out=[]
    for m in re.finditer(rx.encode(),d):
        s=m.start(); e=d.find(b'\0',s); st=d.rfind(b'\0',0,s)+1
        out.append((st+B,d[st:e].decode('latin1')))
    return sorted(set(out))
def xrefs(t):
    res=set()
    for tail in (0,1,4):
        for p in np.where(pos+4+tail+disp==t)[0]: res.add(int(pos[p]))
    return sorted(res)
def insn_at(addr):
    for back in range(2,10):
        s=addr-back
        for i in md.disasm(d[s-B:s-B+24],s):
            if i.address<=addr<i.address+i.size and 'rip' in i.op_str: return i
            if i.address>addr: break
    return None
def func_start(a):
    # walk back to a likely prologue "55 48 89 e5" 
    q=d.rfind(bytes.fromhex('554889e5'),max(0,a-B-8000),a-B)
    return q+B if q>=0 else None
