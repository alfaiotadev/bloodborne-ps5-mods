#!/usr/bin/env python3
"""Minimal ps5debug client (TCP, port 744 by default).

Written from scratch for these tools; it only implements what the scripts in tools/dev need.

Environment
  PS5_HOST         console address (required, no default)
  PS5_DEBUG_PORT   ps5debug port (default 744)

Wire format
  request : magic 0xFFAABBCC (u32 LE), opcode (u32 LE), body length (u32 LE), body
  reply   : u32 status first (0x80000000 = success, 0xF0000001 = error, 0xF0000003 = bad data / unknown
            command), then command specific data

Opcodes used
  0xBDAA0001 process list   reply: u32 count, then count x 36 bytes (32-byte NUL padded name + i32 pid)
  0xBDAA0002 read           body: u32 pid, u64 addr, u32 length   reply: status, raw bytes
  0xBDAA0003 write          body: u32 pid, u64 addr, u32 length   after status success send the raw data,
                            then read a second u32 status
  0xBDAA0004 maps           body: u32 pid   reply: u32 count, then count x 58 bytes
                            (32-byte name, u64 start, u64 end, u64 offset, u16 prot)
  0xBDAA0007 ELF / dump     body: u32 pid, u32 length
  0xBDAA000A process info   body: u32 pid
  0xBDBB0001 debugger attach (body u32 pid), 0xBDBB0002 detach, 0xBDBB0010 stop/go (body u32 0 = go)

After a debugger attach the console connects back to the client on TCP 755 and sends 864-byte
interrupt packets (see parse_interrupt()).

Usage as a script:  PS5_HOST=<ip> python3 ps5dbg.py   (prints the process list)
"""
import os
import socket
import struct

MAGIC = 0xFFAABBCC
CMD_SUCCESS_WIRE = 0x80000000
CMD_ERROR_WIRE = 0xF0000001
CMD_BAD_DATA_WIRE = 0xF0000003            # bad data / unknown command

CMD_PROC_LIST = 0xBDAA0001
CMD_PROC_READ = 0xBDAA0002
CMD_PROC_WRITE = 0xBDAA0003
CMD_PROC_MAPS = 0xBDAA0004
CMD_PROC_ELF = 0xBDAA0007
CMD_PROC_INFO = 0xBDAA000A
CMD_DEBUG_ATTACH = 0xBDBB0001
CMD_DEBUG_DETACH = 0xBDBB0002
CMD_DEBUG_STOPGO = 0xBDBB0010

DEBUG_CALLBACK_PORT = 755                 # the console connects back to us here after an attach
INTERRUPT_PACKET_SIZE = 864
INTERRUPT_REGS = ["r15", "r14", "r13", "r12", "r11", "r10", "r9", "r8", "rdi", "rsi", "rbp", "rbx", "rdx", "rcx", "rax"]


class Ps5DebugError(IOError):
    pass


def _host():
    try:
        return os.environ["PS5_HOST"]
    except KeyError:
        raise SystemExit("PS5_HOST is not set (export PS5_HOST=<console ip address>)")


