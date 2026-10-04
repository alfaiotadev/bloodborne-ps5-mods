#!/usr/bin/env python3
"""Pose lock + call service, one hook at the follow camera update's only epilogue.
POSE LOCK: the follow-camera update (0x183ac60) has several code paths that write the pose rows (0x183b399, 0x183ebb2 look-at, 0x183ec5e, 0x183efc0 ...) and derives
the orientation as a look-at from camera position to pivot, so writes in the middle or from outside are overwritten within a frame.  Hook at 0x183f77b `add rsp,0x3d8`
(7 B) -> `jmp cave` + 2 NOPs.  When FLAG != 0 the cave copies ROW0..ROW3 to [r13+0x10..0x40] (r13 = this); the manager copies the pose from this object right after the call.
CALL SERVICE: when CALL != 0 the cave clears it and calls FN(ARG0..ARG3) (SysV: rdi,rsi,rdx,rcx) on the game thread (rsp is 16-byte aligned here; r13 and other callee-saved
regs survive the call), stores rax to RET.  Client side: write FN/ARGs, set CALL=1, poll until CALL==0, read RET.
Data block (16-byte aligned):  FLAG 0x54A0700, CALL 0x54A0702, CNT 0x54A0704, ROW0..3 0x54A0710..0x54A0740, FN 0x54A0750, ARG0..3 0x54A0758..0x54A0770, RET 0x54A0778.
Scratch for warp args: MAPID 0x54A0C00, POS 0x54A0C10 (x,y,z,1), ROT 0x54A0C20 (pitchRad, yawRad, 0, 0).  Cave at 0x54A0780 (max 0x54A0E00).
HEAD CAMERA (flag-gated by HC_FLAG): at the epilogue, after the pose-lock copy, the cave replaces the camera POSITION row ([r13+0x40]) with the player's head bone in world space
+ an offset along the camera's own right/up/forward rows (HC_R, HC_U, HC_F, metres).  Head = bone HC_BONEOFF/0x30 (78 = Head) of the live model-space pose array pl->[+0xa68]->[+0x50]
(hkQsTransform, stride 0x30), moved to the world with the model->world rows at [pl+0x58]+0x320..0x350 (row-vector convention, translation row last).  The game's own position row is
saved to HC_SAVED and written back by a second hook at the follow-camera update ENTRY (0x183ac60, 6 B), so the game's camera state (orbit, chase, look-at) never sees the override and
the orientation rows stay the game's own (pad-driven).
Head-cam data (0x54A0E00..): HC_FLAG, HC_VALID, HC_STATE (1 = orientation hold), HC_GOODV (last good rows valid), HC_BONEOFF (i32), HC_R/U/F, HC_ENTER2/LEAVE2 (squared metres: hold starts when the game's camera is closer than sqrt(ENTER2) to the pivot, ends beyond sqrt(LEAVE2)),
HC_SAVED (16 B game position), HC_PIVOT (0,1.42,0,0 pivot offset above the model root), HC_GOOD (3 x 16 B last good right/up/forward rows).  Entry cave 0x54A1000, cast cave 0x54A1100, manager cave 0x54A1200.
SQUEEZE HOLD: when the camera is squeezed against a wall the game pulls its camera next to the pivot and the look-at orientation spins wildly; while the game's camera is closer than ENTER the cave
keeps showing the last good rows (the head position still follows).
CAMERA COLLISION OFF: the follow camera's six collision casts all call 0x1c090e0 (filter 0x25, camera only).  A third hook at its entry (cave 0x54A0A80) returns 0 (no hit) while HC_FLAG && HC_NOCOLL,
so the game's camera is no longer pulled in against walls (gated by HC_NOCOLL alone) (the pull-in flickers every frame and makes the look-at orientation tornado).
Order: data + caves first, hooks last; restore hooks first."""
import struct, math
FLAG, CALL, CNT = 0x54A0700, 0x54A0702, 0x54A0704
ROW0, ROW1, ROW2, ROW3 = 0x54A0710, 0x54A0720, 0x54A0730, 0x54A0740
FN, ARG0, ARG1, ARG2, ARG3, RET = 0x54A0750, 0x54A0758, 0x54A0760, 0x54A0768, 0x54A0770, 0x54A0778
MAPID, POS, ROT = 0x54A0C00, 0x54A0C10, 0x54A0C20
CAVE = 0x54A0780
HC_FLAG, HC_VALID, HC_STATE, HC_GOODV, HC_BONEOFF, HC_R, HC_U, HC_F, HC_ENTER2, HC_LEAVE2 = 0x54A0E00, 0x54A0E01, 0x54A0E02, 0x54A0E03, 0x54A0E04, 0x54A0E08, 0x54A0E0C, 0x54A0E10, 0x54A0E14, 0x54A0E18
HC_SAVED, HC_PIVOT, HC_GOOD, HC_NOCOLL, HC_FLAG2, HC_FACE, HC_FACE2 = 0x54A0E20, 0x54A0E30, 0x54A0E40, 0x54A0E70, 0x54A0E71, 0x54A0E72, 0x54A0E73
C_PI, C_NEGPI, C_2PI, HC_FACEOFF = 0x54A0E80, 0x54A0E84, 0x54A0E88, 0x54A0E8C
CAVE_M = 0x54A1200
HOOK_M, BACK_M, ORIG_M = 0x1836C54, 0x1836C59, bytes.fromhex("c5f8295b40")
CAVE_C = 0x54A1100
HOOK_C, BACK_C, ORIG_C = 0x1C090E0, 0x1C090E6, bytes.fromhex("554889e54157")
G_WCM = 0x593E878
CAVE_E = 0x54A1000
HOOK_E, BACK_E, ORIG_E = 0x183AC60, 0x183AC66, bytes.fromhex("554889e54157")
HOOK, BACK, ORIG = 0x183F77B, 0x183F782, bytes.fromhex("4881c4d8030000")
# legacy hooks of the first attempt (removed if present)
LEG_A, LEG_A_ORIG, LEG_B, LEG_B_ORIG = 0x183B399, bytes.fromhex("c4c178294510"), 0x183B649, bytes.fromhex("c4c178295540")
def rip(at, insn_len, target): return struct.pack("<i", target - (at + insn_len))
def vss(op, d, s1, s2):            # VEX.F3 scalar op (0x58 add, 0x59 mul, 0x5c sub) xmm_d = xmm_s1 op xmm_s2  (xmm0..xmm7)
    return bytes([0xC5, 0x80 | ((~s1 & 0xF) << 3) | 0x02, op, 0xC0 | (d << 3) | s2])
