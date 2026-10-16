# -*- coding: utf-8 -*-
"""内存级控制台指令通道 v2（真·游戏内控制台执行链，2026-10-16 于 Ghidra 逆向确认）。

链路（全部由游戏自己的函数完成，Python 只负责摆参数）：
    FUN_14016b4f0()                     取/建 console 管理器（全局 0x143159360）
    FUN_14015bcf0(wrapper, text, len)   构造输入字符串对象（0x30）
    FUN_14015af40(wrapper, vec, 0x20)   按空格切成参数数组（vec 0x18：+8 数组 +0x14 个数）
    FUN_141b43650(mgr, out, vec, 0)     执行：名字/别名查表 → 调用 handler

用法：
    python console_exec.py --scan                 列出游戏内全部控制台命令（只读）
    python console_exec.py "resource energy x"    干跑：打印将执行什么，不执行
    python console_exec.py --go "resource energy 5000"   真执行

注意：
  - 需游戏在运行；建议在游戏暂停时执行。
  - 执行是"游戏内同款"路径：效果与在控制台里手打该指令一致。
  - 远程线程里调用游戏函数有一定风险（先备份存档；本项目 save_backup/ 已有存档）。
"""
import ctypes
import struct
import sys

import psutil

sys.stdout.reconfigure(encoding="utf-8")

k32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
k32.OpenProcess.restype = ctypes.c_void_p
k32.CreateRemoteThread.restype = ctypes.c_void_p
k32.VirtualAllocEx.restype = ctypes.c_void_p
k32.WaitForSingleObject.restype = ctypes.c_uint32

PROCESS_ALL = 0x1F0FFF
MEM_COMMIT_RESERVE = 0x3000
PAGE_EXECUTE_READWRITE = 0x40
MEM_RELEASE = 0x8000
PREF_BASE = 0x140000000

# —— 逆向得到的函数/全局（stellaris.exe 4.5.2）——
RVA_GET_CONSOLE = 0x14016B4F0   # 取/建 console 管理器
RVA_FROM_CSTR = 0x14015BAA0     # 字符串对象构造（从 C 字符串；cap 初始化 0xF → SSO 合法态）
RVA_SPLIT = 0x14015AF40         # 按分隔符切分成参数数组
RVA_EXEC = 0x141B43650          # 执行命令
RVA_MGR_GLOBAL = 0x143159360    # console 管理器全局指针


def find_game(proc="stellaris"):
    target = proc.lower()
    for p in psutil.process_iter(["pid", "name"]):
        nm = (p.info["name"] or "").lower()
        if nm == target or nm == target + ".exe":
            return p.info["pid"]
    return None


def module_base(h):
    mods = (ctypes.c_void_p * 1024)()
    needed = ctypes.c_uint32(0)
    if not psapi.EnumProcessModules(h, mods, ctypes.sizeof(mods), ctypes.byref(needed)):
        return None
    return int(mods[0])


def rpm(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    n = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(n))
    if not ok:
        return None
    return buf.raw[: n.value]


def read_u64(h, addr):
    b = rpm(h, addr, 8)
    return struct.unpack("<Q", b)[0] if b else None


def read_u32(h, addr):
    b = rpm(h, addr, 4)
    return struct.unpack("<I", b)[0] if b else None


def read_cstr(h, addr, maxlen=96):
    b = rpm(h, addr, maxlen)
    if not b:
        return None
    z = b.find(b"\x00")
    raw = b if z < 0 else b[:z]
    try:
        return raw.decode("utf-8", "replace")
    except Exception:
        return None


def read_wrapper_str(h, addr):
    """0x30 字符串对象：+0x10 起为 data(16B 内联/指针)，+0x20 size，+0x28 cap。"""
    size = read_u64(h, addr + 0x20)
    cap = read_u64(h, addr + 0x28)
    if size is None or cap is None or size > 4096:
        return None, None, None
    if cap > 0xF:
        data_ptr = read_u64(h, addr + 0x10)
        b = rpm(h, data_ptr, size) if data_ptr else None
    else:
        b = rpm(h, addr + 0x10, size)
    s = b.decode("utf-8", "replace") if b else None
    return s, size, cap


