# -*- coding: utf-8 -*-
"""进程内存读取/扫描/写入工具（Windows，ctypes 实现，免安装版内存分析器）。

用途：直接读游戏进程内部数据（资源、日期、弹窗状态），不再依赖截图。
子命令：
  selftest                             - 自检（起一个测试进程，扫描/写入全链路验证）
  info    <进程名|pid>                 - 列出可读写内存区域
  scan    <进程名|pid> --int 1234      - 全内存扫描数值（默认只扫可写区）
  filter  <进程名|pid> --int 5678      - 在上次扫描的命中集里过滤（换数值后再缩小范围）
  read    <进程名|pid> 0xADDR          - 读内存（十六进制 + 按类型解释）
  write   <进程名|pid> 0xADDR --int N  - 写内存（危险操作，需 --yes）
"""
import argparse
import ctypes
import json
import struct
import sys
import time
from pathlib import Path

import psutil

sys.stdout.reconfigure(encoding="utf-8")

k32 = ctypes.windll.kernel32
k32.OpenProcess.restype = ctypes.c_void_p
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.ReadProcessMemory.restype = ctypes.c_int
k32.WriteProcessMemory.restype = ctypes.c_int

PROCESS_ALL = 0x1F0FFF
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
READABLE = {PAGE_READONLY, PAGE_READWRITE, PAGE_WRITECOPY,
            PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY}
WRITABLE = {PAGE_READWRITE, PAGE_WRITECOPY, PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY}

STATE_FILE = Path(__file__).resolve().parent / "_scan.json"


def _state_file(name="scan"):
    return Path(__file__).resolve().parent / f"_scan_{name}.json"


class MBI64(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_ulonglong), ("AllocationBase", ctypes.c_ulonglong),
                ("AllocationProtect", ctypes.c_ulong), ("__pad1", ctypes.c_ulong),
                ("RegionSize", ctypes.c_ulonglong),
                ("State", ctypes.c_ulong), ("Protect", ctypes.c_ulong),
                ("Type", ctypes.c_ulong), ("__pad2", ctypes.c_ulong)]


def open_proc(name_or_pid):
    s = str(name_or_pid)
    if s.isdigit():
        pid = int(s)
    else:
        target = s.lower()
        pid = None
        for p in psutil.process_iter(["pid", "name"]):
            nm = (p.info["name"] or "").lower()
            if nm == target or nm == target + ".exe" or (target in nm and nm.endswith(".exe")):
                pid = p.info["pid"]
                break
        if pid is None:
            raise SystemExit(f"找不到进程: {name_or_pid}")
    h = k32.OpenProcess(PROCESS_ALL, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess 失败 pid={pid} err={k32.GetLastError()}（可能权限不足）")
    return h, pid


def regions(h, writable_only=False):
    out = []
    addr = 0
    mbi = MBI64()
    sz = ctypes.sizeof(mbi)
    while addr < 0x7FFFFFFFFFFF:
        r = k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), sz)
        if r != sz:
            addr += 0x1000
            continue
        base, rsize, state, prot = mbi.BaseAddress, mbi.RegionSize, mbi.State, mbi.Protect
        if state == MEM_COMMIT and not (prot & PAGE_GUARD):
            p = prot & 0xFF
            if (p in WRITABLE) if writable_only else (p in (READABLE | WRITABLE)):
                out.append((base, rsize, prot))
        addr = base + max(rsize, 0x1000)
    return out


def read_mem(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    n = ctypes.c_size_t(0)
    if k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(n)):
        return buf.raw[:n.value]
    return None


def write_mem(h, addr, data):
    n = ctypes.c_size_t(0)
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(addr), data, len(data), ctypes.byref(n))
    return bool(ok) and n.value == len(data)


