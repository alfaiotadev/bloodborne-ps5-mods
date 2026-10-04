#!/usr/bin/env python3
"""FPS camera bolted to the player's head (Bloodborne CUSA03173 v01.09), as three onionHEN cheat mods:
  "FPS head camera (experimental)" (core), "FPS head camera: body faces the view" (FACE2 flag) and "FPS head camera: aim at the lock-on target" (AIM flag).
Only code patches + a data block at 0x54A0E00; no runtime tool is needed.

CAVES
  1. MANAGER cave (CAVE_MGR 0x54A1600, 2556 bytes, written as three entries).  Hook 0x1836c54 (5 bytes) in the camera manager update 0x18368b0: the store of the position row
     `vmovaps [rbx+0x40],xmm3` after the follow-camera update; rbx = the manager's output pose, xmm0/1/2 = right/up/forward rows, xmm3 = position.  The cave, in this order:
       - PAD: a double-click of the touchpad (two rising edges within 30 frames) toggles MODE.  The DualSense report ring of libScePad (12 x 0xe0 bytes, buttons dword first) is
         found through the game's import slots 0x57E5B30 (-> libScePad+0xa30) and 0x57E4E90 (-> +0x13c0; their distance and the page offset are the layout check - the library's code itself must never be read, it is execute-only); runs even while MODE is 0.
       - HEAD: matrix 68 of the animated WORLD-space bone matrices (170 x 3x4 floats, stride 0x30, translation in column 3), held by a pose holder reachable from the model container
         ([pl+0x48], vtable 0x579CF10): [mod+0x18], [mod+0x20], [mod+0x5f8] or (one session, flag HOSTA = 0x10000 in HOLD) [A+0x460], [A+0x470], [A+0x478] with A = [mod+0x10] (vtable 0x57A2AC0).
         The slot offsets change between sessions and after a respawn, so the cave caches the working
         holder/slot (HOLD, ARROFF) and rescans slots 0..0x600 of the holders when the cached one fails the plausibility test (head -0.5..2.4 m above the feet, < 1.5 m horizontally);
         failed scans back off for 120 frames (COOL).  If nothing is found the camera is feet + FALLV (fixed standing head height).
       - ORIGIN: the physics body X = [[pl+0x3b0]+0x68], position at X+0x1e0 (the model matrix [pl+0x58]+0x350 is zero after a respawn).
       - 30 Hz POSE: the pose is re-evaluated at 30 Hz in some maps while origin and camera run at 60 Hz; (head - origin) is latched when the array changes, smoothed (ALPHA) and added to
         the current origin.  HMIN keeps the camera from dipping below walking height (rolls).  R/U/F offsets move the eye along the game's camera rows; LIMIT refuses heads that are
         too far from the game's camera (cutscenes, garbage poses).
       - DEAD: when the player's HP ([[pl+0x3b0]+0x20]+0xf8) is <= 0 (flag DEADF) there is no HMIN floor and the view rows are rebuilt from the head bone matrix (HA; forward = column 2, up = column 0, right = -column 1),
         eased with DALPHA from the game's last view (FS/US) and orthonormalised; the final camera y is at least origin.y + DFLOOR (0.30 m).  AIM is skipped while dead and the FACE2 epilogue is suspended.
       - AIM (flag AIM): while the game's lock-on camera has a target (pointer in [mgr+0x110], lock point xyz at [mgr+0x120]) the view is rotated towards it; stored as a camera-space
         offset (TR, TU) of the game's forward that persists after the lock is released and fades while the user turns the camera.
  2. CAST cave (CAVE_CAST 0x54A1100, hook 0x1c090e0, the six follow-camera collision casts are its only callers): with NOCOLL it returns "no hit" so the camera is not pulled against walls.
  3. EPILOGUE cave (CAVE_EPI 0x54A0780, hook 0x183f77b, `add rsp,0x3d8`): FACE2 rotates the model->world rows R0/R2 about the character root so the body is *displayed* facing the
     camera direction (cos = R2x*rz - R2z*rx, sin = R2z*rz + R2x*rx), only while MODE (the head camera) is on, so switching to third person restores the normal body.  Side effect: the coat/hood cloth disappears while it is on.

LOAD SAFETY (the hooks are live from game start, also while saves and maps load): every pointer is range-checked (game heap = 0x2_0000_0000..0x3_FFFF_FFFF, low dword >= 0x10000; the slot scan
dereferenced the packed integers 0x1_0000_0003 and 0x5_0000_0000 and crashed the game twice) and every object is identified by its vtable before it is read or written; if a check fails the cave does nothing and
the game runs its normal camera.

CHEAT ENTRY RULES (see build_cheats.py): onionHEN keeps every entry in 1024-byte buffers (longer entries are skipped, the hooks would then jump into an empty cave), so build_cheats.py splits
long caves into 1000-byte chunks; caves/data get off == on (onionHEN refuses to toggle a mod off when an off value is empty); the cave's own state (ARROFF D+0x14, COOL D+0x2C, HOLD D+0x3C)
is deliberately NOT part of any entry so that toggling the cheat never resets it.  Apply order: data, caves, then hooks last; MODE last of all.

DATA BLOCK 0x54A0E00: +0x04 BONEOFF i32 (68*0x30), +0x08/0C/10 R/U/F (0, 0.17, 0.32 m), +0x14 ARROFF, +0x18 LIMIT (100.0), +0x1C MINN (0.5), +0x20/24/28 YMIN/YMAX/R2, +0x2C COOL,
+0x30 HMIN (1.25), +0x34 SNAP2 (1.0), +0x38 ALPHA (0.5), +0x3C HOLD, +0x40 LASTH, +0x50 LASTO, +0x60 OFFS, +0x70 NOCOLL, +0x71 MODE, +0x72 AIM, +0x73 FACE2, +0x75 PADTOG, +0x76 PADPREV,
+0x74 DEADF, +0x78 FRAME, +0x7C PADLAST, +0x80 FPSFOV, +0x84 TPFOV (radians per FOV degree, copied into the Wide-FOV constant 0x54A0500 every frame), +0x90 FALLV, +0xA0..0xBF aim constants, +0xC0..0xFF masks, +0x118 TR, +0x11C TU, +0x120 FPREV, +0x130 DECAY, MOTCOS, TINY, +0x140 DALPHA, +0x144 DEPS, +0x148 HA, +0x150 FS, +0x160 US, +0x170 DFLOOR, +0x174 DFLR, +0x178 TSCALE, +0x17C SLOWMIN, +0x180 SLOWHOLD, +0x184 SLOWG, +0x188 DCNT, +0x18C FASTMAX, +0x190 FASTEND.
Usage: python3 make_head_camera_mod.py [--u 0.17] [--f 0.32] [--r 0.0] [--bone 68]   -> prints a JSON list with the three mods (not chunked; use build_cheats.py for release files)."""
import json, math, struct, sys
from make_fov_mod import CONST_ADDR as FOVC       # the Wide-FOV mod's float constant (radians per FOV degree)
from caves import Asm, rip, vss, vld, vst, hook5, hook

