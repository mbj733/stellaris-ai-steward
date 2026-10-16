# -*- coding: utf-8 -*-
"""log88 观察/改写钩子（FUN_14099c090 = 全部事件选择命令的公共汇聚点）

RW0（默认 install）: 记录每次调用的 (eventId, option, human, cmd指针) + 总数。
RW1（install --rw）: 24 槽武装表 {flag, keyType, key, option}：
    keyType=0 → 匹配 cmd+0x28（playerEventId，精确到事件实例）
    keyType=1 → 匹配 cmd+0x20（事件模板 id，按"事件名"预武装，任何新实例都命中）
    仅当 human==-1（游戏 AI 自动选择）时改写 cmd+0x24 ← option。
    **模板匹配附带归属校验**：cmd+0x28 必须出现在我方待决事件列表（gs+0x180）中，
    否则拒绝改写并累加 blocked 计数——保证绝不误改其他帝国的 AI 选择。

用法:
  python hook_rw88.py install [--rw]      # 装（RW0 观察 / RW1 改写）
  python hook_rw88.py read                # 读计数、武装表、blocked 拦截数
  python hook_rw88.py arm <key> <opt> [--tpl]    # 武装（--tpl=按模板 id）
  python hook_rw88.py disarm [key] [--tpl]       # 解除（缺省=清空全部）
  python hook_rw88.py revert
"""
import ctypes
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import console_exec as ce

k32 = ce.k32
k32.VirtualAllocEx.restype = ctypes.c_void_p
k32.VirtualProtectEx.restype = ctypes.c_int

RVA_FN = 0x99C090            # FUN_14099c090
RVA_GS = 0x3114700           # DAT_143114700（gamestate 指针全局）
EXPECT_ORIG = "48895c2418555657415441554156"  # 函数序言 14 字节
STATE = Path(__file__).resolve().parent / "_hook_state_rw88.json"

SCR_TOTAL = 0x00   # u64 调用总数
SCR_EVID = 0x08    # u64 最近 playerEventId（含 human 高位）
SCR_OPT = 0x10     # u32 最近 option（进钩子时的原值）
SCR_HUM = 0x18     # u32 最近 human
SCR_CMD = 0x20     # u64 最近 cmd 指针
SCR_RWN = 0x28     # u64 改写次数
SCR_POST = 0x30    # u32 改写后的值
SLOT_BASE = 0x38   # 24 槽武装表：每槽 16B = {u32 flag, u32 keyType, u32 key, u32 option}
SLOT_N = 24
SLOT_SZ = 16
SCR_TPL = 0x1C0    # u32 最近事件模板 id
SCR_BLK = 0x1C4    # u64 归属校验拦截次数
SCR_RWIDX = 0x1CC  # u32 改写环形缓冲写指针（只在改写发生时 ++；0x1C4 拦截计数为 u64，勿越界）
SCR_RWBUF = 0x200  # 8 条 × 16B {u32 evid, u32 pre, u32 post, u32 tpl}
STATE_VER = 5


def suspend_all_threads(pid):
    import psutil
    handles = []
    p = psutil.Process(pid)
    for t in p.threads():
        h = k32.OpenThread(0x1F03FF, False, t.id)
        if h:
            if k32.SuspendThread(ctypes.c_void_p(h)) != -1:
                handles.append(h)
    return handles


def resume_all_threads(handles):
    for h in handles:
        k32.ResumeThread(ctypes.c_void_p(h))
        k32.CloseHandle(ctypes.c_void_p(h))


