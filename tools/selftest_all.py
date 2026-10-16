# -*- coding: utf-8 -*-
"""全系统验收自检 v2（可随时运行；游戏开着时覆盖内存面，关着时覆盖离线面）

检查项（安全/无副作用；v2 起不再有"关窗"等破坏性动作）：
  1. 游戏连接 + 版本守卫
  2. 标志读取（human_ai / 暂停探针）
  3. 命令通道端到端（执行一个不存在的命令，期望 Unknown）
  4. 待决事件读取（evt_select.pending_events，只读）
  5. 资源连续性缓存（_brain_res.json → read_at+valid 实读校验）
  6. 存档解析（digest 一行）
  7. 后台进程（watchdog/brain/panel）
  8. 面板窗口（可见性；未运行时 SKIP）
  9. 决策数据层（event_index / loc / manifest 计数）
 10. 审计尾迹（_brain_audit.json 游标 + decisions.log 最近时间）
 11. MOD 状态（dlc_load.json + 启动器 DB；仅 WARN）
"""
import ctypes
import json
import sqlite3
import struct
import sys
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import console_exec as ce  # noqa: E402

PASS, FAIL, SKIP, WARN = "PASS", "FAIL", "SKIP", "WARN"
rows = []


def rec(name, status, detail=""):
    rows.append((name, status, detail))
    print(f"[{status}] {name}" + (f"  {detail}" if detail else ""))


def check_game():
    try:
        h, pid, base = ce.open_game()
    except Exception as e:
        rec("游戏连接+版本守卫", SKIP, f"游戏未运行（{e}）")
        return None, None, None
    rec("游戏连接+版本守卫", PASS, f"pid={pid} base=0x{base:X}")
    return h, pid, base


def check_flags(h, base):
    hai = ce.read_flag(h, base, ce.RVA_HUMAN_AI)
    paused = ce.read_pause(h, base)
    if hai is None or paused is None:
        rec("标志读取(托管/暂停)", FAIL, f"hai={hai} pause={paused}")
    else:
        rec("标志读取(托管/暂停)", PASS, f"托管={hai} 暂停={paused}")


def check_cmd_channel(h, base):
    r = ce.execute_command(h, base, "zzz_selftest_nonexistent_cmd")
    msg = (r.get("message") or "")[:40]
    if (not r.get("ok")) and ("Unknown" in msg or msg == ""):
        rec("命令通道端到端", PASS, f"回执={msg!r}")
    else:
        rec("命令通道端到端", FAIL, f"ok={r.get('ok')} msg={msg!r}")


def check_pending(h, base):
    try:
        import evt_select as es
        pend = es.pending_events(h, base)
        if pend is None:
            rec("待决事件读取", FAIL, "读取失败（gamestate 指针链异常）")
        else:
            show = [(x["iid"], x.get("name"), x["n_opts"], x["gate"]) for x in pend[:5]]
            rec("待决事件读取", PASS, f"{len(pend)} 个：{show}")
    except Exception as e:
        rec("待决事件读取", FAIL, str(e)[:80])


def check_rw88(h, base):
    try:
        import hook_rw88 as hr
        st = json.loads(hr.STATE.read_text(encoding="utf-8"))
        same = (int(st.get("base") or 0) == base and int(st.get("ver") or 0) == hr.STATE_VER)
        b = ce.rpm(h, base + hr.RVA_FN, 14)
        live = bool(b and b[:2] == b"\xFF\x25")
        tgt = struct.unpack_from("<Q", b, 6)[0] if (b and len(b) >= 14) else 0
        if live and same and tgt == int(st.get("cave") or 0):
            raw = ce.rpm(h, st["scratch"], 0x1D0)
            rwn = struct.unpack_from("<Q", raw, 0x28)[0]
            blk = struct.unpack_from("<Q", raw, 0x1C4)[0]
            nsl = sum(1 for k in range(24)
                      if struct.unpack_from("<I", raw, 0x38 + k * 16)[0] == 1)
            rec("内存改写钩子(rw88 v3)", PASS, f"在线 武装{nsl}条 改写{rwn} 拦截{blk}")
        elif not live:
            rec("内存改写钩子(rw88 v3)", SKIP, "未安装（离开模式时大脑自动安装）")
        else:
            rec("内存改写钩子(rw88 v3)", WARN,
                f"state 不符(base={hex(int(st.get('base') or 0))}/ver={st.get('ver')})，大脑下轮自愈")
    except Exception as e:
        rec("内存改写钩子(rw88 v3)", SKIP, str(e)[:80])


def check_res_continuity(h, base):
    f = ROOT / "tools" / "_brain_res.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        import game_reader as g
        v = g.read_at(h, d["base"]) if (h and d.get("base")) else None
        if v and g.valid(v):
            rec("资源连续性缓存", PASS, f"addr=0x{d['base']:X} energy={v.get('energy'):.0f}")
        elif h is None:
            rec("资源连续性缓存", SKIP, "游戏未运行，未实读校验")
        else:
            rec("资源连续性缓存", WARN, "实读未过校验（brain 下轮会自愈）")
    except Exception as e:
        rec("资源连续性缓存", SKIP, f"无缓存（{e}）")


def check_save():
    try:
        import situation_reader as sr
        sv, gs = sr.load()
        rec("存档解析", PASS, sr.digest_line(gs)[:78])
    except Exception as e:
        rec("存档解析", FAIL, str(e)[:70])


