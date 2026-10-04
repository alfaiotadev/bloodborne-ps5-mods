# Disassembly helper (capstone) over a flat eboot memory dump ($PS5_EBOOT_DUMP, see dump_xref.py): annotated linear disassembly.
# Usage: python bb_ann.py <start_hex> <end_hex>
# Needs capstone + numpy (pip install capstone numpy).
import sys, struct
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dump_xref import *
def rd_str(a):
    o=a-B
    if o<0 or o+4>len(d): return None
    if d[o+1]==0 and d[o]>=0x20:
        s=bytearray(); i=o
        while i+1<len(d) and d[i+1]==0 and d[i]!=0 and len(s)<80: s.append(d[i]); i+=2
        return 'u"'+s.decode('latin1')+'"'
    s=bytearray(); i=o
    while i<len(d) and d[i]!=0 and 0x20<=d[i]<0x7f and len(s)<80: s.append(d[i]); i+=1
    return '"'+s.decode('latin1')+'"' if len(s)>=3 else None
def dis(start,end,only_interesting=False):
    for i in md.disasm(d[start-B:end-B], start):
        note=''
        if i.mnemonic=='lea' and 'rip' in i.op_str:
            import re
            m=re.search(r'rip \+ (0x[0-9a-f]+|\d+)',i.op_str)
            if m:
                t=i.address+i.size+int(m.group(1),0)
                s=rd_str(t); note=f'  ; {t:#x} {s or ""}'
        print(f'{i.address:x}: {i.mnemonic} {i.op_str}{note}')
if __name__=='__main__':
    dis(int(sys.argv[1],16), int(sys.argv[2],16))