def make_pattern(iv=None, iv16=None, fv=None, dv=None, sv=None, hx=None):
    if hx:
        return bytes.fromhex(hx.replace(" ", "")), "hex:" + hx.replace(" ", ""), hx
    if iv is not None:
        return struct.pack("<i", iv), "int32", iv
    if iv16 is not None:
        return struct.pack("<h", iv16), "int16", iv16
    if fv is not None:
        return struct.pack("<f", fv), "float32", fv
    if dv is not None:
        return struct.pack("<d", dv), "float64", dv
    if sv is not None:
        return sv.encode("utf-8"), "str", sv
    raise SystemExit("需要 --int / --float / --double / --str 之一")


def scan_pattern(h, pattern, writable_only=True, limit=200000):
    hits = []
    scanned = 0
    for base, rsize, prot in regions(h, writable_only=writable_only):
        data = read_mem(h, base, rsize)
        scanned += rsize
        if not data:
            continue
        start = 0
        while True:
            i = data.find(pattern, start)
            if i < 0:
                break
            hits.append(base + i)
            start = i + 1
            if len(hits) >= limit:
                return hits, scanned
    return hits, scanned


def scan_float_range(h, lo, hi, dtype="double", writable_only=True, limit=200000):
    """扫描落在 [lo, hi] 区间内的 float64(dtype=double) / float32(dtype=float) 值。"""
    import numpy as np
    hits = []
    scanned = 0
    width = 8 if dtype == "double" else 4
    npdt = np.float64 if dtype == "double" else np.float32
    for base, rsize, prot in regions(h, writable_only=writable_only):
        data = read_mem(h, base, rsize)
        scanned += rsize
        if not data:
            continue
        n = len(data) // width
        if n == 0:
            continue
        arr = np.frombuffer(data[:n * width], dtype=npdt)
        with np.errstate(invalid="ignore"):
            mask = (arr >= lo) & (arr <= hi) & np.isfinite(arr)
        for i in np.where(mask)[0]:
            hits.append(base + int(i) * width)
            if len(hits) >= limit:
                return hits, scanned
    return hits, scanned


def cmd_info(proc):
    h, pid = open_proc(proc)
    regs = regions(h, writable_only=False)
    total = sum(r[1] for r in regs)
    wtotal = sum(r[1] for r in regions(h, writable_only=True))
    print(f"pid={pid}  可读区域 {len(regs)} 个 / {total/2**20:.0f}MB；其中可写 {wtotal/2**20:.0f}MB")
    for base, rsize, prot in regs[:15]:
        print(f"  {hex(base):>18}  {rsize/2**20:8.1f}MB  prot=0x{prot:02x}")
    if len(regs) > 15:
        print(f"  ...（其余 {len(regs)-15} 个略）")


def cmd_scan(proc, pattern, vtype, value, writable_only=True, save="scan"):
    h, pid = open_proc(proc)
    t0 = time.time()
    if vtype == "double-range":
        lo, hi = value
        hits, scanned = scan_float_range(h, lo, hi, "double", writable_only)
    elif vtype == "float-range":
        lo, hi = value
        hits, scanned = scan_float_range(h, lo, hi, "float", writable_only)
    else:
        hits, scanned = scan_pattern(h, pattern, writable_only=writable_only)
    _state_file(save).write_text(json.dumps(
        {"pid": pid, "type": vtype, "value": value, "hits": hits[:5000]}, ensure_ascii=False), encoding="utf-8")
    print(f"扫描 {scanned/2**20:.0f}MB 用时 {time.time()-t0:.1f}s，命中 {len(hits)} 处（已存 {min(len(hits),5000)} 个到 _scan_{save}.json）")
    for a in hits[:12]:
        print(f"  {hex(a)}")
    if len(hits) > 12:
        print(f"  ...共 {len(hits)} 处")


