import sys, struct
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg
d=Dbg(); pid=[p for p in d.proc_list() if p[0]=="eboot.bin"][-1][1]
B=0x59406e0
F={0x18c:"DonotPassOverFocus",0x190:"FocusSensitivity",0x194:"FocusSpeedLimit",0x198:"FocusDelay",0x19c:"FocusDistanceRangeMin",0x1a0:"FocusDistanceRangeMax",0x1a4:"FocusScreenPositionX",
 0x1b0:"DofFocusDistance",0x1b4:"ApertuerF",0x1b8:"DofAdaptiveApertureFactor",0x1bc:"DofAdaptiveApertureBaseFov",0x1c0:"CCD-Size",0x1c4:"DofRotateScale",0x1c8:"DofRotateOffsetInRadians",0x1cc:"DiaphragmRotate",
 0x1d0:"ApertureFrontNumLevels",0x1d4:"ApertureBackNumLevels",0x1d8:"BackgroundMaskThreshold",0x240:"DofEdgeQuality",
 0x2d4:"Enable-Near-Custom",0x2d8:"Enable-Far-Custom",0x2dc:"DofNearDepthStart",0x2e0:"DofNearDepthEnd",0x2e4:"DofNear CocSize",0x2e8:"DofNear CocScale",
 0x2ec:"DofFarDepthStart",0x2f0:"DofFarDepthEnd",0x2f4:"DofFar CocSize",0x2f8:"DofFar CocScale",0x2fc:"DofFar DistanceThreshold"}
raw=d.proc_read(pid,B+0x180,0x180)
for o,n in sorted(F.items()):
    w=struct.unpack_from("<I",raw,o-0x180)[0]; f=struct.unpack_from("<f",raw,o-0x180)[0]
    print("+%03x %-28s %08x  int=%-11d float=%g"%(o,n,w,w if w<2**31 else w-2**32,f))
print("--- enables used by apply func: +1dc,+1e0,+200,+208,+20c")
for o in (0x1dc,0x1e0,0x1ec,0x1f0,0x200,0x204,0x208,0x20c,0x214,0x218,0x220):
    w=struct.unpack_from("<I",raw,o-0x180)[0]; print("+%03x %08x float=%g"%(o,w,struct.unpack_from("<f",raw,o-0x180)[0]))
