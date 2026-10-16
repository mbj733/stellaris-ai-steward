# -*- coding: utf-8 -*-
"""事件选项"内存级选择器"（2026-10-16 实机打通并验证）

链路（全部由游戏自身函数完成，Python 只摆参数与把关）：
    gamestate[+0x180] 活动事件列表 → EVT（+0x180 = 事件实例 id）
      EVT+8 → X → OBJ = *X（事件数据：名@+0x20、编号@+8、选项表@+0x5E0）
    FUN_1408e2270(EVT, 选项序号) → 游戏自建 CSelectEventOptionCommand（vtable 0x1423ABDD8）
      → FUN_14099cd60 校验 → FUN_1408e9aa0 装箱 → FUN_1405f88a0 提交命令管线

实测证据（2026-10-16 19:24:40 / game.log）：
    Event ambition.125 added info about event selection. selectedOption 0, human 1, playerEventId 645
    （调用后：事件从待决列表消失；事件窗口被游戏自行回收关闭；游戏无崩溃）

用法：
    python evt_select.py list                列出待决事件（只读）
    python evt_select.py auto                自动处理"唯一选项"事件；多选项仅报告（需游戏暂停）
    python evt_select.py select <iid> <idx>  选择指定事件实例的第 idx 项（需游戏暂停）

安全规则：
  - 真执行前必须确认 暂停=1（外线程调用游戏函数，暂停可最大限度降低竞态）；
  - 指针全闸门（列表/对象/事件数据/选项数组任一不合格 → 拒绝执行）；
  - 绝不自动处理"多选项"事件（选项内容未解码前，交由决策层/用户处置）；
  - 一切动作写入 logs/decisions.log（审计）。
"""
import ctypes
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import console_exec as ce  # noqa: E402
import evt_click as ec  # noqa: E402

k32 = ce.k32
k32.VirtualAllocEx.restype = ctypes.c_void_p
k32.CreateRemoteThread.restype = ctypes.c_void_p

RVA_FN_SELECT = 0x8E2270   # FUN_1408e2270(事件项, 选项序号)
RVA_GS = 0x3114700         # DAT_143114700 当前 gamestate

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "decisions.log"


