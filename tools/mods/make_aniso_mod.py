#!/usr/bin/env python3
"""Permanent 16x anisotropy: per-frame hook. Redirects the `call 0xfb37f0` (SetAntialiasEnable wrapper, executed every
frame by the scene post-effect apply function) at 0x25d803d to a code-cave stub that writes MaxAnisotropy=16 into the
engine sampler descriptor table ([[0x59406c8]+0x250]+0x360 + i*0x38 + 4, i in 8..15 and 17), then tail-jumps to the original
callee (args rdi/esi untouched; only rax/r10 clobbered). The table lives on the heap, so a static data patch is impossible.
"""
import json, struct, sys
STUB = 0x54A0400                      # code cave (first cave page; hooks/ct_wrap.s use 0x54A0000-0x54A0300)
CALLSITE, CALLEE = 0x25D803D, 0xFB37F0
GFX = 0x59406C8; TABLE_OFF = 0x250; BASE = 0x360; STRIDE = 0x38; ANISO = 16
IDX = [8, 9, 10, 11, 12, 13, 14, 15, 17]
def build():
    code = bytearray()
    code += b"\x49\xba" + struct.pack("<Q", GFX)         # movabs r10, &SprjGraphics
    code += b"\x4d\x8b\x12"                              # mov r10, [r10]
    code += b"\x4d\x85\xd2"                              # test r10, r10
    j1 = len(code); code += b"\x74\x00"                  # jz done (patched)
    code += b"\x4d\x8b\x92" + struct.pack("<I", TABLE_OFF)   # mov r10, [r10+0x250]
    code += b"\x4d\x85\xd2"                              # test r10, r10
    j2 = len(code); code += b"\x74\x00"                  # jz done (patched)
    for i in IDX:                                        # mov dword [r10+disp32], 16
        code += b"\x41\xc7\x82" + struct.pack("<I", BASE + STRIDE * i + 4) + struct.pack("<I", ANISO)
    done = len(code)
    code[j1 + 1] = done - (j1 + 2); code[j2 + 1] = done - (j2 + 2)
    assert code[j1 + 1] < 128 and code[j2 + 1] < 128
    rel = CALLEE - (STUB + done + 5)
    code += b"\xe9" + struct.pack("<i", rel)             # jmp CALLEE
    return bytes(code)
def callsite():
    stub_end_rel = STUB - (CALLSITE + 5)
    return b"\xe8" + struct.pack("<i", stub_end_rel)
def mod():
    return {"name": "Anisotropic filtering 16x", "type": "checkbox", "enabled": False, "memory": [
        {"offset": "%08X" % STUB, "on": build().hex(), "off": "", "absolute": True},
        {"offset": "%08X" % CALLSITE, "on": callsite().hex(), "off": "e8aeb79dfe", "absolute": True}]}
if __name__ == "__main__": print(json.dumps(mod(), indent=1))
