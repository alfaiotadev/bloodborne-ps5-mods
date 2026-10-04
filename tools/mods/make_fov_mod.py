#!/usr/bin/env python3
"""Wide-FOV mod (default x1.3 = 43 deg -> 55.9 deg vertical, ~87 deg horizontal at 16:9).

The follow-camera update (0x183ac60) converts the parameter row's FOV (degrees, LOCK_CAM_PARAM_ST +0x14, clamped to 38..48) to radians with
`vmulss xmm1, xmm1, [0x4d25e58]` (pi/180) at 0x183af56.  We redirect that instruction's RIP-relative operand (disp32 at 0x183af5a) to a float constant in a code cave
(= pi/180 * SCALE), so every row's FOV is multiplied and the game's 48 degree cap no longer matters.  Constant first, then the displacement."""
import json, math, struct, sys
CONST_ADDR = 0x54A0500; INSN = 0x183AF56; DISP_ADDR = INSN + 4; NEXT = INSN + 8
ORIG_DISP = struct.pack("<i", 0x4D25E58 - NEXT)
assert ORIG_DISP.hex() == "faae4e03"
def build(scale=1.3):
    return {"name": "Wide FOV x%g" % scale, "type": "checkbox", "enabled": True, "memory": [
        {"offset": "%08X" % CONST_ADDR, "on": struct.pack("<f", math.pi / 180.0 * scale).hex(), "off": "", "absolute": True},
        {"offset": "%08X" % DISP_ADDR, "on": struct.pack("<i", CONST_ADDR - NEXT).hex(), "off": ORIG_DISP.hex(), "absolute": True}]}
if __name__ == "__main__":
    print(json.dumps(build(float(sys.argv[sys.argv.index("--fov-scale") + 1]) if "--fov-scale" in sys.argv else 1.3), indent=1))
