# Show instructions around an instruction address (syncs the decode start). Usage: python bb_ctx.py <insn_addr_hex>...
# Needs capstone + numpy, see bb_ann.py.
import sys, re
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dump_xref import *
from bb_ann import rd_str
def show(a, before=14, after=24):
    for k in range(0x40,0x80):
        lst=list(md.disasm(d[a-k-B:a-k-B+k+0x100], a-k)); 
        if any(i.address==a for i in lst): break
    idx=[n for n,i in enumerate(lst) if i.address==a][0]
    print('-----',hex(a),'func~',hex(func_start(a) or 0))
    for i in lst[max(0,idx-before):idx+after+1]:
        note=''
        m=re.search(r'rip \+ (0x[0-9a-f]+)',i.op_str)
        if m:
            t=i.address+i.size+int(m.group(1),0); note=f'  ; {t:#x} {rd_str(t) or ""}' if i.mnemonic=='lea' else f'  ; [{t:#x}]'
        print(f'{i.address:x}: {i.mnemonic} {i.op_str}{note}'+(' <<<' if i.address==a else ''))
for x in sys.argv[1:]: show(int(x,16))
