"""crash_catch.py - wait for the game, attach the ps4debug-style debugger, log every stop; on a fatal signal print regs + context and leave the process stopped."""
import sys, socket, struct, time, threading
import os; sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _d) for _d in ("core", "mods-live")]  # tools/dev bootstrap
from ps5dbg import Dbg, CMD_SUCCESS_WIRE
LOG = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)
SIGNAMES = {4: "SIGILL", 5: "SIGTRAP", 6: "SIGABRT", 8: "SIGFPE", 10: "SIGBUS", 11: "SIGSEGV", 17: "SIGSTOP", 18: "SIGTSTP", 19: "SIGCONT"}
REGS = ["r15", "r14", "r13", "r12", "r11", "r10", "r9", "r8", "rdi", "rsi", "rbp", "rbx", "rdx", "rcx", "rax"]
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("0.0.0.0", 755)); srv.listen(1); LOG("listening on 755")
d = Dbg(); pid = None; t0 = time.time()
while time.time() - t0 < 1500:
    ps = [p for p in d.proc_list() if p[0] == "eboot.bin"]
    if ps and (pid is None or ps[-1][1] != pid):
        pid = ps[-1][1]; LOG("game pid", pid, "- waiting 18 s before attach"); time.sleep(18)
        d2 = Dbg()
        st = d2.cmd(0xBDBB0001, struct.pack("<I", pid)); LOG("attach status %#x" % st)
        srv.settimeout(6)
        try: conn, addr = srv.accept(); LOG("debug socket connected from", addr)
        except Exception as e:
            LOG("no debug connection:", e, "- detaching"); LOG("detach %#x" % d2.cmd(0xBDBB0002)); pid = None; continue
        conn.settimeout(600)
        def recv_pkt():
            buf = b""
            while len(buf) < 864:
                c = conn.recv(864 - len(buf))
                if not c: return None
                buf += c
            return buf
        # initial stop?
        conn.settimeout(3)
        try:
            p = recv_pkt(); LOG("initial packet", None if p is None else (len(p), "status %#x" % struct.unpack_from("<I", p, 4)[0]))
        except Exception as e: LOG("no initial packet:", e)
        LOG("go: %#x" % d2.cmd(0xBDBB0010, struct.pack("<I", 0)))
        conn.settimeout(900)
        while True:
            try: p = recv_pkt()
            except Exception as e: LOG("recv:", e); break
            if p is None: LOG("debug socket closed"); break
            lwp, status = struct.unpack_from("<II", p, 0); name = p[8:48].split(b"\0")[0].decode("latin1")
            sig = (status >> 8) & 0xff if (status & 0xff) == 0x7f else status & 0x7f
            regs = struct.unpack_from("<15Q", p, 48); trapno, = struct.unpack_from("<I", p, 48 + 120); err, = struct.unpack_from("<I", p, 48 + 128)
            rip, cs, rflags, rsp, ss = struct.unpack_from("<5Q", p, 48 + 136)
            LOG("STOP lwp %d (%s) status %#x sig %d %s  rip %#x trapno %d err %#x rsp %#x" % (lwp, name, status, sig, SIGNAMES.get(sig, "?"), rip, trapno, err, rsp))
            if sig in (4, 6, 8, 10, 11):
                LOG("FATAL. regs:", " ".join("%s=%#x" % (n, v) for n, v in zip(REGS, regs)))
                try:
                    code = d.proc_read(pid, rip - 16, 48); LOG("code at rip-16:", code.hex() if code else None)
                    stk = d.proc_read(pid, rsp, 0x80); LOG("stack:", " ".join("%#x" % v for v in struct.unpack("<16Q", stk)) if stk else None)
                except Exception as e: LOG("context read failed:", e)
                LOG("process left stopped; exiting watcher"); sys.exit(0)
            else:
                LOG("non-fatal stop -> continue with signal pass-through"); d2.cmd(0xBDBB0010, struct.pack("<I", 0))
    time.sleep(1)
LOG("timeout")