def check_procs():
    import psutil
    found = {"watchdog": 0, "brain": 0, "panel": 0}
    for p in psutil.process_iter(["name", "cmdline"]):
        nm = (p.info["name"] or "").lower()
        if "python" not in nm:
            continue
        try:
            cl = " ".join(p.info["cmdline"] or [])
        except Exception:
            continue
        if "hai_watch.py" in cl:
            found["watchdog"] += 1
        elif "brain.py" in cl:
            found["brain"] += 1
        elif "hai_ui.py" in cl:
            found["panel"] += 1
    ok = found["watchdog"] > 0 and found["brain"] > 0
    rec("后台进程", PASS if ok else FAIL,
        f"watchdog={found['watchdog']} brain={found['brain']} panel={found['panel']}")


def check_panel_window():
    user32 = ctypes.windll.user32
    res = []

    def cb(hwnd, lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if "AI 托管" in buf.value:
                res.append(hwnd)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    if res:
        rec("面板窗口", PASS, f"可见 hwnd=0x{res[0]:X}")
    else:
        rec("面板窗口", SKIP, "不可见（游戏未运行属正常）")


def check_data_layer():
    try:
        idx = json.loads((ROOT / "data" / "event_index.json").read_text(encoding="utf-8"))
        loc = json.loads((ROOT / "data" / "loc.json").read_text(encoding="utf-8"))
        rec("决策数据层", PASS, f"事件 {len(idx)} / 本地化 {len(loc)}")
    except Exception as e:
        rec("决策数据层", SKIP, f"可选数据未生成（{str(e)[:60]}）——运行 tools\\build_event_index.py 生成")
    try:
        man = json.loads((ROOT / "data" / "ai_decisions_manifest.json").read_text(encoding="utf-8"))
        st = man.get("stats", {}) if isinstance(man, dict) else {}
        rec("MOD 构建产物", PASS, f"v{man.get('version')} {man.get('method')}（已搁置，留档）")
    except Exception as e:
        rec("MOD 构建产物", SKIP, f"无（{e}）")


def check_audit_trail():
    try:
        f = ROOT / "tools" / "_brain_audit.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        rec("审计尾迹", PASS, f"游标 off={d.get('off')} 去重键 {len(d.get('seen', []))}")
    except Exception as e:
        rec("审计尾迹", SKIP, f"无（{e}）")
    try:
        lp = ROOT / "logs" / "decisions.log"
        last = lp.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-1]
        rec("决策日志", PASS, last[:90])
    except Exception as e:
        rec("决策日志", SKIP, "尚未运行（无日志文件——启动值守后生成）")


def check_advisor():
    try:
        import evt_analyze as ea
        import evt_decide as ed
        r1 = ea.analyze("utopia.1")
        r2 = ea.analyze("fallen_empires_tasks.2")
        ok1 = r1 and "error" not in r1 and r1.get("conf") == "low"      # 方向未判定→降级
        ok2 = r2 and "error" not in r2 and r2.get("conf") == "high" and r2.get("suggest") == 0
        d, why = ed.decide("fallen_empires_tasks.2", 2)
        ok3 = (d == 0 and "参谋" in (why or ""))                         # 决策器已采纳参谋
        if ok1 and ok2 and ok3:
            rec("事件参谋回归", PASS, "盲区降级 ✓ / 高置信 ✓ / 决策器采纳 ✓")
        else:
            rec("事件参谋回归", FAIL, f"utopia.1={r1.get('conf') if r1 else None} "
                                      f"fet.2={r2.get('conf') if r2 else None} decide={d},{why}")
    except Exception as e:
        rec("事件参谋回归", SKIP, f"数据缺失，跳过（{str(e)[:60]}）")


def check_mods():
    dl = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris" / "dlc_load.json"
    try:
        d = json.loads(dl.read_text(encoding="utf-8"))
        mods = d.get("enabled_mods", [])
        rec("MOD 启用清单", PASS, f"{mods}")
    except Exception as e:
        rec("MOD 启用清单", SKIP, str(e)[:60])
    try:
        db = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris" / "launcher-v2.sqlite"
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows_ = con.execute("SELECT gameRegistryId, m.displayName, pm.enabled FROM mods m "
                            "LEFT JOIN playsets_mods pm ON pm.modId = m.id").fetchall()
        ps = con.execute("SELECT isActive FROM playsets").fetchall()
        con.close()
        rec("启动器 MOD 状态", PASS, f"playset_active={ps} {rows_}")
    except Exception as e:
        rec("启动器 MOD 状态", WARN, str(e)[:70])


def main():
    print("==== AI 托管全系统自检 v2 ====")
    h, pid, base = check_game()
    if h:
        check_flags(h, base)
        check_cmd_channel(h, base)
        check_pending(h, base)
        check_rw88(h, base)
        check_res_continuity(h, base)
    else:
        check_res_continuity(None, None)
    check_save()
    check_procs()
    check_panel_window()
    check_data_layer()
    check_audit_trail()
    check_advisor()
    check_mods()
    fails = [r for r in rows if r[1] == FAIL]
    print(f"\n结论：{len(rows)} 项检查，FAIL {len(fails)} 项"
          + ("，全部通过 ✔" if not fails else " —— 需修复：" + "，".join(r[0] for r in fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
