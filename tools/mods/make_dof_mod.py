#!/usr/bin/env python3
"""No depth of field: the scene post-effect apply function calls SetDepthOfFieldEnable(flag) every frame, where flag = (scene DOF enable != 0) (`setne al`, 0f 95 c0 at 0x25d7a8b).
Replacing it with `xor eax,eax; nop` (31 c0 90) passes false every time.  Also disables DOF in cutscenes.  Effect is subtle in gameplay."""
import json
def build():
    return {"name": "No depth of field", "type": "checkbox", "enabled": False, "memory": [
        {"offset": "025D7A8B", "on": "31c090", "off": "0f95c0", "absolute": True}]}
if __name__ == "__main__": print(json.dumps(build(), indent=1))
