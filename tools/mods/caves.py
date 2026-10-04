"""Tiny x86-64 assembler helpers for building code caves (no external assembler needed).

A *cave* is a block of code written into unused, executable memory inside eboot.bin's address space (0x54A0000-0x54A4000 in Bloodborne
CUSA03173 v01.09).  A *hook* is a 5-byte `jmp rel32` written over the first instructions of a game function (plus NOPs when whole instructions
are longer than 5 bytes); the cave re-executes the displaced instructions and jumps back.  Everything here produces plain bytes, so the result
can be shipped as an onionHEN cheat entry ("offset" / "on" / "off" in hex)."""
import struct

def rip(at, insn_len, target):
    """rel32 displacement for a RIP-relative operand: target - (address of the NEXT instruction)."""
    return struct.pack("<i", target - (at + insn_len))

class Asm:
    """Raw bytes + RIP-relative operands + rel32 jumps to labels."""
    def __init__(self, base): self.base, self.c, self.labels, self.fix = base, bytearray(), {}, []
    def raw(self, b): self.c += b
    def rip(self, opcode, target, imm=b""):
        at = self.base + len(self.c); self.c += opcode; self.c += rip(at, len(opcode) + 4 + len(imm), target); self.c += imm
    def jcc(self, cc, label):
        self.c += {"e": b"\x0f\x84", "ne": b"\x0f\x85", "ae": b"\x0f\x83", "be": b"\x0f\x86", "a": b"\x0f\x87", "p": b"\x0f\x8a", "b": b"\x0f\x82", "le": b"\x0f\x8e"}[cc]; self.fix.append((len(self.c), label)); self.c += b"\0\0\0\0"
    def call(self, label): self.c += b"\xe8"; self.fix.append((len(self.c), label)); self.c += b"\0\0\0\0"
    def jmp(self, label): self.c += b"\xe9"; self.fix.append((len(self.c), label)); self.c += b"\0\0\0\0"
    def bind(self, label): self.labels[label] = len(self.c)
    def jmp_abs(self, target): self.c += b"\xe9" + rip(self.base + len(self.c), 5, target)
    def done(self):
        for at, label in self.fix: self.c[at:at + 4] = struct.pack("<i", self.labels[label] - (at + 4))
        return bytes(self.c)

def vss(op, d, s1, s2):
    """VEX.F3 scalar-single op xmm_d = xmm_s1 op xmm_s2 (xmm0..xmm7); op: 0x58 add, 0x59 mul, 0x5c sub."""
    return bytes([0xC5, 0x80 | ((~s1 & 0xF) << 3) | 0x02, op, 0xC0 | (d << 3) | s2])
def vld(x, base, disp):   # vmovss xmm_x, [base+disp32]   (base register number, e.g. rdx = 2)
    return b"\xc5\xfa\x10" + bytes([0x80 | (x << 3) | base]) + struct.pack("<i", disp)
def vst(x, base, disp):   # vmovss [base+disp32], xmm_x
    return b"\xc5\xfa\x11" + bytes([0x80 | (x << 3) | base]) + struct.pack("<i", disp)

def hook5(at, cave):                # jmp rel32 over exactly 5 bytes
    return b"\xe9" + rip(at, 5, cave)
def hook(at, cave, total):          # jmp rel32 + NOP padding up to `total` bytes (whole displaced instructions)
    return hook5(at, cave) + b"\x90" * (total - 5)
