#!/usr/bin/env python3
"""Annotated disassembly around addresses in the live GOTY eboot dump.
Usage: python3 dump_ctx.py <addr_hex> [<addr_hex> ...]
Resyncs the decoder (x86 has no instruction boundaries) by trying several start
offsets and keeping the one that decodes furthest; annotates rip-relative
targets with C strings and the render-resolution globals (RES W/H)."""
import re, sys
from dump_xref import d, B, md

def best_decode(s, back=0x50, fwd=0x70):
    best, bc = None, -1
    for k in range(back, back + 20):
        st = s - k
        ins = list(md.disasm(d[st - B:st - B + k + fwd + 16], st))
        if ins and ins[-1].address > bc:
            bc, best = ins[-1].address, ins
    return best or []

def annot(i):
    m = re.search(r'rip \+ (0x[0-9a-f]+)\]', i.op_str)
    if not m:
        return ''
    t = i.address + i.size + int(m.group(1), 16)
    if t in (0x55289f8, 0x55289fc):
        return '   ; <<RES %s>>' % ('W' if t == 0x55289f8 else 'H')
    if not (B <= t < B + len(d)):
        return ''
    s = d[t - B:t - B + 60].split(b'\0')[0]
    if len(s) >= 4 and all(32 <= c < 127 for c in s):
        return '   ; "%s"' % s.decode()
    return '   ; ->%x' % t

if __name__ == '__main__':
    for a in sys.argv[1:]:
        x = int(a, 16)
        print('=' * 30, hex(x))
        for i in best_decode(x):
            if x - 0x50 <= i.address <= x + 0x70:
                print('%x: %s %s%s%s' % (i.address, i.mnemonic, i.op_str, annot(i),
                                         ' <<<' if i.address <= x < i.address + i.size else ''))
