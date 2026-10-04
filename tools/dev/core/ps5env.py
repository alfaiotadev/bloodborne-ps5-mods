"""Shared configuration helpers for the tools in tools/dev.

Environment variables
  PS5_HOST         console address (required by everything that talks to the console, no default)
  PS5_DEBUG_PORT   ps5debug port (default 744)
  PS5_FTP_PORT     FTP server port on the console (default 2121)
  PS5_ELFLDR_PORT  ELF loader port on the console (default 9021)
  PS5_WORKDIR      scratch directory for logs, pickles, scenes.json ... (default ./work, created on demand)
  PS5_NOTIFY_ELF   optional: path to a notify.elf built from tools/dev/notify; enables on-screen toasts
"""
import os
import socket
import subprocess


def host():
    try:
        return os.environ["PS5_HOST"]
    except KeyError:
        raise SystemExit("PS5_HOST is not set (export PS5_HOST=<console ip address>)")


def debug_port():
    return int(os.environ.get("PS5_DEBUG_PORT", "744"))


def ftp_port():
    return int(os.environ.get("PS5_FTP_PORT", "2121"))


def elfldr_port():
    return int(os.environ.get("PS5_ELFLDR_PORT", "9021"))


def workdir():
    d = os.environ.get("PS5_WORKDIR", "work")
    os.makedirs(d, exist_ok=True)
    return d


def workpath(name):
    """Path of a scratch file inside the work directory."""
    return os.path.join(workdir(), name)


def ftp_url(path=""):
    """ftp://<PS5_HOST>:<PS5_FTP_PORT>/<path> (use with curl)."""
    return "ftp://%s:%d/%s" % (host(), ftp_port(), path.lstrip("/"))


def toast(msg):
    """Show `msg` as a PS5 notification (optional, never fatal).
    Needs PS5_NOTIFY_ELF (see tools/dev/notify): the text is uploaded to /data/toast.txt over FTP, then the
    notify payload is sent to the ELF loader, which shows it once. Without PS5_NOTIFY_ELF the message is only printed."""
    elf = os.environ.get("PS5_NOTIFY_ELF")
    if not elf:
        print("[toast]", msg, flush=True)
        return
    try:
        p = workpath("toast.txt")
        open(p, "w", encoding="utf-8").write(msg)
        subprocess.run(["curl", "-m", "10", "-gsS", "-T", p, ftp_url("data/toast.txt")], timeout=15)
        with socket.create_connection((host(), elfldr_port()), timeout=10) as s:
            s.sendall(open(elf, "rb").read())
    except Exception as e:
        print("toast failed:", e, flush=True)