def build_cave(scratch, fn, n, orig, rw, gs_var=0):
    code = bytearray()
    fix = []   # (disp_pos, size, label)
    lab = {}

    def emit(b):
        code.extend(b)

    def mark(name):
        lab[name] = len(code)

    def rel8(label):
        fix.append((len(code), 1, label))
        code.extend(b"\x00")

    def rel32(label):
        fix.append((len(code), 4, label))
        code.extend(b"\x00\x00\x00\x00")

    emit(b"\x9C")                                    # pushfq
    emit(b"\x50\x52")                                # push rax, rdx
    emit(b"\x53")                                    # push rbx
    emit(b"\x41\x50\x41\x51\x41\x52")                # push r8, r9, r10
    emit(b"\x49\xB8" + struct.pack("<Q", scratch))   # mov r8, scratch
    emit(b"\xF0\x49\xFF\x00")                        # lock inc qword [r8]
    emit(b"\x48\x8B\x41\x28")                        # mov rax,[rcx+0x28]
    emit(b"\x49\x89\x40\x08")                        # mov [r8+8],rax
    emit(b"\x8B\x41\x24")                            # mov eax,[rcx+0x24]
    emit(b"\x41\x89\x40\x10")                        # mov [r8+0x10],eax
    emit(b"\x8B\x41\x2C")                            # mov eax,[rcx+0x2c]
    emit(b"\x41\x89\x40\x18")                        # mov [r8+0x18],eax
    emit(b"\x49\x89\x48\x20")                        # mov [r8+0x20],rcx
    emit(b"\x8B\x41\x20")                            # mov eax,[rcx+0x20]（事件模板 id）
    emit(b"\x41\x89\x80" + struct.pack("<I", SCR_TPL))   # mov [r8+SCR_TPL],eax
    if rw:
        emit(b"\x83\x79\x2C\xFF")                    # cmp dword [rcx+0x2c], -1
        emit(b"\x0F\x85"); rel32("SKIP")             # jne SKIP（非 AI 选择不改写）
        # ---- Loop A：按实例匹配（keyType=0）----
        emit(b"\x4D\x8D\x48\x38")                    # lea r9,[r8+0x38]
        emit(b"\x41\xBA" + struct.pack("<I", SLOT_N))  # mov r10d, SLOT_N
        mark("A0")
        emit(b"\x41\x83\x39\x01")                    # cmp dword [r9],1
        emit(b"\x75"); rel8("A1")
        emit(b"\x41\x83\x79\x04\x00")                # cmp dword [r9+4],0
        emit(b"\x75"); rel8("A1")
        emit(b"\x8B\x41\x28")                        # mov eax,[rcx+0x28]
        emit(b"\x41\x3B\x41\x08")                    # cmp eax,[r9+8]
        emit(b"\x75"); rel8("A1")
        emit(b"\x4D\x89\xCB")                        # mov r11,r9
        emit(b"\xE9"); rel32("REWRITE")
        mark("A1")
        emit(b"\x49\x83\xC1\x10")                    # add r9,16
        emit(b"\x41\xFF\xCA")                        # dec r10d
        emit(b"\x75"); rel8("A0")
        # ---- Loop B：按模板匹配（keyType=1，带归属校验）----
        emit(b"\x4D\x8D\x48\x38")                    # lea r9,[r8+0x38]
        emit(b"\x41\xBA" + struct.pack("<I", SLOT_N))  # mov r10d, SLOT_N
        mark("B0")
        emit(b"\x41\x83\x39\x01")                    # cmp dword [r9],1
        emit(b"\x75"); rel8("B2")
        emit(b"\x41\x83\x79\x04\x01")                # cmp dword [r9+4],1
        emit(b"\x75"); rel8("B2")
        emit(b"\x8B\x41\x20")                        # mov eax,[rcx+0x20]
        emit(b"\x41\x3B\x41\x08")                    # cmp eax,[r9+8]
        emit(b"\x75"); rel8("B2")
        emit(b"\x4D\x89\xCB")                        # mov r11,r9
        emit(b"\xE9"); rel32("MATCH")
        mark("B2")
        emit(b"\x49\x83\xC1\x10")                    # add r9,16
        emit(b"\x41\xFF\xCA")                        # dec r10d
        emit(b"\x75"); rel8("B0")
        emit(b"\xE9"); rel32("SKIP")
        # ---- MATCH：归属校验（cmd+0x28 必须在我方待决列表）----
        mark("MATCH")
        emit(b"\x48\xB8" + struct.pack("<Q", gs_var))  # mov rax, gs_var
        emit(b"\x48\x8B\x00")                        # mov rax,[rax]
        emit(b"\x48\x85\xC0")                        # test rax,rax
        emit(b"\x74"); rel8("OWNFAIL")
        emit(b"\x48\x8B\x90" + struct.pack("<I", 0x180))  # mov rdx,[rax+0x180]
        emit(b"\x48\x85\xD2")                        # test rdx,rdx
        emit(b"\x74"); rel8("OWNFAIL")
        emit(b"\x8B\x98" + struct.pack("<I", 0x18C))  # mov ebx,[rax+0x18c]
        emit(b"\x85\xDB")                            # test ebx,ebx
        emit(b"\x7E"); rel8("OWNFAIL")               # jle
        emit(b"\x81\xFB\x00\x00\x01\x00")            # cmp ebx,0x10000
        emit(b"\x77"); rel8("OWNFAIL")               # ja
        mark("OWL")
        emit(b"\x48\x8B\x02")                        # mov rax,[rdx]
        emit(b"\x48\x85\xC0")                        # test rax,rax
        emit(b"\x74"); rel8("OW2")                   # jz
        emit(b"\x44\x8B\x88" + struct.pack("<I", 0x180))  # mov r9d,[rax+0x180]
        emit(b"\x44\x3B\x89" + struct.pack("<I", 0x28))   # cmp r9d,[rcx+0x28]
        emit(b"\x74"); rel8("REWRITE")               # je（命中我方事件）
        mark("OW2")
        emit(b"\x48\x83\xC2\x08")                    # add rdx,8
        emit(b"\xFF\xCB")                            # dec ebx
        emit(b"\x75"); rel8("OWL")
        mark("OWNFAIL")
        emit(b"\xF0\x49\xFF\x80" + struct.pack("<I", SCR_BLK))  # lock inc [r8+BLK]
        emit(b"\x4D\x89\xD9")                        # mov r9,r11
        emit(b"\xE9"); rel32("B2")                   # 继续扫下一个槽
        # ---- REWRITE ----
        mark("REWRITE")
        emit(b"\x41\x8B\x43\x0C")                    # mov eax,[r11+0xC]
        emit(b"\x89\x41\x24")                        # mov [rcx+0x24],eax
        emit(b"\xF0\x49\xFF\x40\x28")                # lock inc qword [r8+0x28]
        emit(b"\x41\x89\x40\x30")                    # mov [r8+0x30],eax
        # —— 改写环形缓冲：8 条 × 16B（evid,pre,post,tpl）@0x200，idx u32@0x1C8 ——
        emit(b"\x41\x8B\x90" + struct.pack("<I", 0x1CC))   # mov edx,[r8+0x1CC]
        emit(b"\x83\xE2\x07")                              # and edx,7
        emit(b"\xC1\xE2\x04")                              # shl edx,4
        emit(b"\x49\x8D\x94\x10" + struct.pack("<I", 0x200))  # lea rdx,[r8+rdx+0x200]
        emit(b"\x45\x8B\x50\x08")                          # mov r10d,[r8+8]
        emit(b"\x44\x89\x12")                              # mov [rdx],r10d
        emit(b"\x45\x8B\x50\x10")                          # mov r10d,[r8+0x10]
        emit(b"\x44\x89\x52\x04")                          # mov [rdx+4],r10d
        emit(b"\x89\x42\x08")                              # mov [rdx+8],eax
        emit(b"\x45\x8B\x90" + struct.pack("<I", 0x1C0))   # mov r10d,[r8+0x1C0]
        emit(b"\x44\x89\x52\x0C")                          # mov [rdx+0xC],r10d
        emit(b"\xF0\x41\xFF\x80" + struct.pack("<I", 0x1CC))  # lock inc dword [r8+0x1CC]
        emit(b"\xE9"); rel32("SKIP")
        mark("SKIP")
    emit(b"\x41\x5A\x41\x59\x41\x58")                # pop r10, r9, r8
    emit(b"\x5B")                                    # pop rbx
    emit(b"\x5A\x58")                                # pop rdx, rax
    emit(b"\x9D")                                    # popfq
    emit(orig)
    emit(b"\xFF\x25\x00\x00\x00\x00" + struct.pack("<Q", fn + n))
    for pos, size, label in fix:
        off = lab[label] - (pos + size)
        if size == 1:
            assert -128 <= off <= 127, "rel8 超范围：%s" % label
            code[pos] = off & 0xFF
        else:
            assert -2 ** 31 <= off < 2 ** 31, "rel32 超范围：%s" % label
            code[pos:pos + 4] = struct.pack("<i", off)
    return bytes(code)