# ---- data block -------------------------------------------------------------------------------
D = 0x54A0E00
NOCOLL, MODE, FACE2 = D + 0x70, D + 0x71, D + 0x73
BONEOFF, OFF_R, OFF_U, OFF_F, ARROFF, LIMIT, MINN = D + 0x04, D + 0x08, D + 0x0C, D + 0x10, D + 0x14, D + 0x18, D + 0x1C
YMIN, YMAX, R2, COOL, HMIN = D + 0x20, D + 0x24, D + 0x28, D + 0x2C, D + 0x30
SNAP2, ALPHA, HOLD, OFFS, FALLV = D + 0x34, D + 0x38, D + 0x3C, D + 0x60, D + 0x90
AIM = D + 0x72                          # byte: 1 = re-aim at the lock-on target (needs head camera)
AIMMIN2, AIMMAX2, AIMCOS, AIMWMIN, ONE, EPS, BETA, GAMMA = D + 0xA0, D + 0xA4, D + 0xA8, D + 0xAC, D + 0xB0, D + 0xB4, D + 0xB8, D + 0xBC
FPSFOV, TPFOV = D + 0x80, D + 0x84     # FOV multipliers (as radians per degree) used while the head camera is on / off; the cave copies the active one into the Wide-FOV constant every frame
PADTOG, PADPREV, FRAME, PADLAST = D + 0x75, D + 0x76, D + 0x78, D + 0x7C   # touchpad double-click toggle: enable flag, last state, frame counter, frame of the last rising edge
GOT_PAD, GOT_PAD2, PAD_FN_OFF, PAD_FN2_OFF, PAD_RING_OFF = 0x57E5B30, 0x57E4E90, 0xA30, 0x13C0, 0x28BDC   # game import slot -> libScePad function (offset 0xa30 in the module); pad report ring = module base + 0x28bdc, 12 entries x 0xe0, buttons dword first
DEADF, DALPHA, DEPS, HA, FS, US = D + 0x74, D + 0x140, D + 0x144, D + 0x148, D + 0x150, D + 0x160
SLOWON, TSCALE, SLOWMIN, SLOWHOLD, SLOWG, DCNT = D + 0x77, D + 0x178, D + 0x17C, D + 0x180, D + 0x184, D + 0x188   # death slow motion: flag, global character time scale (read by the CAVE_TS hook), scale while dying, frames to hold it, easing factor, frames since death
FASTMAX, FASTEND = D + 0x18C, D + 0x190          # after the slow part the time scale rushes to FASTMAX until FASTEND frames after the death (the death sequence, and the YOU DIED text, run on game time)
DFLOOR, DFLR = D + 0x170, D + 0x174     # death camera: lowest camera height above the feet (const), and that floor in world y for this frame   # death camera: dead flag (HP <= 0), smoothing alpha, epsilon, head matrix address of this frame, smoothed forward / up
TR, TU, FPREV = D + 0x118, D + 0x11C, D + 0x120     # camera-space aim offset; last frame's game forward row (16 B)
DECAY, MOTCOS, TINY = D + 0x130, D + 0x134, D + 0x138
MASKXYZ, MASKRAND, SIGNZ, SIGNALL = D + 0xC0, D + 0xD0, D + 0xE0, D + 0xF0
LASTH, LASTO = D + 0x40, D + 0x50      # latched head (array value) and the model origin of the frame the array last changed
G_WCM = 0x593E878                      # WorldChrMan global; player ChrIns = [[G_WCM]+0x60]
VT_MOD, VT_POSE, VT_W = 0x579CF10, 0x57A0820, 0x5770610   # vtables of [pl+0x48], [[pl+0x48]+0x18], [pl+0x58]
VT_A, HOSTA = 0x57A2AC0, 0x10000                                 # [mod+0x10]: the animation object that hosts the pose holders in some sessions (flag bit in the holder id)
VT_SLOT, VT_X = 0x5735D70, 0x57356F0                        # vtables of [pl+0x3b0] and the physics body X = [[pl+0x3b0]+0x68] (position at X+0x1e0)
# ---- caves and hooks --------------------------------------------------------------------------
CAVE_EPI, CAVE_CAST, CAVE_MGR, CAVE_TS = 0x54A0780, 0x54A1100, 0x54A1600, 0x54A1140
HOOK_TS, BACK_TS, ORIG_TS = 0x1E196BB, 0x1E196C4, bytes.fromhex("c4c17a108574030000")       # vmovss xmm0,[r13+0x374]: the character's speed factor (1.0) that multiplies its time step; r13 = [[chr+0x3b0]+0x30]
HOOK_EPI, BACK_EPI, ORIG_EPI = 0x183F77B, 0x183F782, bytes.fromhex("4881c4d8030000")          # add rsp, 0x3d8
HOOK_CAST, BACK_CAST, ORIG_CAST = 0x1C090E0, 0x1C090E6, bytes.fromhex("554889e54157")          # push rbp; mov rbp,rsp; push r15
HOOK_MGR, BACK_MGR, ORIG_MGR = 0x1836C54, 0x1836C59, bytes.fromhex("c5f8295b40")               # vmovaps [rbx+0x40], xmm3
RAX, RCX, RDX = 0, 1, 2

def ld(dst, base, disp): return bytes([0x48, 0x8b, 0x40 | (dst << 3) | base, disp])        # mov dst,[base+disp8]
def chk(A, reg, label):                                                                    # rsi = scratch; jump to label unless reg is a plausible game-heap pointer
    A.raw(b"\x48\x89" + bytes([0xC0 | (reg << 3) | 6]))                                      # mov rsi,reg
    A.raw(b"\x48\xc1\xee\x20"); A.raw(b"\x48\x83\xee\x02"); A.raw(b"\x48\x83\xfe\x01"); A.jcc("a", label)   # shr rsi,32 ; sub rsi,2 ; cmp rsi,1 ; ja label     high dword 2..3: every game-heap pointer ever seen is in 0x2_0000_0000..0x3_FFFF_FFFF
    A.raw(b"\x89" + bytes([0xC0 | (reg << 3) | 6]))                                          # mov esi,reg32
    A.raw(b"\x81\xfe\x00\x00\x01\x00"); A.jcc("b", label)                                    # cmp esi,0x10000 ; jb label        a tiny low dword means two packed integers (0x5_0000_0000, 0x1_0000_0003), not a pointer
def vx(op, dst, s1, s2): return bytes([0xC5, 0x80 | ((~s1 & 0xF) << 3), op, 0xC0 | (dst << 3) | s2])           # VEX.128 packed-single op xmm_dst = xmm_s1 op xmm_s2 (0x58 add, 0x59 mul, 0x5c sub, 0x5e div; 0x51 sqrt and 0x28 mov take s1 = 0)
def vins(dst, s1, s2, imm): return bytes([0xC4, 0xE3, 0x01 | ((~s1 & 0xF) << 3), 0x21, 0xC0 | (dst << 3) | s2, imm])   # vinsertps
def vdp(dst, s1, s2, imm): return bytes([0xC4, 0xE3, 0x01 | ((~s1 & 0xF) << 3), 0x40, 0xC0 | (dst << 3) | s2, imm])    # vdpps
def vshuf(dst, s1, s2, imm): return bytes([0xC5, 0x80 | ((~s1 & 0xF) << 3), 0xC6, 0xC0 | (dst << 3) | s2, imm])        # vshufps
def vt(A, reg, vtable, label):                                                             # cmp qword [reg],vtable ; jne label
    A.raw(b"\x48\x81" + bytes([0x38 | reg]) + struct.pack("<I", vtable)); A.jcc("ne", label)
def walk(A, label, want_w=False):
    """rax = [G_WCM] -> player ChrIns; rcx = pose object ([[pl+0x48]+0x18]); optional rdx = [pl+0x58] (module container).  All validated, else jump to label."""
    A.rip(b"\x48\x8b\x05", G_WCM); chk(A, RAX, label)
    A.raw(ld(RAX, RAX, 0x60)); chk(A, RAX, label)                                           # rax = player ChrIns
    A.raw(ld(RCX, RAX, 0x48)); chk(A, RCX, label); vt(A, RCX, VT_MOD, label)               # rcx = model container
    A.raw(ld(RCX, RCX, 0x18)); chk(A, RCX, label); vt(A, RCX, VT_POSE, label)               # rcx = pose object
    if want_w: A.raw(ld(RDX, RAX, 0x58)); chk(A, RDX, label); vt(A, RDX, VT_W, label)       # rdx = module container (model->world rows at +0x320..)

