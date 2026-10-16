# -*- coding: utf-8 -*-
"""事件选项"内存级点选" 实机运行器（阶段化；执行器接线完成前安全止步）

用法：
  python evt_click.py scan          只读：找"活的窗口对象"候选（vtable 指针扫描）
  python evt_click.py build N       扫窗口 → 构造"选中第 N 项"的命令对象 → 转储（不执行）
  python evt_click.py fire N        预留：真正执行（执行器接线完成后启用；当前拒绝运行）

锚点：事件窗口类方法表 [0x142403410, 0x1424036A0)；实例特征 = 对象字段指向该区间；
      窗口对象字段：+0x78 → 事件数据指针；+0x9e4 = 事件 id。
"""
import ctypes
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import console_exec as ce  # noqa: E402
import memread as mr  # noqa: E402

IMG_BASE = 0x140000000                      # Ghidra 映像基址（静态地址 = 此 + RVA）
VT_RVA_LO = 0x142403410 - IMG_BASE          # 事件窗口类方法表（映像相对）
VT_RVA_HI = 0x1424036A0 - IMG_BASE


def in_exe(base, ptr):
    """ptr 是否落在游戏主模块映像范围（判断 vtable/函数指针是否可信）。"""
    return bool(ptr) and (base + 0x1000) <= ptr < (base + 0x8000000)


def user_ptr_ok(p):
    """粗判'像样的用户态对象指针'（堆区、8 对齐、非内核/非空）。"""
    return bool(p) and 0x10000 < p < 0x7FFFFFFFFFFF and (p & 7) == 0


def get_window_instance(h, base, name="EventWindow"):
    """［未验证槽·默认禁用］走 window 命令同款路径拿【实例】：
    instance = (*(*mgr+0x48))(mgr, nameWrapper)，mgr=[0x143159458]
    （按 window 命令反编译：类型 ≠0x264 走 +0x48；+0x58 只用于类型 0x264）

    ⚠ 2026-10-17 04:09 实机调用返回 0；04:12:26 游戏在 FUN_141aa5f40（事件效果链表拷贝）
    处 c0000005 崩溃（RVA 0x1AA5F80，悬空节点）。+0x48 槽语义未经 Ghidra 确认，
    在静态确认其为"只读查找"之前，不得再次调用（do_scan 默认不调用本函数）。"""
    k32 = ce.k32
    mem = int(k32.VirtualAllocEx(h, None, 0x400, 0x3000, 0x40))
    text_addr, wrap, scratch, stub_addr = mem, mem + 0x40, mem + 0x100, mem + 0x140
    code = bytearray()
    code += b"\x48\x83\xEC\x28"
    code += b"\x48\xB9" + struct.pack("<Q", wrap)
    code += b"\x48\xBA" + struct.pack("<Q", text_addr)
    code += b"\x48\xB8" + struct.pack("<Q", base + (0x14015BAA0 - 0x140000000))
    code += b"\xFF\xD0"
    code += b"\x49\xBA" + struct.pack("<Q", base + (0x143159458 - 0x140000000))
    code += b"\x4D\x8B\x12"
    code += b"\x4C\x89\xD1"
    code += b"\x48\xBA" + struct.pack("<Q", wrap)
    code += b"\x45\x31\xC0"
    code += b"\x45\x31\xC9"
    code += b"\x49\x8B\x02"
    code += b"\x48\x8B\x40\x48"
    code += b"\xFF\xD0"
    code += b"\x49\xBA" + struct.pack("<Q", scratch)
    code += b"\x49\x89\x02"
    code += b"\x48\x83\xC4\x28\xC3"
    blob = bytearray(0x400)
    t = (name + "\x00").encode("ascii")
    blob[0 : len(t)] = t
    blob[0x140 : 0x140 + len(code)] = code
    k32.WriteProcessMemory(h, ctypes.c_void_p(mem), bytes(blob), 0x400, None)
    thr = k32.CreateRemoteThread(h, None, 0, ctypes.c_void_p(stub_addr), None, 0, None)
    k32.WaitForSingleObject(ctypes.c_void_p(thr), 8000)
    P = ce.read_u64(h, scratch)
    k32.VirtualFreeEx(h, ctypes.c_void_p(mem), 0, 0x8000)
    return P


def find_window_candidates(h, base):
    import numpy as np
    vt_lo, vt_hi = base + VT_RVA_LO, base + VT_RVA_HI   # 运行时地址 = 基址 + 映像相对
    hits = []
    for b0, rsize, prot in mr.regions(h, writable_only=True):
        data = mr.read_mem(h, b0, rsize)
        if not data or len(data) < 8:
            continue
        n = len(data) // 8
        arr = np.frombuffer(data[: n * 8], dtype=np.uint64)
        idx = np.where((arr >= vt_lo) & (arr < vt_hi))[0]
        for i in idx[:50]:
            hits.append((b0 + int(i) * 8, int(arr[i])))
            if len(hits) >= 400:
                return hits
    return hits