def cmd_filter(proc, pattern, vtype, value, save="scan"):
    sf = _state_file(save)
    if not sf.exists():
        raise SystemExit(f"没有 _scan_{save}.json，先跑 scan")
    st = json.loads(sf.read_text(encoding="utf-8"))
    h, pid = open_proc(proc)
    keep = []
    for a in st["hits"]:
        data = read_mem(h, a, len(pattern))
        if data == pattern:
            keep.append(a)
    st2 = {"pid": pid, "type": vtype, "value": value, "hits": keep}
    sf.write_text(json.dumps(st2, ensure_ascii=False), encoding="utf-8")
    print(f"过滤后剩 {len(keep)} 处：")
    for a in keep[:20]:
        print(f"  {hex(a)}")
    if not keep:
        print("  （0 处：可能数值还没变化/进程重启过，回到 scan 重来）")


def cmd_read(proc, addr, size, vtype):
    h, pid = open_proc(proc)
    data = read_mem(h, addr, size)
    if data is None:
        raise SystemExit("读取失败")
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        print(f"{hex(addr+off):>18}  {hexs:<48}")
    if vtype == "int32" and len(data) >= 4:
        print("int32 :", struct.unpack("<i", data[:4])[0])
    elif vtype == "int64" and len(data) >= 8:
        print("int64 :", struct.unpack("<q", data[:8])[0])
    elif vtype == "float32" and len(data) >= 4:
        print("float :", struct.unpack("<f", data[:4])[0])
    elif vtype == "double" and len(data) >= 8:
        print("double:", struct.unpack("<d", data[:8])[0])
    elif vtype == "str":
        print("str   :", data.split(b"\x00")[0].decode("utf-8", errors="replace"))


def cmd_write(proc, addr, pattern, confirmed):
    if not confirmed:
        raise SystemExit("写入是危险操作（可能让游戏崩溃），请加 --yes 确认")
    h, pid = open_proc(proc)
    ok = write_mem(h, addr, pattern)
    print("写入", "成功" if ok else "失败", hex(addr), pattern.hex())