def vld(x, base, disp): return b"\xc5\xfa\x10" + bytes([0x80 | (x << 3) | base]) + struct.pack("<i", disp)      # vmovss xmm_x,[base+disp32]  (base = rdx(2))
def vst(x, base, disp): return b"\xc5\xfa\x11" + bytes([0x80 | (x << 3) | base]) + struct.pack("<i", disp)      # vmovss [base+disp32],xmm_x
class Asm:
    """Tiny assembler: raw bytes + rip-relative operands + rel32 jumps to labels."""
    def __init__(self, base): self.base, self.c, self.labels, self.fix = base, bytearray(), {}, []
    def raw(self, b): self.c += b
    def rip(self, opcode, target, imm=b""):                       # [opcode][disp32 -> target][imm]
        at = self.base + len(self.c); self.c += opcode; self.c += rip(at, len(opcode) + 4 + len(imm), target); self.c += imm
    def jcc(self, cc, label): self.c += {"e": b"\x0f\x84", "ne": b"\x0f\x85", "ae": b"\x0f\x83", "be": b"\x0f\x86"}[cc]; self.fix.append((len(self.c), label)); self.c += b"\0\0\0\0"
    def jmp(self, label): self.c += b"\xe9"; self.fix.append((len(self.c), label)); self.c += b"\0\0\0\0"
    def bind(self, label): self.labels[label] = len(self.c)
    def jmp_abs(self, target): self.c += b"\xe9" + rip(self.base + len(self.c), 5, target)
    def done(self):
        for at, label in self.fix: self.c[at:at + 4] = struct.pack("<i", self.labels[label] - (at + 4))
        return bytes(self.c)