def scan_commands(h, base):
    mgr = read_u64(h, base + (RVA_MGR_GLOBAL - PREF_BASE))
    if not mgr:
        print("console 管理器还没创建（先进游戏读个档再试）")
        return
    count = read_u32(h, mgr + 0x14)
    arr = read_u64(h, mgr + 8)
    print(f"console 管理器 = 0x{mgr:X}   命令数 = {count}")
    if not arr or not count or count > 4000:
        print("结构读不出来（偏移可能不对）")
        return
    names = []
    for i in range(count):
        e = arr + i * 0xA8
        name = read_cstr(h, read_u64(h, e + 8) or 0)
        if name:
            names.append(name)
    names = sorted(set(names))
    print(f"（去重后 {len(names)} 个）:")
    for n in names:
        print("  " + n)


def find_command(h, mgr, name):
    count = read_u32(h, mgr + 0x14)
    arr = read_u64(h, mgr + 8)
    if not arr or not count:
        return None, None
    lname = name.lower()
    for i in range(count):
        e = arr + i * 0xA8
        nm = read_cstr(h, read_u64(h, e + 8) or 0)
        if nm and nm.lower() == lname:
            entry = read_u64(h, e + 0x40)
            return e, entry
        n_alias = read_u32(h, e + 0x10) or 0
        for j in range(min(n_alias, 32)):
            aptr = read_u64(h, e + 0x18 + j * 8)
            alias = read_cstr(h, aptr or 0)
            if alias and alias.lower() == lname:
                return e, read_u64(h, e + 0x40)
    return None, None


def build_stub(base, text_addr, text_len, wrapper, vec, out):
    F = lambda rva: base + (rva - PREF_BASE)
    code = bytearray()
    code += b"\x48\x83\xEC\x28"                      # sub rsp,0x28
    code += b"\x48\xB9" + struct.pack("<Q", wrapper) # mov rcx, wrapper
    code += b"\x48\xBA" + struct.pack("<Q", text_addr)  # mov rdx, text
    code += b"\x48\xB8" + struct.pack("<Q", F(RVA_FROM_CSTR))
    code += b"\xFF\xD0"                              # call rax  (string ctor from C str)
    code += b"\x48\xB9" + struct.pack("<Q", wrapper)
    code += b"\x48\xBA" + struct.pack("<Q", vec)
    code += b"\x49\xB8" + struct.pack("<Q", 0x20)
    code += b"\x48\xB8" + struct.pack("<Q", F(RVA_SPLIT))
    code += b"\xFF\xD0"                              # call rax  (split)
    code += b"\x48\xB8" + struct.pack("<Q", F(RVA_GET_CONSOLE))
    code += b"\xFF\xD0"                              # call rax  (get console)
    code += b"\x49\xBA" + struct.pack("<Q", F(RVA_MGR_GLOBAL))
    code += b"\x4D\x8B\x12"                          # mov r10,[r10]  (mgr)
    code += b"\x4C\x89\xD1"                          # mov rcx,r10
    code += b"\x48\xBA" + struct.pack("<Q", out)     # mov rdx, out
    code += b"\x49\xB8" + struct.pack("<Q", vec)     # mov r8, vec
    code += b"\x45\x31\xC9"                          # xor r9d,r9d
    code += b"\x48\xB8" + struct.pack("<Q", F(RVA_EXEC))
    code += b"\xFF\xD0"                              # call rax  (exec)
    code += b"\x48\x83\xC4\x28\xC3"                  # add rsp,0x28; ret
    return bytes(code)


RVA_HUMAN_AI = 0x142814839      # human_ai 托管标志（与 0x142814833 同步翻转）
RVA_DEBUGTOOLTIP = 0x1431146F9  # 调试提示标志
RVA_IDLER_GLOBAL = 0x143114E68  # "ingame idler" 全局指针
RVA_PAUSE_OFF = 0x594           # idler+0x594 = 暂停状态字节（1=暂停）