def plausible_window(h, obj):
    """粗验证：能读到 +0x9e4 处一个合理范围的小整数（事件 id，宽松判定）"""
    try:
        raw = ce.rpm(h, obj + 0x9E4, 4)
        if not raw:
            return False
        v = struct.unpack("<i", raw)[0]
        return 0 <= v <= 0x7FFFFFF0
    except Exception:
        return False


def chain_info(h, win, n=0):
    """读取 窗口 →( +0x78 两跳) 事件数据 → vtable → 选项表 的完整指针链（只读）。
    静态依据：分发器 FUN_14107b1d0 用 **（W+0x78） 作 eventData；选项表内嵌在
    eventData+0x5e0（+8=数组指针、+0x14=选项数、步长 0x10）。"""
    d = {"W": win, "x": 0, "y": 0, "vt": 0, "cnt": None, "arr": 0, "item": 0}
    try:
        d["x"] = ce.read_u64(h, win + 0x78) or 0
        d["y"] = (ce.read_u64(h, d["x"]) or 0) if d["x"] else 0
        d["vt"] = (ce.read_u64(h, d["y"]) or 0) if d["y"] else 0
        if d["y"]:
            d["cnt"] = ce.read_u32(h, d["y"] + 0x5F4)      # 0x5e0+0x14
            d["arr"] = ce.read_u64(h, d["y"] + 0x5E8) or 0  # 0x5e0+0x8
            if d["arr"] and d["cnt"] and 0 <= n < d["cnt"]:
                d["item"] = ce.read_u64(h, d["arr"] + n * 0x10) or 0
    except Exception:
        pass
    return d


def chain_gate_ok(base, d, n):
    """完整闸门：两跳堆指针健全 + 事件数据 vtable 在 exe 区 + 选项表健全。"""
    return (user_ptr_ok(d["x"]) and user_ptr_ok(d["y"]) and in_exe(base, d["vt"])
            and d["cnt"] is not None and 1 <= d["cnt"] <= 24 and user_ptr_ok(d["arr"]))


def pick_window(h, base, good, n):
    """从候选里挑第一个通过完整闸门的窗口（打印每个候选的链状态）。"""
    for win in good[:8]:
        d = chain_info(h, win, n)
        ok = chain_gate_ok(base, d, n)
        print(f"  [挑窗] @0x{win:X} X=0x{d['x']:X} Y=0x{d['y']:X} vt=0x{d['vt']:X} "
              f"选项数={d['cnt']} arr=0x{d['arr']:X} item[{n}]=0x{d['item']:X} "
              f"{'PASS' if ok else 'fail'}")
        if ok:
            return win, d
    return None, None


def do_scan(h, base=None, via_slot=False):
    """定位窗口候选：默认只走只读扫描（+0x48 槽调用未验证且疑似 04:12 崩溃诱因，默认禁用）。"""
    if base is None:
        base = ce.module_base(h)
    good = []
    if via_slot:
        inst = get_window_instance(h, base)
        if inst:
            print(f"管理器实例通道返回 = 0x{inst:X}")
            good.append(inst)
    hits = find_window_candidates(h, base)
    print(f"vtable 区间扫描命中 {len(hits)} 处（备用通道）")
    for slot, _vt in hits[:80]:
        if slot not in good and plausible_window(h, slot):
            good.append(slot)
    for slot in good[:12]:
        idd = struct.unpack("<i", ce.rpm(h, slot + 0x9E4, 4) or b"\0\0\0\0")[0]
        vt0 = ce.read_u64(h, slot) or 0
        tag = "(exe)" if in_exe(base, vt0) else "(非exe!)"
        print(f"  候选窗口 @0x{slot:X}  vtable=0x{vt0:X}{tag}  +0x9e4={idd}")
    return good