def verify_cave(code, n, fn, gs_var):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    ins = list(md.disasm(code, 0))
    assert ins, "capstone 反汇编为空"
    jp = None
    for i in ins:
        if i.mnemonic == "jmp" and "rip" in i.op_str:
            jp = i
            break
    assert jp is not None, "找不到 jmp [rip] 回跳指令"
    for i in ins:
        if i.address >= jp.address:
            break
        assert i.mnemonic != "(bad)", "发现非法指令 @%d" % i.address
    assert jp.size == 6, "jmp[rip] 长度异常"
    tgt = struct.unpack_from("<Q", code, jp.address + 6)[0]
    assert tgt == fn + n, "跳回目标错误: 0x%X != 0x%X" % (tgt, fn + n)
    return [("%s %s" % (i.mnemonic, i.op_str)) for i in ins if i.address <= jp.address]


def install(rw=False):
    h, pid, base = ce.open_game()
    fn = base + RVA_FN
    raw = ce.rpm(h, fn, 32)
    if raw[:14].hex() != EXPECT_ORIG:
        print("!! 入口字节与预期不符（可能已装其它钩子或版本变化）: %s" % raw[:14].hex())
        return 2
    orig = bytes.fromhex(EXPECT_ORIG)
    n = 14
    mem = int(k32.VirtualAllocEx(h, None, 0x1000, 0x3000, 0x40))
    if not mem:
        print("VirtualAllocEx 失败")
        return 2
    scratch = mem + 0x800
    gs_var = base + RVA_GS
    code = build_cave(scratch, fn, n, orig, rw, gs_var)
    dis = verify_cave(code, n, fn, gs_var)
    print("cave 指令数: %d" % len(dis))
    for d in dis[:14]:
        print("   ", d)
    blob = bytearray(0x1000)
    blob[0:len(code)] = code
    if not k32.WriteProcessMemory(h, ctypes.c_void_p(mem), bytes(blob), 0x1000, None):
        print("写代码洞失败")
        return 2
    patch = b"\xFF\x25\x00\x00\x00\x00" + struct.pack("<Q", mem)
    old_prot = ctypes.c_uint32(0)
    k32.VirtualProtectEx(h, ctypes.c_void_p(fn), 64, 0x40, ctypes.byref(old_prot))
    handles = suspend_all_threads(pid)
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(fn), patch, len(patch), None)
    resume_all_threads(handles)
    k32.VirtualProtectEx(h, ctypes.c_void_p(fn), 64, old_prot.value, ctypes.byref(old_prot))
    if not ok:
        print("打补丁失败")
        return 2
    STATE.write_text(json.dumps({
        "base": base, "fn": fn, "n": n, "orig": orig.hex(),
        "cave": mem, "scratch": scratch, "rw": bool(rw), "ver": STATE_VER,
    }), encoding="utf-8")
    print("已安装 rw88（%s）：cave=0x%X scratch=0x%X" % ("RW1 改写版(24槽+归属校验)" if rw else "RW0 观察版", mem, scratch))
    return read()