def cmd_selftest():
    import subprocess
    child_code = (
        "import ctypes,sys,threading,time\n"
        "v=ctypes.c_int32(987654321)\n"
        "def rd():\n"
        "    for line in sys.stdin:\n"
        "        if line.strip()=='?':\n"
        "            print(f'VALUE {v.value}',flush=True)\n"
        "threading.Thread(target=rd,daemon=True).start()\n"
        "while True: time.sleep(0.05)\n")
    # venv 的 python.exe 是转发启动器：真正解释器是它的子进程，这里直接找基础解释器
    exe = getattr(sys, "_base_executable", None) or sys.executable
    child = subprocess.Popen([exe, "-c", child_code],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    time.sleep(1.2)
    ok = False
    try:
        pid = child.pid
        try:
            kids = psutil.Process(child.pid).children(recursive=True)
            if kids:
                pid = kids[0].pid
        except Exception:
            pass
        h, pid = open_proc(str(pid))
        hits, scanned = scan_pattern(h, struct.pack("<i", 987654321), writable_only=True)
        print(f"自检：扫描 {scanned/2**20:.0f}MB，命中 {len(hits)} 处")
        for a in hits[:60]:
            write_mem(h, a, struct.pack("<i", 424242))
            child.stdin.write("?\n")
            child.stdin.flush()
            line = child.stdout.readline().strip()
            if line == "VALUE 424242":
                print(f"读写验证成功：{hex(a)}（正确命中测试进程变量）")
                ok = True
                break
            write_mem(h, a, struct.pack("<i", 987654321))
    finally:
        child.kill()
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def cmd_ptr(proc, target, depth=3, near=0x800, save="ptr"):
    """从目标地址出发向上找指针链，直到出现模块静态区内的指针（= 可固化路径）。"""
    import numpy as np
    h, pid = open_proc(proc)
    modules = []
    try:
        for mm in psutil.Process(pid).memory_maps(grouped=False):
            try:
                a, b = [int(x, 16) for x in mm.addr.split("-")]
            except Exception:
                continue
            modules.append((a, b, mm.path))
    except Exception:
        pass

    def describe(addr):
        for a, b, p in modules:
            if a <= addr < b and p and p != "[anon]":
                try:
                    return p.split("\\")[-1]
                except Exception:
                    return p
        return "私有内存"

    def is_static(addr):
        return 0x140000000 <= addr < 0x143800000

    def scan_edges(front, radius):
        lo = max(0, min(front) - radius)
        hi = max(front) + radius
        fset = sorted(set(front))
        edges = []
        for base, rsize, prot in regions(h, writable_only=False):
            data = read_mem(h, base, rsize)
            if not data:
                continue
            n = len(data) // 8
            if n == 0:
                continue
            arr = np.frombuffer(data[:n * 8], dtype=np.uint64)
            idx = np.where((arr >= lo) & (arr <= hi))[0]
            for i in idx:
                v = int(arr[i])
                for t in fset:
                    if abs(v - t) <= radius:
                        edges.append((base + int(i) * 8, v, t))
                        break
            if len(edges) >= 500:
                break
        return edges

    front = [target]
    levels = []
    for d in range(1, depth + 1):
        edges = scan_edges(front, near)
        print(f"-- 第 {d} 层：{len(edges)} 个指针指向上一层候选 --")
        statics = [(hd, v, t) for (hd, v, t) in edges if is_static(hd)]
        for (hd, v, t) in edges[:25]:
            tag = "★静态区" if is_static(hd) else describe(hd)
            print(f"   [{tag}] 0x{hd:X} -> 0x{v:X}   (目标 0x{t:X}, 偏移 {t - v:+d})")
        if statics:
            print(f"★★ 第 {d} 层出现 {len(statics)} 个静态区指针：固化路径成形")
        levels.append([[hd, v, t] for (hd, v, t) in edges])
        front = list({hd for (hd, v, t) in edges if not is_static(hd)})[:200]
        if not front:
            print("（已到顶：没有更多指针指向这些位置）")
            break
    out = _state_file(save)
    out.write_text(json.dumps({"target": target, "levels": levels}, ensure_ascii=False), encoding="utf-8")
    print("已存:", out)


def cmd_probe(proc, value):
    """对同一个小数按多种编码假设做一次全内存扫描，找出它到底怎么存的。"""
    import struct
    h, pid = open_proc(proc)
    pats = {}
    for scale, tag in ((1.0, ""), (0.001, "/1000"), (1000.0, "*1000")):
        val = value * scale
        try:
            pats[f"f32{tag}"] = struct.pack("<f", val)
        except Exception:
            pass
        try:
            pats[f"f64{tag}"] = struct.pack("<d", val)
        except Exception:
            pass
    for scale, tag in ((1, "int"), (100, "x100"), (1000, "x1000"), (100000, "x1e5")):
        iv = int(round(value * scale))
        if -2**31 <= iv < 2**31:
            pats[f"i32_{tag}"] = struct.pack("<i", iv)
        if -2**63 <= iv < 2**63:
            pats[f"i64_{tag}"] = struct.pack("<q", iv)
    pats["str"] = f"{value}".encode()
    results = {k: [] for k in pats}
    scanned = 0
    for base, rsize, prot in regions(h, writable_only=True):
        data = read_mem(h, base, rsize)
        if not data:
            continue
        scanned += rsize
        for name, pat in pats.items():
            if len(results[name]) >= 30:
                continue
            start = 0
            while len(results[name]) < 30:
                i = data.find(pat, start)
                if i < 0:
                    break
                results[name].append(base + i)
                start = i + 1
    print(f"目标值 {value} 的多编码探测（扫描 {scanned/2**20:.0f}MB）：")
    any_hit = False
    for name, hits in results.items():
        if hits:
            any_hit = True
            print(f"  {name}: {len(hits)} 处 -> {[hex(x) for x in hits[:6]]}")
    if not any_hit:
        print("  所有编码假设均 0 命中")


def main():
    ap = argparse.ArgumentParser(description="进程内存工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info")
    p.add_argument("proc")

    p = sub.add_parser("scan")
    p.add_argument("proc")
    p.add_argument("--int", dest="iv", type=int)
    p.add_argument("--int16", dest="iv16", type=int)
    p.add_argument("--float", dest="fv", type=float)
    p.add_argument("--double", dest="dv", type=float)
    p.add_argument("--str", dest="sv")
    p.add_argument("--hex", dest="hx", help="原始字节模式（十六进制，如 b1080a02）")
    p.add_argument("--dmin", type=float)
    p.add_argument("--dmax", type=float)
    p.add_argument("--fmin", type=float)
    p.add_argument("--fmax", type=float)
    p.add_argument("--all", action="store_true", help="连只读内存一起扫（更慢）")
    p.add_argument("--save", default="scan", help="命中集另存名（默认 scan）")

    p = sub.add_parser("filter")
    p.add_argument("proc")
    p.add_argument("--int", dest="iv", type=int)
    p.add_argument("--int16", dest="iv16", type=int)
    p.add_argument("--float", dest="fv", type=float)
    p.add_argument("--double", dest="dv", type=float)
    p.add_argument("--str", dest="sv")
    p.add_argument("--hex", dest="hx", help="原始字节模式（十六进制）")
    p.add_argument("--save", default="scan", help="使用哪份命中集（默认 scan）")

    p = sub.add_parser("read")
    p.add_argument("proc")
    p.add_argument("addr")
    p.add_argument("--size", type=int, default=64)
    p.add_argument("--type", dest="vt", default=None)

    p = sub.add_parser("write")
    p.add_argument("proc")
    p.add_argument("addr")
    p.add_argument("--int", dest="iv", type=int)
    p.add_argument("--float", dest="fv", type=float)
    p.add_argument("--yes", action="store_true")

    sub.add_parser("selftest")

    p = sub.add_parser("ptr")
    p.add_argument("proc")
    p.add_argument("target", help="目标地址（0x...）")
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--near", default="0x800", help="允许的偏移范围（十六进制）")
    p.add_argument("--save", default="ptr")

    p = sub.add_parser("probe")
    p.add_argument("proc")
    p.add_argument("value", type=float)

    a = ap.parse_args()
    if a.cmd == "selftest":
        sys.exit(cmd_selftest())
    if a.cmd == "ptr":
        cmd_ptr(a.proc, int(a.target, 0), a.depth, int(a.near, 0), a.save)
        return
    if a.cmd == "probe":
        cmd_probe(a.proc, a.value)
        return
    if a.cmd == "info":
        cmd_info(a.proc)
        return
    if a.cmd == "scan":
        if getattr(a, "dmin", None) is not None and getattr(a, "dmax", None) is not None:
            cmd_scan(a.proc, None, "double-range", (a.dmin, a.dmax),
                     writable_only=not a.all, save=a.save)
        elif getattr(a, "fmin", None) is not None and getattr(a, "fmax", None) is not None:
            cmd_scan(a.proc, None, "float-range", (a.fmin, a.fmax),
                     writable_only=not a.all, save=a.save)
        else:
            pattern, vtype, value = make_pattern(a.iv, a.iv16, a.fv, a.dv, a.sv, a.hx)
            cmd_scan(a.proc, pattern, vtype, value, writable_only=not a.all, save=a.save)
        return
    if a.cmd == "filter":
        pattern, vtype, value = make_pattern(a.iv, a.iv16, a.fv, a.dv,
                                             getattr(a, "sv", None), getattr(a, "hx", None))
        cmd_filter(a.proc, pattern, vtype, value, save=a.save)
        return
    if a.cmd == "read":
        cmd_read(a.proc, int(a.addr, 0), a.size, a.vt)
        return
    if a.cmd == "write":
        pattern, vtype, value = make_pattern(a.iv, a.fv, None, None)
        cmd_write(a.proc, int(a.addr, 0), pattern, a.yes)
        return


if __name__ == "__main__":
    main()