def build_cmd(h, base, win, n):
    """调用 FUN_1408e5d20(**(win+0x78), scratch, win+0x80, 1, N, 1) 构造命令对象"""
    k32 = ce.k32
    func = base + (0x1408E5D20 - 0x140000000)
    # ---- 安全闸：验证 win+0x78 → 事件数据 → vtable → 选项表 完整链（2026-10-17 崩溃教训） ----
    d = chain_info(h, win, n)
    ok = chain_gate_ok(base, d, n)
    print(f"[闸] X=0x{d['x']:X} Y=0x{d['y']:X} vt=0x{d['vt']:X} "
          f"选项数={d['cnt']} arr=0x{d['arr']:X} item[{n}]=0x{d['item']:X}")
    if not ok:
        print("⛔ 安全闸触发：指针链/选项表不满足健全性条件（拒绝构造，不执行任何跨进程调用）。")
        print("   参见 kernel_findings.md 崩溃复盘；先跑 evt_click.py scan 看链诊断。")
        return None, -1
    mem = int(k32.VirtualAllocEx(h, None, 0x400, 0x3000, 0x40))
    off_scratch, off_stub = 0x00, 0x100
    scratch, stub_addr = mem + off_scratch, mem + off_stub
    code = bytearray()
    code += b"\x48\x83\xEC\x38"                                    # sub rsp,0x38
    code += b"\x49\xBA" + struct.pack("<Q", win)                   # mov r10, win
    code += b"\x4D\x8B\x5A\x78"                                    # mov r11,[r10+0x78]
    code += b"\x49\x8B\x0B"                                        # mov rcx,[r11]
    code += b"\x48\xBA" + struct.pack("<Q", scratch)               # mov rdx, scratch
    code += b"\x49\xB8" + struct.pack("<Q", win + 0x80)            # mov r8, win+0x80
    code += b"\x45\x31\xC9"                                        # xor r9d,r9d
    code += b"\x41\xB1\x01"                                        # mov r9b,1
    code += b"\xC7\x44\x24\x20" + struct.pack("<i", n)             # mov dword [rsp+0x20], N
    code += b"\xC7\x44\x24\x28\x01\x00\x00\x00"                    # mov dword [rsp+0x28], 1
    code += b"\x48\xB8" + struct.pack("<Q", func)                  # mov rax, func
    code += b"\xFF\xD0"                                            # call rax
    code += b"\x48\x83\xC4\x38\xC3"                                # add rsp,0x38; ret
    blob = bytearray(0x400)
    blob[off_stub : off_stub + len(code)] = code
    if not k32.WriteProcessMemory(h, ctypes.c_void_p(mem), bytes(blob), 0x400, None):
        print("WriteProcessMemory 失败")
        return None, mem
    thr = k32.CreateRemoteThread(h, None, 0, ctypes.c_void_p(stub_addr), None, 0, None)
    if not thr:
        print("CreateRemoteThread 失败")
        return None, mem
    k32.WaitForSingleObject(ctypes.c_void_p(thr), 8000)
    raw = ce.rpm(h, scratch, 0x60)
    return raw, mem


def main():
    args = sys.argv[1:]
    mode = args[0] if args else "scan"
    if mode == "fire":
        print("执行器接线未完成（见 kernel_findings.md），fire 暂不开放——安全优先。")
        return
    try:
        h, pid, base = ce.open_game()
    except Exception as e:
        print("无法连接游戏：", e)
        return
    print(f"pid={pid} base=0x{base:X}")
    if mode == "validate":
        print("⛔ validate 模式已禁用：实测『无事件上下文时 window open EventWindow』会导致游戏崩溃")
        print("   （2026-10-17 03:53 事故）。请走安全路径：托管OFF → event 触发 → scan→build（带指针闸）。")
        return
    if False:  # 保留原实现作参考，永不执行
        r = ce.execute_command(h, base, "window open EventWindow")
        print("window open ->", r.get("ok"), r.get("message"))
        time.sleep(1.2)
        P = get_window_instance(h, base)
        print("实例 =", hex(P) if P else 0)
        if P:
            idd = struct.unpack("<i", ce.rpm(h, P + 0x9E4, 4) or b"\0\0\0\0")[0]
            ev = ce.read_u64(h, P + 0x78)
            ev2 = ce.read_u64(h, ev) if ev else 0
            print(f"  +0x9e4={idd}  [P+0x78]=0x{(ev or 0):X}  **[P+0x78]=0x{(ev2 or 0):X}")
            raw = ce.rpm(h, P, 0x90)
            print("  对象头:", raw.hex() if raw else "?")
        for _i in range(3):
            rc = ce.execute_command(h, base, "window close EventWindow")
            if rc.get("ok"):
                print("close ok")
                break
            time.sleep(0.8)
        print("清理后实例 =", hex(get_window_instance(h, base) or 0))
        return
    good = do_scan(h, base)
    if mode == "scan":
        return
    if mode == "build":
        if len(args) < 2:
            print("用法：build N")
            return
        n = int(args[1])
        if not good:
            print("没有找到可疑窗口对象——确认事件弹窗正开着（托管 OFF + 触发事件）")
            return
        win, d = pick_window(h, base, good, n)
        if not win:
            print("候选窗口都没过完整闸门——先跑 scan 看诊断输出。")
            return
        print(f"使用窗口候选 @0x{win:X}，构造第 {n} 项命令对象（不执行）...")
        raw, mem = build_cmd(h, base, win, n)
        if raw:
            print("命令对象前 0x60 字节:", raw.hex())
            vt = struct.unpack_from("<Q", raw, 0)[0]
            if in_exe(base, vt):
                img = IMG_BASE + (vt - base)
                print(f"vtable 运行时=0x{vt:X}   Ghidra 映像地址=0x{img:X}")
                print("槽位前 16 项（运行时调用地址 / 括号内为 Ghidra 地址）：")
                for k in range(16):
                    q = ce.read_u64(h, vt + k * 8)
                    if q and in_exe(base, q):
                        print(f"  [{k}] 0x{q:X}  (Ghidra 0x{IMG_BASE + (q - base):X})")
                    else:
                        print(f"  [{k}] 0x{(q or 0):X}")
                print("→ 把 Ghidra 地址交 Ghidra 反查函数体，定位 Execute 槽后交给 evt_fire.py。")
            else:
                print("首字段不是 exe 指针（vtable 可能在其他偏移），请人工查看转储。")
        if mem and mem > 0:
            ce.k32.VirtualFreeEx(h, ctypes.c_void_p(mem), 0, 0x8000)


if __name__ == "__main__":
    main()