def build_epilogue():
    A = Asm(CAVE_EPI)
    A.rip(b"\x80\x3d", FACE2, b"\x00"); A.jcc("e", "orig")                                  # cmp byte [FACE2],0 ; je orig
    A.rip(b"\x80\x3d", MODE, b"\x00"); A.jcc("e", "orig")                                   # cmp byte [MODE],0 ; je orig     only while the head camera is on (third person keeps the normal body)
    A.rip(b"\x80\x3d", DEADF, b"\x00"); A.jcc("ne", "orig")                                # cmp byte [DEADF],0 ; jne orig   not while dead: the displayed body must match the bone matrices the death camera follows
    A.raw(b"\x50\x51\x52\x56")                                                              # push rax, rcx, rdx, rsi
    walk(A, "pop", want_w=True)
    A.raw(vld(0, 2, 0x340)); A.raw(vld(1, 2, 0x348))                                       # xmm0 = R2.x, xmm1 = R2.z
    A.raw(b"\xc4\xc1\x7a\x10\x55\x10"); A.raw(b"\xc4\xc1\x7a\x10\x5d\x18")                 # xmm2 = rx ([r13+0x10]), xmm3 = rz ([r13+0x18]); r13 = follow camera
    A.raw(vss(0x59, 4, 0, 3)); A.raw(vss(0x59, 5, 1, 2)); A.raw(vss(0x5c, 4, 4, 5))        # xmm4 = cos = R2x*rz - R2z*rx
    A.raw(vss(0x59, 5, 1, 3)); A.raw(vss(0x59, 6, 0, 2)); A.raw(vss(0x58, 5, 5, 6))        # xmm5 = sin = R2z*rz + R2x*rx
    A.raw(vss(0x59, 6, 4, 4)); A.raw(vss(0x59, 7, 5, 5)); A.raw(vss(0x58, 6, 6, 7))        # xmm6 = cos^2 + sin^2  (1.0 for sane rows; ~0 for zeroed/garbage camera or model rows)
    A.rip(b"\xc5\xf8\x2e\x35", MINN); A.jcc("b", "pop")                                    # vucomiss xmm6,[MINN] ; jb pop  (below MINN or NaN: do not touch the matrices)
    for xo, zo in ((0x340, 0x348), (0x320, 0x328)):                                         # rotate R2 then R0: x' = x*cos + z*sin ; z' = z*cos - x*sin
        A.raw(vld(0, 2, xo)); A.raw(vld(1, 2, zo))
        A.raw(vss(0x59, 6, 0, 4)); A.raw(vss(0x59, 7, 1, 5)); A.raw(vss(0x58, 6, 6, 7))
        A.raw(vss(0x59, 7, 1, 4)); A.raw(vss(0x59, 2, 0, 5)); A.raw(vss(0x5c, 7, 7, 2))
        A.raw(vst(6, 2, xo)); A.raw(vst(7, 2, zo))
    A.bind("pop"); A.raw(b"\x5e\x5a\x59\x58")                                               # pop rsi, rdx, rcx, rax
    A.bind("orig"); A.raw(ORIG_EPI); A.jmp_abs(BACK_EPI); return A.done()

def build_cast():
    A = Asm(CAVE_CAST)
    A.rip(b"\x80\x3d", NOCOLL, b"\x00"); A.jcc("e", "orig")
    A.raw(b"\x31\xc0\xc3")                                                                  # xor eax,eax ; ret   (no collision hit)
    A.bind("orig"); A.raw(ORIG_CAST); A.jmp_abs(BACK_CAST); return A.done()

def build_ts():
    A = Asm(CAVE_TS)
    A.raw(ORIG_TS)                                                                          # vmovss xmm0,[r13+0x374]
    A.rip(b"\xc5\xfa\x59\x05", TSCALE)                                                      # vmulss xmm0,xmm0,[TSCALE]     every character's time step is scaled (1.0 normally)
    A.jmp_abs(BACK_TS); return A.done()