def build_cave():
    A = Asm(CAVE)
    A.rip(b"\xff\x05", CNT)                                                      # inc dword [rip+CNT]
    A.rip(b"\x80\x3d", FLAG, b"\x00"); A.jcc("e", "pose_end")                     # cmp byte [FLAG],0 ; je
    for row, off in ((ROW0, 0x10), (ROW1, 0x20), (ROW2, 0x30), (ROW3, 0x40)):
        A.rip(b"\xc5\xf8\x28\x05", row)                                           # vmovaps xmm0,[rip+row]
        A.raw(b"\xc4\xc1\x78\x29\x45" + bytes([off]))                               # vmovaps [r13+off],xmm0
    A.bind("pose_end")
    # ---- head camera ----
    A.rip(b"\x80\x3d", HC_FLAG, b"\x00"); A.jcc("e", "hc_end")
    A.rip(b"\x48\x8b\x05", G_WCM); A.raw(b"\x48\x85\xc0"); A.jcc("e", "hc_end")   # mov rax,[WorldChrMan]; test; je
    A.raw(b"\x48\x8b\x40\x60"); A.raw(b"\x48\x85\xc0"); A.jcc("e", "hc_end")        # mov rax,[rax+0x60] (player ChrIns)
    A.raw(b"\x48\x8b\x88\x68\x0a\x00\x00"); A.raw(b"\x48\x85\xc9"); A.jcc("e", "hc_end")  # mov rcx,[rax+0xa68]
    A.raw(b"\x48\x8b\x49\x50"); A.raw(b"\x48\x85\xc9"); A.jcc("e", "hc_end")        # mov rcx,[rcx+0x50] (pose array)
    A.raw(b"\x48\x8b\x50\x58"); A.raw(b"\x48\x85\xd2"); A.jcc("e", "hc_end")        # mov rdx,[rax+0x58] (module container)
    A.rip(b"\x48\x63\x35", HC_BONEOFF); A.raw(b"\x48\x01\xf1")                        # movsxd rsi,[BONEOFF]; add rcx,rsi
    A.raw(b"\xc5\xf8\x10\x82\x50\x03\x00\x00")                                      # vmovups xmm0,[rdx+0x350]   (model->world translation row)
    for tof, rowoff in ((None, 0x320), (4, 0x330), (8, 0x340)):
        A.raw(b"\xc4\xe2\x79\x18" + (b"\x11" if tof is None else bytes([0x51, tof])))   # vbroadcastss xmm2,[rcx(+t)]
        A.raw(b"\xc5\xe8\x59\x92" + struct.pack("<i", rowoff))                         # vmulps xmm2,xmm2,[rdx+row]
        A.raw(b"\xc5\xf8\x58\xc2")                                                      # vaddps xmm0,xmm0,xmm2
    for hc, off in ((HC_R, 0x10), (HC_U, 0x20), (HC_F, 0x30)):
        A.rip(b"\xc4\xe2\x79\x18\x15", hc)                                              # vbroadcastss xmm2,[rip+hc]
        A.raw(b"\xc4\xc1\x68\x59\x55" + bytes([off]))                                   # vmulps xmm2,xmm2,[r13+off]  (camera right/up/forward row)
        A.raw(b"\xc5\xf8\x58\xc2")                                                      # vaddps xmm0,xmm0,xmm2
    A.raw(b"\xc4\xc1\x78\x28\x5d\x40")                                                # vmovaps xmm3,[r13+0x40]   (game's own position)
    A.rip(b"\xc5\xf8\x29\x1d", HC_SAVED)                                                # vmovaps [HC_SAVED],xmm3
    # squeeze hold: distance (game camera -> pivot = model root + HC_PIVOT)
    A.raw(b"\xc5\xf8\x10\xaa\x50\x03\x00\x00")                                      # vmovups xmm5,[rdx+0x350]
    A.rip(b"\xc5\xd0\x58\x2d", HC_PIVOT)                                                # vaddps xmm5,xmm5,[HC_PIVOT]
    A.raw(b"\xc5\xe0\x5c\xf5")                                                          # vsubps xmm6,xmm3,xmm5
    A.raw(b"\xc4\xe3\x49\x40\xf6\x71")                                                # vdpps xmm6,xmm6,xmm6,0x71  -> dist^2 in lane 0
    A.rip(b"\x80\x3d", HC_STATE, b"\x00"); A.jcc("ne", "in_hold")
    A.rip(b"\xc5\xfa\x10\x3d", HC_ENTER2); A.raw(b"\xc5\xf8\x2f\xf7"); A.jcc("ae", "healthy")   # vmovss xmm7,[ENTER2]; vcomiss xmm6,xmm7; jae healthy
    A.rip(b"\xc6\x05", HC_STATE, b"\x01"); A.jmp("apply_hold")
    A.bind("in_hold")
    A.rip(b"\xc5\xfa\x10\x3d", HC_LEAVE2); A.raw(b"\xc5\xf8\x2f\xf7"); A.jcc("be", "apply_hold")  # dist^2 <= LEAVE2 -> keep holding
    A.rip(b"\xc6\x05", HC_STATE, b"\x00")                                                # left the squeeze
    A.bind("healthy")                                                                       # remember the current rows as "last good"
    for off in (0x10, 0x20, 0x30):
        A.raw(b"\xc4\xc1\x78\x10\x6d" + bytes([off]))                                       # vmovups xmm5,[r13+off]
        A.rip(b"\xc5\xf8\x11\x2d", HC_GOOD + (off - 0x10))                                   # vmovups [HC_GOOD+..],xmm5
    A.rip(b"\xc6\x05", HC_GOODV, b"\x01"); A.jmp("hold_end")
    A.bind("apply_hold")
    A.rip(b"\x80\x3d", HC_GOODV, b"\x00"); A.jcc("e", "hold_end")
    for off in (0x10, 0x20, 0x30):
        A.rip(b"\xc5\xf8\x10\x2d", HC_GOOD + (off - 0x10))                                   # vmovups xmm5,[HC_GOOD+..]
        A.raw(b"\xc4\xc1\x78\x11\x6d" + bytes([off]))                                       # vmovups [r13+off],xmm5
    A.bind("hold_end")
    A.rip(b"\xc6\x05", HC_VALID, b"\x01")                                                # mov byte [HC_VALID],1
    A.raw(b"\xc4\xc1\x78\x29\x45\x40")                                                # vmovaps [r13+0x40],xmm0
    A.bind("hc_end")
    # ---- body faces the camera (FPS look): player yaw := camera yaw - pi, then the game's own 0x1cbcf30(pl,1) applies it ----
    A.rip(b"\x80\x3d", HC_FACE, b"\x00"); A.jcc("e", "face_end")
    A.rip(b"\x48\x8b\x05", G_WCM); A.raw(b"\x48\x85\xc0"); A.jcc("e", "face_end")
    A.raw(b"\x48\x8b\x40\x60"); A.raw(b"\x48\x85\xc0"); A.jcc("e", "face_end")        # rax = player ChrIns
    A.raw(b"\x48\x89\xc3")                                                               # mov rbx,rax   (callee-saved across the call; restored by the epilogue pops)
    A.raw(b"\x48\x8b\x88\xb0\x03\x00\x00"); A.raw(b"\x48\x85\xc9"); A.jcc("e", "face_end")   # mov rcx,[rax+0x3b0]
    A.raw(b"\x48\x8b\x49\x68"); A.raw(b"\x48\x85\xc9"); A.jcc("e", "face_end")                # mov rcx,[rcx+0x68]  (X)
    A.raw(b"\xc4\xc1\x7a\x10\x85\x44\x01\x00\x00")                                      # vmovss xmm0,[r13+0x144]  (follow camera yaw angle)
    A.rip(b"\xc5\xfa\x58\x05", HC_FACEOFF)                                              # vaddss xmm0,xmm0,[FACEOFF]
    A.rip(b"\xc5\xfa\x5c\x05", C_PI)                                                    # vsubss xmm0,xmm0,[PI]
    A.rip(b"\xc5\xf8\x2f\x05", C_NEGPI); A.jcc("ae", "face_wrapped")                    # vcomiss xmm0,[-PI]; jae
    A.rip(b"\xc5\xfa\x58\x05", C_2PI)                                                   # vaddss xmm0,xmm0,[2PI]
    A.bind("face_wrapped")
    A.raw(b"\xc5\xfa\x11\x81\xd4\x01\x00\x00")                                      # vmovss [rcx+0x1d4],xmm0   (player yaw)
    A.raw(b"\x48\x89\xdf\xbe\x01\x00\x00\x00")                                      # mov rdi,rbx ; mov esi,1
    A.raw(b"\x48\xb8" + struct.pack("<Q", 0x1CBCF30)); A.raw(b"\xff\xd0")                # mov rax,0x1cbcf30 ; call rax
    A.bind("face_end")
    # ---- body faces the camera, DISPLAY ONLY (FACE2): rotate the model->world rows R0/R2 about the root so the model's forward (-R2) points along the camera's horizontal forward.
    #      cos = f.c, sin = fz*cx - fx*cz with f = -(R2x,R2z), c = (-rz, rx) from the camera right row; the game's state (facing, movement) stays untouched.  Needs no trig.
    A.rip(b"\x80\x3d", HC_FACE2, b"\x00"); A.jcc("e", "face2_end")
    A.rip(b"\x48\x8b\x05", G_WCM); A.raw(b"\x48\x85\xc0"); A.jcc("e", "face2_end")
    A.raw(b"\x48\x8b\x40\x60"); A.raw(b"\x48\x85\xc0"); A.jcc("e", "face2_end")
    A.raw(b"\x48\x8b\x50\x58"); A.raw(b"\x48\x85\xd2"); A.jcc("e", "face2_end")          # rdx = module container (model->world rows at +0x320..)
    A.raw(vld(0, 2, 0x340)); A.raw(vld(1, 2, 0x348))                                         # xmm0 = R2.x, xmm1 = R2.z
    A.raw(b"\xc4\xc1\x7a\x10\x55\x10"); A.raw(b"\xc4\xc1\x7a\x10\x5d\x18")             # xmm2 = rx ([r13+0x10]), xmm3 = rz ([r13+0x18])
    A.raw(vss(0x59, 4, 0, 3)); A.raw(vss(0x59, 5, 1, 2)); A.raw(vss(0x5c, 4, 4, 5))          # xmm4 = cos = R2x*rz - R2z*rx
    A.raw(vss(0x59, 5, 1, 3)); A.raw(vss(0x59, 6, 0, 2)); A.raw(vss(0x58, 5, 5, 6))          # xmm5 = sin = R2z*rz + R2x*rx
    for xo, zo in ((0x340, 0x348), (0x320, 0x328)):                                           # rotate R2, then R0:  x' = x*cos + z*sin ; z' = z*cos - x*sin
        A.raw(vld(0, 2, xo)); A.raw(vld(1, 2, zo))
        A.raw(vss(0x59, 6, 0, 4)); A.raw(vss(0x59, 7, 1, 5)); A.raw(vss(0x58, 6, 6, 7))       # xmm6 = x'
        A.raw(vss(0x59, 7, 1, 4)); A.raw(vss(0x59, 2, 0, 5)); A.raw(vss(0x5c, 7, 7, 2))       # xmm7 = z'
        A.raw(vst(6, 2, xo)); A.raw(vst(7, 2, zo))
    A.bind("face2_end")
    # ---- call service ----
    A.rip(b"\x80\x3d", CALL, b"\x00"); A.jcc("e", "call_end")
    A.rip(b"\xc6\x05", CALL, b"\x00")
    A.rip(b"\x48\x8b\x3d", ARG0); A.rip(b"\x48\x8b\x35", ARG1); A.rip(b"\x48\x8b\x15", ARG2); A.rip(b"\x48\x8b\x0d", ARG3)
    A.rip(b"\x48\x8b\x05", FN); A.raw(b"\xff\xd0"); A.rip(b"\x48\x89\x05", RET)
    A.bind("call_end")
    A.raw(ORIG); A.jmp_abs(BACK)
    c = A.done(); assert CAVE + len(c) <= CAVE_E, hex(CAVE + len(c)); return c