def log(msg):
    try:
        LOG.parent.mkdir(exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except Exception:
        pass


def u64(h, a):
    b = ce.rpm(h, a, 8)
    return struct.unpack("<Q", b)[0] if b else None


def u32(h, a):
    b = ce.rpm(h, a, 4)
    return struct.unpack("<I", b)[0] if b else None


def i32(h, a):
    b = ce.rpm(h, a, 4)
    return struct.unpack("<i", b)[0] if b else None


def rname(h, a, maxlen=64):
    """读 MSVC std::string（{内联16字节|指针, size@+0x10, cap@+0x18}）。
    长度 ≥16 时 +0 是堆指针——旧式盲读会拿到指针字节导致长名事件读不出（2026-10-16 修复）。"""
    head = ce.rpm(h, a, 16)
    if not head:
        return None
    size = u64(h, a + 0x10)
    raw = None
    if size and 0 < size < 512:
        if size >= 16:
            if len(head) >= 8:
                ptr = struct.unpack("<Q", head[:8])[0]
                raw = ce.rpm(h, ptr, int(size)) if ptr else None
        else:
            raw = head[:int(size)]
            if not raw:
                raw = None
    if raw is None:  # 回退：旧式读法（兼容非 std::string 场景）
        b = ce.rpm(h, a, maxlen)
        if not b:
            return None
        z = b.find(b"\x00")
        raw = b if z < 0 else b[:z]
    if not raw:
        return None
    try:
        s = raw.decode("utf-8")
        return s if s.isprintable() else None
    except Exception:
        return None


def pending_events(h, base):
    """列出待决事件（只读）。返回 list[dict] 或 None（读取失败）。"""
    gs = u64(h, base + RVA_GS)
    if not ec.user_ptr_ok(gs):
        return None
    lst = u64(h, gs + 0x180)
    cnt = u32(h, gs + 0x18C)
    if cnt is None:
        return None
    if cnt == 0:
        return []
    if not ec.user_ptr_ok(lst) or cnt > 4096:
        return None
    out = []
    for i in range(cnt):
        p = u64(h, lst + i * 8)
        if not (p and ec.user_ptr_ok(p)):
            continue
        iid = i32(h, p + 0x180)
        x = u64(h, p + 8) or 0
        obj = (u64(h, x) or 0) if ec.user_ptr_ok(x) else 0
        name = rname(h, obj + 0x20) if obj else None
        n = i32(h, obj + 0x5F4) if obj else None
        arr = u64(h, obj + 0x5E8) if obj else 0
        item0 = u64(h, arr) if (arr and ec.user_ptr_ok(arr)) else 0
        gate = bool(ec.user_ptr_ok(x) and ec.user_ptr_ok(obj) and name
                    and n and 0 < n <= 24 and ec.user_ptr_ok(arr) and ec.user_ptr_ok(item0))
        out.append(dict(evt=p, iid=iid, obj=obj, name=name, n_opts=n, arr=arr, gate=gate))
    return out


def call_select(h, base, evt, idx, timeout_ms=10000):
    """远程调用 FUN_1408e2270(evt, idx)。返回 (完成标记 bytes, 等待结果)。"""
    mem = int(k32.VirtualAllocEx(h, None, 0x200, 0x3000, 0x40))
    if not mem:
        return None, "alloc fail"
    scratch = mem
    stub = mem + 0x100
    fn = base + RVA_FN_SELECT
    code = b""
    code += b"\x48\x83\xEC\x28"
    code += b"\x48\xB9" + struct.pack("<Q", evt)
    code += b"\xBA" + struct.pack("<I", idx & 0xFFFFFFFF)
    code += b"\x48\xB8" + struct.pack("<Q", fn)
    code += b"\xFF\xD0"
    code += b"\x48\xB1\xA5"
    code += b"\x48\xBA" + struct.pack("<Q", scratch)
    code += b"\x88\x0A"
    code += b"\x48\x83\xC4\x28\xC3"
    blob = bytearray(0x200)
    blob[0x100:0x100 + len(code)] = code
    if not k32.WriteProcessMemory(h, ctypes.c_void_p(mem), bytes(blob), 0x200, None):
        k32.VirtualFreeEx(h, ctypes.c_void_p(mem), 0, 0x8000)
        return None, "wpm fail"
    thr = k32.CreateRemoteThread(h, None, 0, ctypes.c_void_p(stub), None, 0, None)
    if not thr:
        k32.VirtualFreeEx(h, ctypes.c_void_p(mem), 0, 0x8000)
        return None, "thread fail"
    rc = k32.WaitForSingleObject(ctypes.c_void_p(thr), timeout_ms)
    time.sleep(0.8)
    flag = ce.rpm(h, scratch, 1)
    k32.CloseHandle(ctypes.c_void_p(thr))
    k32.VirtualFreeEx(h, ctypes.c_void_p(mem), 0, 0x8000)
    return flag, rc


def select_option(h, base, ev, idx, verify=True):
    """对一个 pending_events() 条目执行选择。返回 True/False。"""
    if not ev.get("gate"):
        log(f"[evt_select] 拒绝执行（闸门未过）：{ev.get('name')} id={ev.get('iid')}")
        return False
    if ce.read_pause(h, base) != 1:
        log(f"[evt_select] 拒绝执行（游戏未暂停）：{ev.get('name')} id={ev.get('iid')}")
        return False
    # 竞态防护：快照可能已过期（游戏 AI / 其他路径先处理了）→ 执行前立即重验
    fresh = None
    try:
        for x in (pending_events(h, base) or []):
            if x.get("iid") == ev.get("iid"):
                fresh = x
                break
    except Exception:
        fresh = None
    if not fresh or not fresh.get("gate"):
        log(f"[evt_select] 事件已不在待决列表（竞态防护触发）：{ev.get('name')} id={ev.get('iid')}")
        return False
    ev = fresh
    if not (isinstance(idx, int) and 0 <= idx < (ev.get("n_opts") or 0)):
        log(f"[evt_select] 拒绝执行（选项序号越界）：idx={idx} n={ev.get('n_opts')}")
        return False
    flag, rc = call_select(h, base, ev["evt"], idx)
    time.sleep(1.2)
    ok = flag == b"\xa5"
    consumed = None
    if verify:
        lst2 = pending_events(h, base)
        if lst2 is not None:
            consumed = all(x.get("iid") != ev.get("iid") for x in lst2)
    log(f"[evt_select] 选择：{ev.get('name')} id={ev.get('iid')} 选项{idx} "
        f"调用={'完成' if ok else '异常'} 事件已消费={consumed}")
    return bool(ok and (consumed is not False))


def cmd_list(h, base):
    pend = pending_events(h, base)
    if pend is None:
        print("读取失败（先进游戏读档）")
        return 1
    print(f"待决事件 {len(pend)} 个：")
    if not pend:
        print("  （无——所有事件均已处理）")
    for ev in pend:
        print(f"  id={ev['iid']}  名={ev['name']}  选项数={ev['n_opts']}  闸门={'PASS' if ev['gate'] else 'FAIL'}")
    return 0


def cmd_auto(h, base):
    if ce.read_pause(h, base) != 1:
        print("游戏未暂停，auto 模式拒绝执行")
        return 2
    pend = pending_events(h, base)
    if pend is None:
        print("读取失败")
        return 1
    acted = 0
    for ev in pend:
        if not ev.get("gate"):
            continue
        if ev["n_opts"] == 1:
            if select_option(h, base, ev, 0):
                acted += 1
        else:
            log(f"[evt_select] 多选项事件待决策：{ev['name']} id={ev['iid']} 选项数={ev['n_opts']}（未自动处理）")
            print(f"  多选项待决策：{ev['name']} (id={ev['iid']}, {ev['n_opts']} 项)")
    print(f"auto 完成：自动处理 {acted} 个单选项事件")
    return 0


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    h, pid, base = ce.open_game()
    mode = args[0]
    if mode == "list":
        return cmd_list(h, base)
    if mode == "auto":
        return cmd_auto(h, base)
    if mode == "select" and len(args) == 3:
        iid, idx = int(args[1]), int(args[2])
        pend = pending_events(h, base) or []
        ev = next((x for x in pend if x.get("iid") == iid), None)
        if ev is None:
            print(f"没有 id={iid} 的待决事件")
            return 3
        ok = select_option(h, base, ev, idx)
        print("完成" if ok else "失败")
        return 0 if ok else 4
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