class Dbg:
    def __init__(self, host=None, port=None):
        host = host or _host()
        port = int(port or os.environ.get("PS5_DEBUG_PORT", "744"))
        self.s = socket.create_connection((host, port), timeout=15)
        self.s.settimeout(120)

    def close(self):
        self.s.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _recvn(self, n):
        b = b""
        while len(b) < n:
            c = self.s.recv(n - len(b))
            if not c:
                raise IOError("conn closed")
            b += c
        return b

    def _recv_upto(self, n, timeout):
        """Read up to n bytes, stopping early when nothing arrives for `timeout` seconds."""
        old = self.s.gettimeout()
        self.s.settimeout(timeout)
        b = b""
        try:
            while len(b) < n:
                c = self.s.recv(n - len(b))
                if not c:
                    break
                b += c
        except socket.timeout:
            pass
        finally:
            self.s.settimeout(old)
        return b

    def cmd(self, op, body=b""):
        """Send one command, return the u32 status word of the reply (reply data, if any, is still unread)."""
        self.s.sendall(struct.pack("<III", MAGIC, op, len(body)) + body)
        st = struct.unpack("<I", self._recvn(4))[0]
        return st

    # ---- process commands -------------------------------------------------------------------
    def proc_list(self):
        st = self.cmd(CMD_PROC_LIST)
        assert st == CMD_SUCCESS_WIRE, hex(st)
        n = struct.unpack("<I", self._recvn(4))[0]
        out = []
        for _ in range(n):
            e = self._recvn(36)
            out.append((e[:32].split(b"\0")[0].decode("utf-8", "replace"),
                        struct.unpack("<i", e[32:])[0]))
        return out

    def proc_maps(self, pid):
        st = self.cmd(CMD_PROC_MAPS, struct.pack("<I", pid))
        assert st == CMD_SUCCESS_WIRE, hex(st)
        n = struct.unpack("<I", self._recvn(4))[0]
        out = []
        for _ in range(n):
            e = self._recvn(58)
            name = e[:32].split(b"\0")[0].decode("utf-8", "replace")
            start, end, off = struct.unpack("<QQQ", e[32:56])
            prot = struct.unpack("<H", e[56:])[0]
            out.append((name, start, end, off, prot))
        return out

    def proc_read(self, pid, addr, length):
        """Read `length` bytes; returns None when the range is not readable."""
        st = self.cmd(CMD_PROC_READ, struct.pack("<IQI", pid, addr, length))
        if st != CMD_SUCCESS_WIRE:
            return None
        return self._recvn(length)

    def proc_write(self, pid, addr, data):
        """Write `data` (one atomic request); raises Ps5DebugError on failure, returns len(data)."""
        st = self.cmd(CMD_PROC_WRITE, struct.pack("<IQI", pid, addr, len(data)))
        if st != CMD_SUCCESS_WIRE:
            raise Ps5DebugError("write %#x (%d bytes) refused: status %#x" % (addr, len(data), st))
        self.s.sendall(data)
        st2 = struct.unpack("<I", self._recvn(4))[0]
        if st2 != CMD_SUCCESS_WIRE:
            raise Ps5DebugError("write %#x (%d bytes) failed: status %#x" % (addr, len(data), st2))
        return len(data)

    def proc_elf(self, pid, length):
        st = self.cmd(CMD_PROC_ELF, struct.pack("<II", pid, length))
        if st != CMD_SUCCESS_WIRE:
            return None
        data = self._recvn(length)
        st2 = struct.unpack("<I", self._recvn(4))[0]
        return data, st2

    def proc_info(self, pid, length=188):
        """Raw process-info reply (None on error status). The layout is not decoded here: a ps4debug-style
        reply is u32 pid, char name[40], char path[64], char titleid[16], char contentid[64] (188 bytes);
        this is unverified on ps5debug, so whatever arrives (up to `length` bytes) is returned as-is."""
        st = self.cmd(CMD_PROC_INFO, struct.pack("<I", pid))
        if st != CMD_SUCCESS_WIRE:
            return None
        return self._recv_upto(length, 2.0)

    # ---- debugger commands ------------------------------------------------------------------
    # Use a separate Dbg connection for these (see crash_catch.py): the console connects back to
    # TCP DEBUG_CALLBACK_PORT of this machine and streams interrupt packets there.
    def debug_attach(self, pid):
        return self.cmd(CMD_DEBUG_ATTACH, struct.pack("<I", pid))

    def debug_detach(self):
        return self.cmd(CMD_DEBUG_DETACH)

    def debug_go(self):
        return self.cmd(CMD_DEBUG_STOPGO, struct.pack("<I", 0))


def parse_interrupt(pkt):
    """Decode one 864-byte debugger interrupt packet into a dict."""
    lwpid, status = struct.unpack_from("<II", pkt, 0)
    name = pkt[8:48].split(b"\0")[0].decode("latin1")
    regs = dict(zip(INTERRUPT_REGS, struct.unpack_from("<15Q", pkt, 48)))
    trapno, fs, gs = struct.unpack_from("<IHH", pkt, 48 + 120)
    err, es, ds = struct.unpack_from("<IHH", pkt, 48 + 128)
    rip, cs, rflags, rsp, ss = struct.unpack_from("<5Q", pkt, 48 + 136)
    regs.update(trapno=trapno, fs=fs, gs=gs, err=err, es=es, ds=ds, rip=rip, cs=cs, rflags=rflags, rsp=rsp, ss=ss)
    return {"lwpid": lwpid, "status": status, "tdname": name, "regs": regs}


if __name__ == "__main__":
    d = Dbg()
    for name, pid in d.proc_list():
        print(f"{pid:6d}  {name}")