def build_cave_entry():
    """Follow-camera update entry: give the game back its own position row (saved by the head-cam epilogue) before it reads its state."""
    A = Asm(CAVE_E)
    A.rip(b"\x80\x3d", HC_VALID, b"\x00"); A.jcc("e", "skip")
    A.rip(b"\xc5\xf8\x28\x05", HC_SAVED); A.raw(b"\xc5\xf8\x29\x47\x40")           # vmovaps xmm0,[SAVED]; vmovaps [rdi+0x40],xmm0
    A.rip(b"\x80\x3d", HC_FLAG, b"\x00"); A.jcc("ne", "skip")
    A.rip(b"\xc6\x05", HC_VALID, b"\x00")                                               # head cam switched off: clear VALID after one last restore
    A.bind("skip"); A.raw(ORIG_E); A.jmp_abs(BACK_E); return A.done()
def build_cave_mgr():
    """MANAGER MODE (HC_FLAG2): override the position row only where the camera manager copies the follow camera's pose into ITS OWN pose (0x1836c54, `vmovaps [rbx+0x40],xmm3`;
    xmm0..xmm2 = right/up/forward rows, xmm3 = position).  The follow camera object keeps the game's own state, so no restore hooks are needed."""
    A = Asm(CAVE_M)
    A.rip(b"\x80\x3d", HC_FLAG2, b"\x00"); A.jcc("e", "orig")
    A.raw(b"\x50\x51\x52\x56")                                                          # push rax, rcx, rdx, rsi
    A.rip(b"\x48\x8b\x05", G_WCM); A.raw(b"\x48\x85\xc0"); A.jcc("e", "pop")
    A.raw(b"\x48\x8b\x40\x60"); A.raw(b"\x48\x85\xc0"); A.jcc("e", "pop")
    A.raw(b"\x48\x8b\x88\x68\x0a\x00\x00"); A.raw(b"\x48\x85\xc9"); A.jcc("e", "pop")
    A.raw(b"\x48\x8b\x49\x50"); A.raw(b"\x48\x85\xc9"); A.jcc("e", "pop")
    A.raw(b"\x48\x8b\x50\x58"); A.raw(b"\x48\x85\xd2"); A.jcc("e", "pop")
    A.rip(b"\x48\x63\x35", HC_BONEOFF); A.raw(b"\x48\x01\xf1")
    A.raw(b"\xc5\xf8\x10\xa2\x50\x03\x00\x00")                                      # vmovups xmm4,[rdx+0x350]  (model->world translation row)
    for tof, rowoff in ((None, 0x320), (4, 0x330), (8, 0x340)):
        A.raw(b"\xc4\xe2\x79\x18" + (b"\x29" if tof is None else bytes([0x69, tof])))   # vbroadcastss xmm5,[rcx(+t)]  (bone translation component)
        A.raw(b"\xc5\xd0\x59\xaa" + struct.pack("<i", rowoff))                         # vmulps xmm5,xmm5,[rdx+row]
        A.raw(b"\xc5\xd8\x58\xe5")                                                      # vaddps xmm4,xmm4,xmm5
    for hc, reg in ((HC_R, 0xe8), (HC_U, 0xe9), (HC_F, 0xea)):                              # offsets along the camera's right/up/forward rows (xmm0/xmm1/xmm2)
        A.rip(b"\xc4\xe2\x79\x18\x2d", hc)                                              # vbroadcastss xmm5,[rip+hc]
        A.raw(b"\xc5\xd0\x59" + bytes([reg]))                                            # vmulps xmm5,xmm5,xmm0/1/2
        A.raw(b"\xc5\xd8\x58\xe5")                                                      # vaddps xmm4,xmm4,xmm5
    A.raw(b"\xc5\xf8\x28\xdc")                                                          # vmovaps xmm3,xmm4
    A.bind("pop"); A.raw(b"\x5e\x5a\x59\x58")                                           # pop rsi, rdx, rcx, rax
    A.bind("orig"); A.raw(ORIG_M); A.jmp_abs(BACK_M); return A.done()