def build_mgr():
    A = Asm(CAVE_MGR)
    # ---- pad: double-click of the touchpad toggles MODE (the game's personal-effects menu opens/closes with the clicks).  The libScePad base is derived from a game import slot; the report ring
    # (12 DualSense reports, newest overwrites oldest) is OR-ed so any press of the last ~50 ms is seen.  Runs before the MODE test, so it also works while the head camera is off. ----
    A.raw(b"\x50\x51\x52\x56")                                                              # push rax, rcx, rdx, rsi
    A.rip(b"\x80\x3d", PADTOG, b"\x00"); A.jcc("e", "padend")                                 # cmp byte [PADTOG],0 ; je padend
    A.rip(b"\x48\x8b\x05", GOT_PAD)                                                         # rax = [import slot] = address of a libScePad function
    A.raw(b"\x48\x89\xc6"); A.raw(b"\x48\xc1\xee\x20"); A.raw(b"\x48\x83\xfe\x08"); A.jcc("ne", "padend")   # mov rsi,rax ; shr rsi,32 ; cmp rsi,8 ; jne padend   (unresolved/foreign: stop)
    # NEVER read the library's code to verify it: system libraries are execute-only (XOM), a read faults and kills the game.  Only the game's own data is used: the page offset of the function
    # and the distance to a second import slot must match the known module layout.
    A.raw(b"\x89\xc6"); A.raw(b"\x81\xe6\xff\x0f\x00\x00"); A.raw(b"\x81\xfe" + struct.pack("<i", PAD_FN_OFF)); A.jcc("ne", "padend")   # mov esi,eax ; and esi,0xfff ; cmp esi,0xa30 ; jne padend
    A.rip(b"\x48\x8b\x0d", GOT_PAD2); A.raw(b"\x48\x29\xc1"); A.raw(b"\x48\x81\xf9" + struct.pack("<i", PAD_FN2_OFF - PAD_FN_OFF)); A.jcc("ne", "padend")   # rcx = [slot2] - [slot1] must be 0x990
    A.raw(b"\x48\x8d\x88" + struct.pack("<i", PAD_RING_OFF - PAD_FN_OFF))                    # lea rcx,[rax + ring - function offset]
    A.raw(b"\x31\xd2"); A.raw(b"\xbe\x0c\x00\x00\x00")                                      # xor edx,edx ; mov esi,12
    A.bind("padloop"); A.raw(b"\x0b\x11"); A.raw(b"\x48\x81\xc1\xe0\x00\x00\x00"); A.raw(b"\xff\xce"); A.jcc("ne", "padloop")   # or edx,[rcx] ; add rcx,0xe0 ; dec esi ; jnz padloop
    A.rip(b"\xff\x05", FRAME)                                                               # inc dword [FRAME]
    A.raw(b"\xc1\xea\x14"); A.raw(b"\x83\xe2\x01")                                          # shr edx,20 ; and edx,1      touchpad button (0x100000)
    A.rip(b"\x0f\xb6\x35", PADPREV); A.rip(b"\x88\x15", PADPREV)                             # movzx esi,[PADPREV] ; mov [PADPREV],dl
    A.raw(b"\x85\xd2"); A.jcc("e", "padend"); A.raw(b"\x85\xf6"); A.jcc("ne", "padend")       # not pressed, or still held from the last frame
    A.rip(b"\x8b\x05", FRAME); A.raw(b"\x89\xc6"); A.rip(b"\x2b\x05", PADLAST); A.rip(b"\x89\x35", PADLAST)   # eax = FRAME - [PADLAST] ; [PADLAST] = FRAME
    A.raw(b"\x83\xf8\x1e"); A.jcc("a", "padend")                                            # cmp eax,30 ; ja padend     (first click of a pair)
    A.rip(b"\x80\x35", MODE, b"\x01"); A.rip(b"\xc7\x05", PADLAST, struct.pack("<I", 0))     # xor byte [MODE],1 ; mov dword [PADLAST],0     second click within 0.5 s: toggle
    A.bind("padend"); A.raw(b"\x5e\x5a\x59\x58")                                            # pop rsi, rdx, rcx, rax
    # ---- FOV sync: the Wide-FOV constant follows MODE (third person / first person), so the FPS view can be wider than the normal camera ----
    A.raw(b"\x50")                                                                         # push rax
    A.rip(b"\x0f\xb6\x05", MODE); A.raw(b"\x85\xc0")                                         # movzx eax,[MODE] ; test eax,eax
    A.rip(b"\x8b\x05", TPFOV); A.jcc("e", "fovset"); A.rip(b"\x8b\x05", FPSFOV)             # eax = TPFOV ; if MODE: eax = FPSFOV
    A.bind("fovset"); A.rip(b"\x89\x05", FOVC); A.raw(b"\x58")                              # mov [FOVC],eax ; pop rax
    A.rip(b"\x80\x3d", MODE, b"\x00"); A.jcc("e", "modeoff")
    A.raw(b"\x50\x51\x52\x56"); A.raw(b"\x41\x50\x41\x51")                                  # push rax, rcx, rdx, rsi, r8, r9
    A.rip(b"\x48\x8b\x05", G_WCM); chk(A, RAX, "pop")
    A.raw(ld(RAX, RAX, 0x60)); chk(A, RAX, "pop")                                           # rax = player ChrIns
    A.raw(ld(RCX, RAX, 0x48)); chk(A, RCX, "pop"); vt(A, RCX, VT_MOD, "pop")               # rcx = model container
    A.raw(b"\x49\x89\xc8")                                                                  # mov r8,rcx   r8 = model container; the pose holders hang off it
    A.raw(b"\x48\x8b\x90\xb0\x03\x00\x00"); chk(A, RDX, "pop"); vt(A, RDX, VT_SLOT, "pop")   # rdx = [pl+0x3b0]
    A.raw(ld(RAX, RDX, 0x20)); chk(A, RAX, "nohp")                                          # rax = [[pl+0x3b0]+0x20]: the status object whose +0xf8 is the player's HP (the same path before and after a respawn)
    A.raw(b"\x83\xb8\xf8\x00\x00\x00\x00"); A.rip(b"\x0f\x9e\x05", DEADF); A.jmp("hpdone")   # cmp dword [rax+0xf8],0 ; setle [DEADF]     dead = HP <= 0
    A.bind("nohp"); A.rip(b"\xc6\x05", DEADF, b"\x00")                                      # mov byte [DEADF],0
    A.bind("hpdone")
    # ---- death slow motion (flag SLOWON): TSCALE eases (SLOWG per frame) to SLOWMIN while the player is dead and fewer than SLOWHOLD frames have passed since the death, else to 1.0.  The factor is applied by the CAVE_TS hook
    # to every character's time step.  DCNT counts manager frames (real time, unaffected by the slow motion). ----
    A.rip(b"\x80\x3d", SLOWON, b"\x00"); A.jcc("e", "tsone")                                 # cmp byte [SLOWON],0 ; je tsone
    A.rip(b"\x80\x3d", DEADF, b"\x00"); A.jcc("e", "tsalive")                                # cmp byte [DEADF],0 ; je tsalive
    A.rip(b"\x8b\x05", DCNT); A.raw(b"\xff\xc0"); A.rip(b"\x89\x05", DCNT)                    # mov eax,[DCNT] ; inc eax ; mov [DCNT],eax
    A.rip(b"\x3b\x05", SLOWHOLD); A.jcc("b", "tsslow")                                       # cmp eax,[SLOWHOLD] ; jb tsslow       first SLOWHOLD frames: slow motion
    A.rip(b"\x3b\x05", FASTEND); A.jcc("ae", "tsone")                                        # cmp eax,[FASTEND] ; jae tsone        then until FASTEND: fast forward, afterwards normal time
    A.rip(b"\xc5\xfa\x10\x25", FASTMAX); A.jmp("tsmix")                                       # vmovss xmm4,[FASTMAX]
    A.bind("tsslow"); A.rip(b"\xc5\xfa\x10\x25", SLOWMIN); A.jmp("tsmix")                      # vmovss xmm4,[SLOWMIN] ; target
    A.bind("tsalive"); A.rip(b"\xc7\x05", DCNT, struct.pack("<I", 0))                        # alive: mov dword [DCNT],0
    A.bind("tsone"); A.rip(b"\xc5\xfa\x10\x25", ONE)                                         # vmovss xmm4,[ONE]  target 1.0
    A.bind("tsmix")
    A.rip(b"\xc5\xfa\x10\x2d", TSCALE); A.raw(vss(0x5C, 6, 4, 5)); A.rip(b"\xc5\xca\x59\x35", SLOWG); A.raw(vss(0x58, 5, 5, 6)); A.rip(b"\xc5\xfa\x11\x2d", TSCALE)   # TSCALE += SLOWG*(target-TSCALE)
    A.raw(b"\x48\x8b\x52\x68"); chk(A, RDX, "pop"); vt(A, RDX, VT_X, "pop")                  # rdx = X = [[pl+0x3b0]+0x68]   physics body
    A.raw(b"\xc5\xf8\x10\xba\xe0\x01\x00\x00")                                              # vmovups xmm7,[rdx+0x1e0]   character position (x,y,z,1) = feet; the model matrix [pl+0x58]+0x350 is zero after a respawn
    # The animated bone arrays live in a holder object [mod+HOLD] (0x18, 0x20 or 0x5f8 - it changes with the model build, e.g. after a respawn) at slot offset ARROFF.
    A.rip(b"\x4c\x63\x0d", HOLD); A.call("H"); A.raw(b"\x85\xc0"); A.jcc("e", "ffail")     # fast path: movsxd r9,[HOLD] ; H: rcx = holder
    A.rip(b"\x48\x63\x15", ARROFF); A.call("P"); A.raw(b"\x85\xc0"); A.jcc("ne", "found")  # movsxd rdx,[ARROFF] ; P: head -> xmm4
    A.bind("ffail")
    A.rip(b"\x8b\x05", COOL); A.raw(b"\x85\xc0"); A.jcc("e", "doscan")                     # mov eax,[COOL] ; test ; jz doscan   (a failed scan backs off for 120 frames)
    A.raw(b"\xff\xc8"); A.rip(b"\x89\x05", COOL); A.jmp("nopose")                           # dec eax ; mov [COOL],eax ; fallback head meanwhile
    A.bind("doscan"); A.raw(b"\x41\xb9\x18\x00\x00\x00")                                     # mov r9d,0x18
    A.bind("hloop"); A.call("H"); A.raw(b"\x85\xc0"); A.jcc("e", "hnext")
    A.raw(b"\x31\xd2")                                                                      # xor edx,edx
    A.bind("sloop"); A.call("P"); A.raw(b"\x85\xc0"); A.jcc("ne", "upd")
    A.raw(b"\x83\xc2\x08"); A.raw(b"\x81\xfa\x00\x06\x00\x00"); A.jcc("b", "sloop")      # add edx,8 ; cmp edx,0x600 ; jb sloop
    A.bind("hnext")                                                                         # next holder: 0x18 -> 0x20 -> 0x5f8 (hosted by the model container) -> A+0x460 -> A+0x470 -> A+0x478 (A = [mod+0x10], flag 0x10000)
    for cur, nxt in ((0x18, 0x20), (0x20, 0x5F8), (0x5F8, HOSTA | 0x460), (HOSTA | 0x460, HOSTA | 0x470), (HOSTA | 0x470, HOSTA | 0x478)):
        A.raw(b"\x41\x81\xf9" + struct.pack("<I", cur)); A.jcc("e", "hn%x" % nxt)             # cmp r9d,cur ; je hn<next>
    A.rip(b"\xc7\x05", COOL, struct.pack("<I", 120)); A.jmp("nopose")                      # nothing found: mov dword [COOL],120 ; fallback head
    for nxt in (0x20, 0x5F8, HOSTA | 0x460, HOSTA | 0x470, HOSTA | 0x478):
        A.bind("hn%x" % nxt); A.raw(b"\x41\xb9" + struct.pack("<I", nxt)); A.jmp("hloop")      # mov r9d,next ; jmp hloop
    A.bind("upd"); A.rip(b"\x89\x15", ARROFF); A.rip(b"\x44\x89\x0d", HOLD)                  # mov [ARROFF],edx ; mov [HOLD],r9d   remember the working holder/slot
    A.bind("found")
    # The pose arrays are re-evaluated at 30 Hz in some maps (Yharnam) while the model origin and the camera run at 60 Hz.  Latch (head, origin) whenever the array value changes and
    # use  origin(now) + (head - origin)@latch  : movement stays 60 Hz, the animated head offset (bobbing) updates at the animation rate.  With a 60 Hz pose this equals head(now).
    A.rip(b"\xc5\xf8\x10\x2d", LASTH); A.raw(b"\xc5\xd8\xc2\xf5\x00")                         # vmovups xmm5,[LASTH] ; vcmpeqps xmm6,xmm4,xmm5
    A.raw(b"\xc5\xf8\x50\xc6"); A.raw(b"\x83\xe0\x07"); A.raw(b"\x83\xf8\x07"); A.jcc("e", "same")   # vmovmskps eax,xmm6 ; and eax,7 ; cmp eax,7 ; je same   (x,y,z all equal: array not re-evaluated)
    A.rip(b"\xc5\xf8\x11\x25", LASTH); A.rip(b"\xc5\xf8\x11\x3d", LASTO)                       # vmovups [LASTH],xmm4 ; vmovups [LASTO],xmm7
    A.bind("same")
    A.rip(b"\xc5\xf8\x10\x25", LASTH); A.rip(b"\xc5\xd8\x5c\x25", LASTO)                       # vmovups xmm4,[LASTH] ; vsubps xmm4,xmm4,[LASTO]     T = animated head offset from the origin
    # smooth it: S += ALPHA*(T-S) every frame (removes the 30 Hz stepping of the bobbing); a jump bigger than sqrt(SNAP2) (first frame, slot change) snaps
    A.rip(b"\xc5\xd8\x5c\x35", OFFS)                                                        # vsubps xmm6,xmm4,[OFFS]        diff = T - S
    A.raw(b"\xc4\xe3\x49\x40\xee\x71")                                                      # vdpps xmm5,xmm6,xmm6,0x71      |diff|^2
    A.rip(b"\xc5\xf8\x2e\x2d", SNAP2); A.jcc("p", "snap"); A.jcc("ae", "snap")             # vucomiss xmm5,[SNAP2] ; NaN or too far -> snap
    A.rip(b"\xc4\xe2\x79\x18\x2d", ALPHA); A.raw(b"\xc5\xc8\x59\xf5")                    # vbroadcastss xmm5,[ALPHA] ; vmulps xmm6,xmm6,xmm5
    A.rip(b"\xc5\xc8\x58\x35", OFFS); A.jmp("smooth")                                        # vaddps xmm6,xmm6,[OFFS]        S' = S + ALPHA*diff
    A.bind("snap"); A.raw(b"\xc5\xf8\x28\xf4")                                                # vmovaps xmm6,xmm4              S' = T
    A.bind("smooth"); A.rip(b"\xc5\xf8\x11\x35", OFFS)                                       # vmovups [OFFS],xmm6
    A.raw(b"\xc5\xc8\x58\xe7")                                                              # vaddps xmm4,xmm6,xmm7          camera = origin(now) + S'
    A.jmp("clamp")
    A.bind("nopose"); A.rip(b"\x48\xc7\x05", HA, struct.pack("<I", 0)); A.rip(b"\xc5\xc0\x58\x25", FALLV)                                       # vaddps xmm4,xmm7,[FALLV]       no pose arrays found: origin + fixed standing head offset (no bobbing)
    A.bind("clamp")
    A.raw(b"\x45\x31\xc9")                                                                # xor r9d,r9d      r9d = 1 when the death camera has built the view rows this frame
    A.rip(b"\x80\x3d", DEADF, b"\x00"); A.jcc("ne", "dead")                                # cmp byte [DEADF],0 ; jne dead
    A.rip(b"\xc5\xf8\x29\x15", FS); A.rip(b"\xc5\xf8\x29\x0d", US)                       # vmovaps [FS],xmm2 ; [US],xmm1   alive: remember the game's forward / up (start of the death-camera smoothing)
    A.raw(b"\xc5\xfa\x16\xef"); A.rip(b"\xc5\xd2\x58\x2d", HMIN)                              # vmovshdup xmm5,xmm7 ; vaddss xmm5,xmm5,[HMIN]   floor = origin.y + HMIN
    A.raw(b"\xc5\xfa\x16\xf4"); A.raw(b"\xc5\xca\x5f\xf5")                                  # vmovshdup xmm6,xmm4 ; vmaxss xmm6,xmm6,xmm5     max(head.y, floor): the camera never dips below walking height (rolls, crouches)
    A.raw(b"\xc4\xe3\x59\x21\xe6\x10")                                                      # vinsertps xmm4,xmm4,xmm6,0x10                  head.y = clamped value
    A.jmp("clamped")
    # ---- DEAD (HP <= 0): no height floor (the head falls to the ground with the body) and the view follows the head bone: forward = matrix column 2, up = column 0 (right = -column 1),
    # eased with S += DALPHA*(T-S) from the game's last view, then orthonormalised: F' = Fs/|Fs|, R' = Us x F' /|.|, U' = F' x R'.  The rows are stored after the LIMIT test below. ----
    A.bind("dead")
    A.rip(b"\x48\x83\x3d", HA, b"\x00"); A.jcc("e", "clamped")                              # cmp qword [HA],0 ; je clamped    no head matrix this frame: keep the game's rows
    A.raw(b"\xc5\xfa\x16\xef"); A.rip(b"\xc5\xd2\x58\x2d", DFLOOR); A.rip(b"\xc5\xfa\x11\x2d", DFLR)   # vmovshdup xmm5,xmm7 ; vaddss xmm5,xmm5,[DFLOOR] ; vmovss [DFLR],xmm5    floor = origin.y + DFLOOR
    A.rip(b"\x48\x8b\x05", HA)                                                              # rax = head matrix (3 rows of 4 floats)
    A.raw(b"\xc5\xf8\x10\x28"); A.raw(b"\xc5\xf8\x10\x70\x10"); A.raw(b"\xc5\xf8\x10\x78\x20")   # vmovups xmm5,[rax] ; xmm6,[rax+0x10] ; xmm7,[rax+0x20]   rows r0 r1 r2
    A.raw(vx(0x28, 2, 0, 5)); A.raw(vins(2, 2, 2, 0x80)); A.raw(vins(2, 2, 6, 0x90)); A.raw(vins(2, 2, 7, 0xA8))   # xmm2 = Fh = (m2, m6, m10, 0)
    A.raw(vx(0x28, 0, 0, 5)); A.raw(vins(0, 0, 6, 0x10)); A.raw(vins(0, 0, 7, 0x28))                              # xmm0 = Uh = (m0, m4, m8, 0)
    A.rip(b"\xc5\xf8\x28\x0d", FS); A.raw(vx(0x5C, 5, 2, 1))                                  # xmm1 = Fs ; xmm5 = Fh - Fs
    A.rip(b"\xc4\xe2\x79\x18\x35", DALPHA); A.raw(vx(0x59, 5, 5, 6)); A.raw(vx(0x58, 1, 1, 5))  # xmm6 = alpha ; xmm5 *= alpha ; xmm1 = Fs' = Fs + alpha*(Fh-Fs)
    A.rip(b"\xc5\xf8\x29\x0d", FS)                                                          # vmovaps [FS],xmm1
    A.rip(b"\xc5\xf8\x28\x3d", US); A.raw(vx(0x5C, 5, 0, 7)); A.raw(vx(0x59, 5, 5, 6)); A.raw(vx(0x58, 7, 7, 5))   # xmm7 = Us' = Us + alpha*(Uh-Us)
    A.rip(b"\xc5\xf8\x29\x3d", US)                                                          # vmovaps [US],xmm7
    A.raw(vdp(5, 1, 1, 0x7F)); A.rip(b"\xc5\xf8\x2e\x2d", DEPS); A.jcc("be", "dfail")           # |Fs|^2 > eps (NaN fails)
    A.raw(vx(0x51, 5, 0, 5)); A.raw(vx(0x5E, 2, 1, 5))                                           # xmm2 = F' = Fs / |Fs|
    A.raw(vshuf(5, 7, 7, 0xC9)); A.raw(vshuf(6, 2, 2, 0xD2)); A.raw(vx(0x59, 5, 5, 6))             # cross(Us, F') = Us.yzx*F'.zxy - Us.zxy*F'.yzx
    A.raw(vshuf(6, 7, 7, 0xD2)); A.raw(vshuf(0, 2, 2, 0xC9)); A.raw(vx(0x59, 6, 6, 0)); A.raw(vx(0x5C, 0, 5, 6))   # xmm0 = R (unnormalised)
    A.raw(vdp(5, 0, 0, 0x7F)); A.rip(b"\xc5\xf8\x2e\x2d", DEPS); A.jcc("be", "dfail")           # |R|^2 > eps
    A.raw(vx(0x51, 5, 0, 5)); A.raw(vx(0x5E, 0, 0, 5))                                           # xmm0 = R' = R / |R|
    A.raw(vshuf(5, 2, 2, 0xC9)); A.raw(vshuf(6, 0, 0, 0xD2)); A.raw(vx(0x59, 5, 5, 6))             # cross(F', R')
    A.raw(vshuf(6, 2, 2, 0xD2)); A.raw(vshuf(1, 0, 0, 0xC9)); A.raw(vx(0x59, 6, 6, 1)); A.raw(vx(0x5C, 1, 5, 6))   # xmm1 = U' = F' x R'
    A.raw(b"\x41\xb9\x01\x00\x00\x00"); A.jmp("clamped")                                       # mov r9d,1
    A.bind("dfail")
    A.raw(b"\xc5\xf8\x28\x43\x10"); A.raw(b"\xc5\xf8\x28\x4b\x20"); A.raw(b"\xc5\xf8\x28\x53\x30")   # reload xmm0..xmm2 = the game's rows
    A.bind("clamped")
    A.raw(b"\xc4\xe3\x59\x21\xe3\xf0")                                                      # vinsertps xmm4,xmm4,xmm3,0xf0        keep the camera row's w
    for off, reg in ((OFF_R, 0xe8), (OFF_U, 0xe9), (OFF_F, 0xea)):                          # + R*right + U*up + F*forward (camera rows xmm0/xmm1/xmm2)
        A.rip(b"\xc4\xe2\x79\x18\x2d", off); A.raw(b"\xc5\xd0\x59" + bytes([reg])); A.raw(b"\xc5\xd8\x58\xe5")
    A.raw(b"\x45\x85\xc9"); A.jcc("e", "nofloor")                                            # test r9d,r9d ; jz nofloor     death camera only
    A.rip(b"\xc5\xfa\x10\x2d", DFLR); A.raw(b"\xc5\xfa\x16\xf4"); A.raw(b"\xc5\xca\x5f\xf5")   # vmovss xmm5,[DFLR] ; vmovshdup xmm6,xmm4 ; vmaxss xmm6,xmm6,xmm5
    A.raw(b"\xc4\xe3\x59\x21\xe6\x10")                                                      # vinsertps xmm4,xmm4,xmm6,0x10      the camera never sinks into the ground
    A.bind("nofloor")
    A.raw(b"\xc5\xd8\x5c\xeb")                                                              # vsubps xmm5,xmm4,xmm3        head - game camera
    A.raw(b"\xc4\xe3\x51\x40\xed\x71")                                                      # vdpps xmm5,xmm5,xmm5,0x71    squared distance (x,y,z) -> xmm5.x
    A.rip(b"\xc5\xf8\x2e\x2d", LIMIT)                                                       # vucomiss xmm5,[LIMIT]
    A.jcc("p", "pop"); A.jcc("ae", "pop")                                                   # NaN or >= LIMIT: keep the game's camera
    A.raw(b"\xc5\xf8\x28\xdc")                                                              # vmovaps xmm3,xmm4  (new position row)
    # ---- AIM: while the game's lock-on camera is active (a target pointer sits in [mgr+0x110]) look from the head at the lock-on target instead of at the player's pivot ----
    # target world point = [mgr+0x120]; rows right/up/forward = [mgr+0x10/0x20/0x30] = xmm0/xmm1/xmm2, R x U = F.  The aim is stored as a CAMERA-SPACE offset (TR, TU) of the game's forward:
    #   view forward = normalize(F + TR*R + TU*U).  Locked on: (TR,TU) eases to the value that points at the target.  After the release it simply STAYS (the game's view does not drag the camera back);
    #   it only fades while the user turns the camera (the game's forward moves faster than MOTCOS per frame), where the change is hidden by the motion.
    A.raw(b"\x45\x85\xc9"); A.jcc("e", "aimgate")                                           # test r9d,r9d ; jz aimgate
    A.raw(b"\xc5\xf8\x29\x43\x10"); A.raw(b"\xc5\xf8\x29\x4b\x20"); A.raw(b"\xc5\xf8\x29\x53\x30")   # death camera: vmovaps [rbx+0x10],xmm0 ; [rbx+0x20],xmm1 ; [rbx+0x30],xmm2   (right, up, forward)
    A.jmp("pop")
    A.bind("aimgate")
    A.rip(b"\x80\x3d", AIM, b"\x00"); A.jcc("e", "pop")
    A.raw(b"\x48\x8b\x83\x10\x01\x00\x00"); chk(A, RAX, "nolock")                            # rax = [rbx+0x110]  target pointer (zero when not locked on)
    A.raw(b"\xc5\xf8\x10\xb3\x20\x01\x00\x00")                                              # vmovups xmm6,[rbx+0x120]  lock point (x,y,z,1)
    A.raw(b"\xc5\xc8\x5c\xf3")                                                              # vsubps xmm6,xmm6,xmm3     D = target - camera
    A.raw(b"\xc4\xe3\x49\x40\xfe\x71")                                                      # vdpps xmm7,xmm6,xmm6,0x71 |D|^2
    A.rip(b"\xc5\xf8\x2e\x3d", AIMMIN2); A.jcc("be", "nolock")                                 # |D|^2 <= AIMMIN2 (or NaN)
    A.rip(b"\xc5\xf8\x2e\x3d", AIMMAX2); A.jcc("ae", "nolock")                                 # |D|^2 >= AIMMAX2
    A.raw(b"\xc5\xc2\x51\xff"); A.raw(b"\xc5\xc0\xc6\xff\x00"); A.raw(b"\xc5\xc8\x5e\xf7")   # vsqrtss xmm7 ; vshufps xmm7,xmm7,xmm7,0 ; vdivps xmm6,xmm6,xmm7   F' = D/|D|
    A.raw(b"\xc4\xe3\x49\x40\xfa\x71")                                                      # vdpps xmm7,xmm6,xmm2,0x71 cf = F'.F
    A.rip(b"\xc5\xf8\x2e\x3d", AIMCOS); A.jcc("b", "nolock")                                   # cf < AIMCOS (or NaN): wrong target
    A.raw(b"\xc4\xe3\x49\x40\xe8\x71"); A.raw(b"\xc5\xd2\x5e\xef")                          # vdpps xmm5,xmm6,xmm0,0x71 ; vdivss xmm5,xmm5,xmm7     target TR = (F'.R)/cf
    A.raw(b"\xc4\xe3\x49\x40\xe1\x71"); A.raw(b"\xc5\xda\x5e\xe7")                          # vdpps xmm4,xmm6,xmm1,0x71 ; vdivss xmm4,xmm4,xmm7     target TU = (F'.U)/cf
    A.rip(b"\xc5\xd2\x5c\x2d", TR); A.rip(b"\xc5\xd2\x59\x2d", BETA); A.rip(b"\xc5\xd2\x58\x2d", TR); A.rip(b"\xc5\xfa\x11\x2d", TR)    # TR += BETA*(target - TR)
    A.rip(b"\xc5\xda\x5c\x25", TU); A.rip(b"\xc5\xda\x59\x25", BETA); A.rip(b"\xc5\xda\x58\x25", TU); A.rip(b"\xc5\xfa\x11\x25", TU)    # TU += BETA*(target - TU)
    A.jmp("apply")
    A.bind("nolock")
    A.rip(b"\xc5\xf8\x10\x3d", FPREV); A.raw(b"\xc4\xe3\x41\x40\xfa\x71")                    # vmovups xmm7,[FPREV] ; vdpps xmm7,xmm7,xmm2,0x71   cos between this and the last frame's game forward
    A.rip(b"\xc5\xf8\x2e\x3d", MOTCOS); A.jcc("p", "apply"); A.jcc("ae", "apply")           # not turning (cos >= MOTCOS) or NaN: keep the offset
    A.rip(b"\xc5\xfa\x10\x2d", TR); A.rip(b"\xc5\xd2\x59\x2d", DECAY); A.rip(b"\xc5\xfa\x11\x2d", TR)    # the user is turning the camera: TR *= DECAY
    A.rip(b"\xc5\xfa\x10\x25", TU); A.rip(b"\xc5\xda\x59\x25", DECAY); A.rip(b"\xc5\xfa\x11\x25", TU)    # TU *= DECAY
    A.bind("apply")
    A.rip(b"\xc5\xf8\x11\x15", FPREV)                                                       # vmovups [FPREV],xmm2   remember the game's forward
    A.rip(b"\xc5\xfa\x10\x2d", TR); A.raw(b"\xc5\xd2\x59\xed"); A.rip(b"\xc5\xfa\x10\x25", TU); A.raw(b"\xc5\xda\x59\xe4"); A.raw(b"\xc5\xd2\x58\xec")   # xmm5 = TR^2 + TU^2
    A.rip(b"\xc5\xf8\x2e\x2d", TINY); A.jcc("be", "pop")                                      # no offset: the game's view
    A.rip(b"\xc4\xe2\x79\x18\x2d", TR); A.raw(b"\xc5\xd0\x59\xe8")                          # vbroadcastss xmm5,[TR] ; vmulps xmm5,xmm5,xmm0
    A.rip(b"\xc4\xe2\x79\x18\x25", TU); A.raw(b"\xc5\xd8\x59\xe1")                          # vbroadcastss xmm4,[TU] ; vmulps xmm4,xmm4,xmm1
    A.raw(b"\xc5\xd0\x58\xec"); A.raw(b"\xc5\xd0\x58\xf2")                                 # vaddps xmm5,xmm5,xmm4 ; vaddps xmm6,xmm5,xmm2     F + TR*R + TU*U
    A.raw(b"\xc4\xe3\x49\x40\xfe\x71"); A.raw(b"\xc5\xc2\x51\xff"); A.raw(b"\xc5\xc0\xc6\xff\x00"); A.raw(b"\xc5\xc8\x5e\xf7")   # normalise Fb
    A.raw(b"\xc5\xc8\x59\xfe")                                                              # vmulps xmm7,xmm6,xmm6
    A.raw(b"\xc5\xc0\x12\xef"); A.raw(b"\xc5\xc2\x58\xed")                                 # vmovhlps xmm5,xmm7,xmm7 ; vaddss xmm5,xmm7,xmm5   h^2 = Fx^2 + Fz^2
    A.rip(b"\xc5\xf8\x2e\x2d", EPS); A.jcc("be", "pop")                                        # looking straight up/down: keep the game's view
    A.raw(b"\xc5\xd2\x51\xed")                                                              # vsqrtss xmm5,xmm5,xmm5    h
    A.rip(b"\xc5\xfa\x10\x3d", ONE); A.raw(b"\xc5\xc2\x5e\xfd"); A.raw(b"\xc5\xc0\xc6\xff\x00")   # vmovss xmm7,[ONE] ; vdivss xmm7,xmm7,xmm5 ; vshufps xmm7,xmm7,xmm7,0   1/h
    A.raw(b"\xc5\xc8\x59\xff")                                                              # vmulps xmm7,xmm6,xmm7     V = Fb/h
    A.raw(b"\xc4\xe3\x79\x04\xe7\xc2")                                                      # vpermilps xmm4,xmm7,0xc2  (Vz, Vx, Vx, Vw)
    A.rip(b"\xc5\xd8\x54\x25", MASKRAND); A.rip(b"\xc5\xd8\x57\x25", SIGNZ)               # vandps xmm4,xmm4,[(1,0,1,0)] ; vxorps xmm4,xmm4,[(0,0,-0,0)]     right = (Vz, 0, -Vx, 0)
    A.raw(b"\xc4\xe3\x79\x04\xc7\x55")                                                      # vpermilps xmm0,xmm7,0x55  (Vy x4)
    A.raw(b"\xc5\xf8\x59\xc6"); A.rip(b"\xc5\xf8\x57\x05", SIGNALL)                       # vmulps xmm0,xmm0,xmm6 ; vxorps xmm0,xmm0,[-0 x4]    (-Vy*Fx, -Vy*Fy, -Vy*Fz)
    A.raw(b"\xc4\xe3\x79\x21\xc5\x10"); A.rip(b"\xc5\xf8\x54\x05", MASKXYZ)              # vinsertps xmm0,xmm0,xmm5,0x10 (y = h) ; vandps xmm0,xmm0,[xyz mask]     up = (-Fy*Fx/h, h, -Fy*Fz/h, 0)
    A.rip(b"\xc5\xc8\x54\x35", MASKXYZ)                                                     # vandps xmm6,xmm6,[xyz mask]     forward (w = 0)
    A.raw(b"\xc5\xf8\x29\x63\x10"); A.raw(b"\xc5\xf8\x29\x43\x20"); A.raw(b"\xc5\xf8\x29\x73\x30")   # vmovaps [rbx+0x10],xmm4 ; [rbx+0x20],xmm0 ; [rbx+0x30],xmm6
    A.raw(b"\xc5\xf8\x28\x43\x10"); A.raw(b"\xc5\xf8\x28\x4b\x20"); A.raw(b"\xc5\xf8\x28\x53\x30")   # reload xmm0..xmm2 = the new rows
    A.bind("pop"); A.raw(b"\x41\x59\x41\x58"); A.raw(b"\x5e\x5a\x59\x58")                  # pop r9, r8, rsi, rdx, rcx, rax
    A.bind("orig"); A.raw(ORIG_MGR); A.jmp_abs(BACK_MGR)
    A.bind("modeoff"); A.rip(b"\xc7\x05", TSCALE, struct.pack("<f", 1.0)); A.rip(b"\xc7\x05", DCNT, struct.pack("<I", 0)); A.jmp("orig")   # head camera off: normal time, then the original instruction
    # ---- H: rcx = [r8+r9] (holder object), validated.  eax = 1 / 0 ----
    A.bind("H")                                                                             # r9d = holder offset (| HOSTA: the host is A = [mod+0x10] instead of the model container r8)
    A.raw(b"\x4c\x89\xc1")                                                                # mov rcx,r8
    A.raw(b"\x41\xf7\xc1" + struct.pack("<I", HOSTA)); A.jcc("e", "hdirect")                # test r9d,HOSTA ; jz hdirect
    A.raw(b"\x49\x8b\x48\x10"); chk(A, RCX, "hfail"); vt(A, RCX, VT_A, "hfail")           # mov rcx,[r8+0x10] ; A must have its vtable
    A.bind("hdirect")
    A.raw(b"\x44\x89\xc8"); A.raw(b"\x25\xff\xff\x00\x00")                              # mov eax,r9d ; and eax,0xffff
    A.raw(b"\x3d\x00\x07\x00\x00"); A.jcc("a", "hfail")                                     # cmp eax,0x700 ; ja hfail
    A.raw(b"\x48\x8b\x0c\x01"); chk(A, RCX, "hfail")                                         # mov rcx,[rcx+rax]
    A.raw(b"\xb8\x01\x00\x00\x00\xc3")                                                       # mov eax,1 ; ret
    A.bind("hfail"); A.raw(b"\x31\xc0\xc3")                                                   # xor eax,eax ; ret
    # ---- P: is [rcx+rdx] a pointer to the animated world-space bone matrices?  rcx = holder object, rdx = slot offset, xmm7 = model origin.  eax = 1 (head in xmm4) / 0 ----
    A.bind("P")
    A.raw(b"\x81\xfa\x00\x07\x00\x00"); A.jcc("a", "fail")                                   # cmp edx,0x700 ; ja fail   (also rejects negative)
    A.raw(b"\x48\x8b\x04\x11"); A.raw(b"\xa8\x0f"); A.jcc("ne", "fail"); chk(A, RAX, "fail")  # rax = [rcx+rdx] ; test al,0xf ; jnz fail  (the arrays are 16-byte aligned)
    A.rip(b"\x48\x63\x35", BONEOFF); A.raw(b"\x48\x01\xf0")                                 # movsxd rsi,[BONEOFF] ; add rax,rsi   -> head bone matrix
    A.raw(b"\xc5\xfa\x10\x60\x0c")                                                          # vmovss xmm4,[rax+0x0c]            tx
    A.raw(b"\xc4\xe3\x59\x21\x60\x1c\x10")                                                  # vinsertps xmm4,xmm4,[rax+0x1c],0x10  ty
    A.raw(b"\xc4\xe3\x59\x21\x60\x2c\x20")                                                  # vinsertps xmm4,xmm4,[rax+0x2c],0x20  tz
    A.raw(b"\xc5\xd8\x5c\xef")                                                              # vsubps xmm5,xmm4,xmm7        head - origin
    A.raw(b"\xc5\xfa\x16\xf5")                                                              # vmovshdup xmm6,xmm5          y
    A.rip(b"\xc5\xf8\x2e\x35", YMIN); A.jcc("be", "fail")                                   # y <= YMIN (or NaN) -> not a head
    A.rip(b"\xc5\xf8\x2e\x35", YMAX); A.jcc("ae", "fail")                                   # y >= YMAX -> not a head
    A.raw(b"\xc5\xd0\x59\xf5")                                                              # vmulps xmm6,xmm5,xmm5
    A.raw(b"\xc5\xc8\x12\xee")                                                              # vmovhlps xmm5,xmm6,xmm6      z^2
    A.raw(b"\xc5\xca\x58\xf5")                                                              # vaddss xmm6,xmm6,xmm5        x^2 + z^2
    A.rip(b"\xc5\xf8\x2e\x35", R2); A.jcc("ae", "fail")                                     # horizontal distance >= sqrt(R2) -> not this player's head
    A.rip(b"\x48\x89\x05", HA)                                                           # mov [HA],rax     the head matrix (the death camera reads its rotation)
    A.raw(b"\xb8\x01\x00\x00\x00\xc3")                                                       # mov eax,1 ; ret
    A.bind("fail"); A.raw(b"\x31\xc0\xc3")                                                   # xor eax,eax ; ret
    return A.done()