# 版本指纹（stellaris.exe 4.5.2 实测）：函数入口前 24 字节。
# 游戏更新后这些字节会变 → 工具拒绝执行，避免乱调地址把游戏搞崩。
SIGS = {
    0x14016B4F0: "4883ec28488b0565defe024885c00f8598000000b9b00000",
    0x14015BAA0: "40534883ec20488bd933c089014889410848894110488941",
    0x14015AF40: "4889542410534883ec30488bda33d289542420488d055636",
    0x141B43650: "48895c2408488974241048897c2418554154415541564157",
}


def verify_version(h, base):
    """校验函数入口字节与已知版本一致；返回 (ok, 首个不匹配的 RVA)。"""
    for rva, sig in SIGS.items():
        b = rpm(h, base + (rva - PREF_BASE), len(sig) // 2)
        if not b or b.hex() != sig:
            return False, rva
    return True, None


def open_game():
    """返回 (h, pid, base)，失败抛 RuntimeError。"""
    pid = find_game()
    if not pid:
        raise RuntimeError("游戏没在运行")
    h = k32.OpenProcess(PROCESS_ALL, False, pid)
    if not h:
        raise RuntimeError(f"OpenProcess 失败 err={k32.GetLastError()}")
    base = module_base(h)
    if not base:
        raise RuntimeError("EnumProcessModules 失败")
    ok, bad = verify_version(h, base)
    if not ok:
        k32.CloseHandle(ctypes.c_void_p(h))
        raise RuntimeError(
            f"游戏版本指纹不匹配（0x{bad:X} 处）——游戏可能已更新，工具拒绝执行。"
            "请让 Codex 重新核对函数地址。")
    return h, pid, base


def read_flag(h, base, rva):
    """读模块内某标志字节；失败返回 None。"""
    b = rpm(h, base + (rva - PREF_BASE), 1)
    return b[0] if b else None


def read_pause(h, base):
    """读游戏暂停状态：1=暂停 0=运行中 None=读不到。"""
    idler = read_u64(h, base + (RVA_IDLER_GLOBAL - PREF_BASE))
    if not idler:
        return None
    b = rpm(h, idler + RVA_PAUSE_OFF, 1)
    return b[0] if b else None


def read_out_message(h, out):
    """从执行结果结构里取游戏写回的消息。

    不同 handler 的消息布局略有差异，这里穷举常见的 (data, size, cap) 偏移组合，
    取第一个能解出合法字符串的：
      A) data@0x18 size@0x20 cap@0x28   （resource / human_ai 系）
      B) data@0x18 size@0x28 cap@0x30   （window 系）
      C) data@0x08 size@0x10 cap@0x18
    """
    for doff, soff, coff in ((0x18, 0x20, 0x28), (0x18, 0x28, 0x30), (0x08, 0x10, 0x18)):
        size = read_u64(h, out + soff)
        cap = read_u64(h, out + coff)
        if size is None or cap is None or size == 0 or size > 8192:
            continue
        if cap > 0xF:
            ptr = read_u64(h, out + doff)
            data = rpm(h, ptr, size) if ptr else None
        else:
            data = rpm(h, out + doff, size)
        if not data:
            continue
        try:
            s = data.decode("utf-8", "replace")
        except Exception:
            continue
        printable = sum(1 for ch in s if ch.isprintable() or ch in "\r\n\t")
        if printable >= max(2, len(s) - 1) and len(s) >= 2:
            return s
    return None


def execute_command(h, base, command, verbose=False):
    """在游戏进程里执行一条控制台命令。返回 dict(ok, message, out, thread_code[, error])。"""
    result = {"ok": False, "message": None, "out": None, "thread_code": None}
    text = command.encode("utf-8") + b"\x00"
    total = 0x400
    mem = k32.VirtualAllocEx(h, None, total, MEM_COMMIT_RESERVE, PAGE_EXECUTE_READWRITE)
    if not mem:
        result["error"] = f"VirtualAllocEx 失败 err={k32.GetLastError()}"
        return result
    mem = int(mem)
    off_text, off_wrap, off_vec, off_out, off_stub = 0x00, 0x100, 0x140, 0x180, 0x200
    text_addr, wrapper, vec, out, stub_addr = (
        mem + off_text, mem + off_wrap, mem + off_vec, mem + off_out, mem + off_stub,
    )
    stub = build_stub(base, text_addr, len(text) - 1, wrapper, vec, out)
    blob = bytearray(total)
    blob[off_text : off_text + len(text)] = text
    blob[off_stub : off_stub + len(stub)] = stub
    written = ctypes.c_size_t(0)
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(mem), bytes(blob), total, ctypes.byref(written))
    if not ok or written.value != total:
        result["error"] = f"WriteProcessMemory 失败 err={k32.GetLastError()}"
        k32.VirtualFreeEx(h, ctypes.c_void_p(mem), 0, MEM_RELEASE)
        return result
    if verbose:
        print(f"缓冲区: text@0x{text_addr:X} wrapper@0x{wrapper:X} vec@0x{vec:X} out@0x{out:X} stub@0x{stub_addr:X}")
    thr = k32.CreateRemoteThread(h, None, 0, ctypes.c_void_p(stub_addr), None, 0, None)
    if not thr:
        result["error"] = f"CreateRemoteThread 失败 err={k32.GetLastError()}"
        k32.VirtualFreeEx(h, ctypes.c_void_p(mem), 0, MEM_RELEASE)
        return result
    k32.WaitForSingleObject(ctypes.c_void_p(thr), 10000)
    code = ctypes.c_uint32(0)
    k32.GetExitCodeThread(ctypes.c_void_p(thr), ctypes.byref(code))
    ob = rpm(h, out, 0x40)
    result["thread_code"] = code.value
    result["out"] = ob
    result["ok"] = bool(ob and ob[0] == 1)
    result["message"] = read_out_message(h, out) if ob else None
    if verbose:
        arr = read_u64(h, vec + 8)
        vcount = read_u32(h, vec + 0x14)
        if arr and vcount and vcount < 64:
            for i in range(vcount):
                s, size, cap = read_wrapper_str(h, arr + i * 0x30)
                print(f"  [{i}] {s!r}")
    k32.CloseHandle(ctypes.c_void_p(thr))
    k32.VirtualFreeEx(h, ctypes.c_void_p(mem), 0, MEM_RELEASE)
    return result