def hook_mgr(): return b"\xe9" + rip(HOOK_M, 5, CAVE_M)
def build_cave_cast():
    A = Asm(CAVE_C)
    A.rip(b"\x80\x3d", HC_NOCOLL, b"\x00"); A.jcc("e", "orig")
    A.raw(b"\x31\xc0\xc3")                                                               # xor eax,eax ; ret   (no hit)
    A.bind("orig"); A.raw(ORIG_C); A.jmp_abs(BACK_C); return A.done()
def hook_cast(): return b"\xe9" + rip(HOOK_C, 5, CAVE_C) + b"\x90"
def hook_entry(): return b"\xe9" + rip(HOOK_E, 5, CAVE_E) + b"\x90"
def hook(): return b"\xe9" + rip(HOOK, 5, CAVE) + b"\x90\x90"
def rows_from_yaw_pitch(yaw, pitch, pos):
    sy, cy, sp, cp = math.sin(yaw), math.cos(yaw), math.sin(pitch), math.cos(pitch)
    return struct.pack("<16f", cy, 0, -sy, 0, -sp * sy, cp, -sp * cy, 0, cp * sy, sp, cp * cy, 0, pos[0], pos[1], pos[2], 1.0)
if __name__ == "__main__":
    c = build_cave(); print("cave %d B, ends %#x, hook %s" % (len(c), CAVE + len(c), hook().hex()))
    assert CAVE + len(c) <= MAPID