AIMCONST = AIMMIN2
def aimconst():
    return (struct.pack("<8f", 0.09, 3600.0, 0.3, 0.05, 1.0, 1e-6, 0.3, 0.35) + struct.pack("<4I", 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0) + struct.pack("<4I", 0xFFFFFFFF, 0, 0xFFFFFFFF, 0)
            + struct.pack("<4I", 0, 0, 0x80000000, 0) + struct.pack("<4I", 0x80000000, 0x80000000, 0x80000000, 0x80000000))      # 96 bytes at D+0xA0

def entry(addr, on, off=b""): return {"offset": "%08X" % addr, "on": on.hex(), "off": off.hex(), "absolute": True}

def build(r=0.0, u=0.17, f=0.32, bone=68, limit=100.0, minn=0.5, ymin=-0.5, ymax=2.4, r2=2.25, hmin=1.25, snap2=1.0, alpha=0.5, fallh=1.53, fps_fov=1.5, tp_fov=1.3, slow_min=0.10, slow_hold=75, slow_g=0.15, fast_max=3.0, fast_end=240):
    # Tunables are written in three pieces on purpose: ARROFF (D+0x14), COOL (D+0x2C) and HOLD (D+0x3C) are the cave's own cached state (working pose holder/slot, scan back-off).  They start at
    # zero (cave memory is zeroed), are maintained by the cave and must NOT be rewritten when the cheat is toggled in a running game - a reset would force a full memory scan in the live process.
    cfg_a = struct.pack("<ifff", bone * 0x30, r, u, f)                                       # D+0x04: BONEOFF, R, U, F
    cfg_b = struct.pack("<fffff", limit, minn, ymin, ymax, r2)                               # D+0x18: LIMIT, MINN, YMIN, YMAX, R2
    cfg_c = struct.pack("<fff", hmin, snap2, alpha)                                          # D+0x30: HMIN, SNAP2, ALPHA
    core = {"name": "FPS head camera (experimental)", "type": "checkbox", "enabled": True, "memory": [
        entry(BONEOFF, cfg_a), entry(LIMIT, cfg_b), entry(HMIN, cfg_c), entry(FPSFOV, struct.pack("<ff", math.pi / 180.0 * fps_fov, math.pi / 180.0 * tp_fov)), entry(PADTOG, b"\x01", b"\x00"), entry(AIMCONST, aimconst()), entry(TR, struct.pack("<2f", 0.0, 0.0)), entry(DECAY, struct.pack("<3f", 0.97, 0.99998, 1e-6)), entry(DALPHA, struct.pack("<2f", 0.2, 1e-4)), entry(DFLOOR, struct.pack("<f", 0.30)), entry(FALLV, struct.pack("<4f", 0.0, fallh, 0.0, 0.0)), entry(NOCOLL, b"\x01", b"\x00"), entry(CAVE_EPI, build_epilogue()), entry(CAVE_CAST, build_cast()), entry(CAVE_MGR, build_mgr()),
        entry(HOOK_EPI, hook(HOOK_EPI, CAVE_EPI, 7), ORIG_EPI), entry(HOOK_CAST, hook(HOOK_CAST, CAVE_CAST, 6), ORIG_CAST), entry(HOOK_MGR, hook5(HOOK_MGR, CAVE_MGR), ORIG_MGR),
        entry(MODE, b"\x01", b"\x00")]}                                                      # MODE last: switches the camera override on
    face = {"name": "FPS head camera: body faces the view (needs head camera)", "type": "checkbox", "enabled": True, "memory": [entry(FACE2, b"\x01", b"\x00")]}
    aim = {"name": "FPS head camera: aim at the lock-on target (needs head camera)", "type": "checkbox", "enabled": True, "memory": [entry(AIM, b"\x01", b"\x00")]}
    slow = {"name": "FPS head camera: death slow motion (needs head camera)", "type": "checkbox", "enabled": True, "memory": [
        entry(TSCALE, struct.pack("<ffIf", 1.0, slow_min, slow_hold, slow_g)), entry(FASTMAX, struct.pack("<fI", fast_max, fast_end)), entry(CAVE_TS, build_ts()), entry(HOOK_TS, hook(HOOK_TS, CAVE_TS, 9), ORIG_TS),
        entry(SLOWON, b"\x01", b"\x00")]}                                                      # flag last
    return [core, face, aim, slow]

if __name__ == "__main__":
    a = sys.argv
    val = lambda k, d: float(a[a.index(k) + 1]) if k in a else d
    print(json.dumps(build(val("--r", 0.0), val("--u", 0.17), val("--f", 0.32), int(val("--bone", 68))), indent=1))