def main():
    args = sys.argv[1:]
    go = False
    scan = False
    if args and args[0] == "--scan":
        scan = True
        args = args[1:]
    if args and args[0] == "--go":
        go = True
        args = args[1:]
    command = args[0] if args else None

    pid = find_game()
    if not pid:
        print("游戏没在运行（先打开游戏、读档，再跑这个）")
        return
    h = k32.OpenProcess(PROCESS_ALL, False, pid)
    if not h:
        print("OpenProcess 失败 err=", k32.GetLastError())
        return
    base = module_base(h)
    if not base:
        print("EnumProcessModules 失败")
        return
    print(f"pid={pid}  模块基址=0x{base:X}")

    if scan:
        scan_commands(h, base)
        return
    if not command:
        print('用法: python console_exec.py [--scan|--go] "命令 参数..."')
        return

    mgr = read_u64(h, base + (RVA_MGR_GLOBAL - PREF_BASE))
    if mgr:
        head = command.split()[0]
        entry, handler = find_command(h, mgr, head)
        print(f"console 管理器 = 0x{mgr:X}")
        if entry:
            nm = read_cstr(h, read_u64(h, entry + 8) or 0)
            print(f"命中命令表项: '{nm}' @0x{entry:X}  handler=0x{(handler or 0):X}")
        else:
            print(f"⚠ 命令表里没有 '{head}'（执行后应返回 Unknown command）")
    else:
        print("console 管理器尚未创建（读档后才会建）")

    if not go:
        print(f"（干跑）将执行: {command}")
        return

    r = execute_command(h, base, command, verbose=False)
    if "error" in r:
        print(r["error"])
        return
    print(f"执行完成（线程码={r['thread_code']}）  ok={r['ok']}")
    if r["message"]:
        print(f"游戏回传消息: {r['message']!r}")
    if r["out"]:
        print("out[0..0x40] =", bytes(r["out"]).hex())
    k32.CloseHandle(ctypes.c_void_p(h))


if __name__ == "__main__":
    main()