def ensure(rw=True):
    """钩子不在线（未装 / 游戏重启 / 旧版本）则安装。返回 True/False。"""
    try:
        st = json.loads(STATE.read_text(encoding="utf-8"))
        h, pid, base = ce.open_game()
        same = (int(st.get("base") or 0) == base
                and int(st.get("ver") or 0) == STATE_VER
                and (not rw or st.get("rw")))
        if same:
            return True
    except Exception:
        pass
    return install(rw=rw) == 0


def _open():
    st = json.loads(STATE.read_text(encoding="utf-8"))
    h, pid, base = ce.open_game()
    if base != st["base"]:
        return None, None, st
    return h, base, st


def read():
    h, base, st = _open()
    if h is None:
        print("!! 游戏已重启（base 变化），钩子不在了")
        return 2
    raw = ce.rpm(h, st["scratch"], SLOT_BASE + SLOT_N * SLOT_SZ + 32)
    total = struct.unpack_from("<Q", raw, SCR_TOTAL)[0]
    evid = struct.unpack_from("<Q", raw, SCR_EVID)[0]
    opt = struct.unpack_from("<I", raw, SCR_OPT)[0]
    hum = struct.unpack_from("<i", raw, SCR_HUM)[0]
    cmd = struct.unpack_from("<Q", raw, SCR_CMD)[0]
    rwn = struct.unpack_from("<Q", raw, SCR_RWN)[0]
    post = struct.unpack_from("<I", raw, SCR_POST)[0]
    tpl = struct.unpack_from("<I", raw, SCR_TPL)[0]
    blk = struct.unpack_from("<Q", raw, SCR_BLK)[0]
    rwidx = struct.unpack_from("<I", raw, SCR_RWIDX)[0]
    print("总调用=%d | 最近: evid=%d tpl=%d opt=%d human=%d cmd=0x%X" % (total, evid & 0xFFFFFFFF, tpl, opt, hum, cmd))
    print("改写=%d 缓冲指针=%d 最近post=%d | 归属拦截=%d" % (rwn, rwidx, post, blk))
    slots = []
    for k in range(SLOT_N):
        s = struct.unpack_from("<IIII", raw, SLOT_BASE + k * SLOT_SZ)
        if s[0] == 1:
            slots.append("%s:%d→%d" % ("模板" if s[1] == 1 else "实例", s[2], s[3]))
    print("武装(%d/%d): %s" % (len(slots), SLOT_N, " | ".join(slots) if slots else "（）"))
    return 0


def _read_slots(h, st):
    raw = ce.rpm(h, st["scratch"] + SLOT_BASE, SLOT_N * SLOT_SZ)
    if not raw:
        return None
    return [list(struct.unpack_from("<IIII", raw, k * SLOT_SZ)) for k in range(SLOT_N)]


def arm(key, opt, tpl=False):
    """武装单个槽（tpl=True → 模板匹配；否则按实例 playerEventId）。"""
    h, base, st = _open()
    if h is None:
        print("!! 游戏已重启，钩子不在了")
        return False
    kt = 1 if tpl else 0
    ent = _read_slots(h, st)
    if ent is None:
        return False
    idx = None
    for k, s in enumerate(ent):
        if s[0] == 1 and s[1] == kt and s[2] == key:
            idx = k
            break
    if idx is None:
        for k, s in enumerate(ent):
            if s[0] == 0:
                idx = k
                break
    if idx is None:
        idx = 0
    slot = st["scratch"] + SLOT_BASE + idx * SLOT_SZ
    k32.WriteProcessMemory(h, ctypes.c_void_p(slot), struct.pack("<I", 0), 4, None)
    k32.WriteProcessMemory(h, ctypes.c_void_p(slot + 4), struct.pack("<III", kt, key, opt), 12, None)
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(slot), struct.pack("<I", 1), 4, None)
    print("武装%s %s: key=%d option=%d（槽%d）" % ("成功" if ok else "失败", "(模板)" if tpl else "", key, opt, idx))
    return bool(ok)


def set_slots(rules):
    """全表重写：rules = [(keyType, key, option), ...]。用于大脑批量刷新（实例+模板混合表）。"""
    h, base, st = _open()
    if h is None:
        return False
    base_a = st["scratch"] + SLOT_BASE
    for k in range(SLOT_N):
        k32.WriteProcessMemory(h, ctypes.c_void_p(base_a + k * SLOT_SZ), struct.pack("<I", 0), 4, None)
    for k, rule in enumerate(rules[:SLOT_N]):
        kt, key, opt = (list(rule) + [0, 0])[:3]
        ka = base_a + k * SLOT_SZ
        k32.WriteProcessMemory(h, ctypes.c_void_p(ka + 4), struct.pack("<III", kt, key, opt), 12, None)
        k32.WriteProcessMemory(h, ctypes.c_void_p(ka), struct.pack("<I", 1), 4, None)
    return True


def disarm(key=None, tpl=None):
    """清除武装槽：无参数=清空全部；key+可选 tpl 指定过滤。"""
    h, base, st = _open()
    if h is None:
        print("游戏已重启，无需处理")
        return 0
    ent = _read_slots(h, st)
    if ent is None:
        return 0
    cnt = 0
    for k, s in enumerate(ent):
        if s[0] != 1:
            continue
        if key is not None:
            kt = 1 if tpl else 0
            if not (s[1] == kt and s[2] == key):
                continue
        k32.WriteProcessMemory(
            h, ctypes.c_void_p(st["scratch"] + SLOT_BASE + k * SLOT_SZ), struct.pack("<I", 0), 4, None)
        cnt += 1
    print("解除武装 %d 项" % cnt)
    return 0


def revert():
    st = json.loads(STATE.read_text(encoding="utf-8"))
    h, pid, base = ce.open_game()
    fn = base + RVA_FN
    orig = bytes.fromhex(st.get("orig") or EXPECT_ORIG)
    b = ce.rpm(h, fn, 14)
    if b and b[:14] == orig:
        print("入口已是原始序言，无需还原")
        return 0
    old_prot = ctypes.c_uint32(0)
    k32.VirtualProtectEx(h, ctypes.c_void_p(fn), 64, 0x40, ctypes.byref(old_prot))
    handles = suspend_all_threads(pid)
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(fn), orig, len(orig), None)
    resume_all_threads(handles)
    k32.VirtualProtectEx(h, ctypes.c_void_p(fn), 64, old_prot.value, ctypes.byref(old_prot))
    print("已还原 rw88:", ok)
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 0
    m = args[0]
    if m == "install":
        return install(rw="--rw" in args)
    if m == "read":
        return read()
    if m == "arm" and len(args) >= 3:
        return 0 if arm(int(args[1]), int(args[2]), tpl=("--tpl" in args)) else 2
    if m == "disarm":
        if len(args) >= 2 and not args[1].startswith("--"):
            return disarm(int(args[1]), tpl=("--tpl" in args))
        return disarm()
    if m == "revert":
        return revert()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
