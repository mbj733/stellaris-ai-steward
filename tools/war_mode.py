# -*- coding: utf-8 -*-
"""战争组件控制器（需已安装 ai_steward_war 并重启游戏）。

  python war_mode.py status   查看最新存档里的进攻开关/战争/舰队状态（只读）
  python war_mode.py on       开启进攻模式（事件 ai_steward_war.10）
  python war_mode.py off      关闭进攻模式（事件 ai_steward_war.11）
  python war_mode.py verify   验战争组件是否加载（error.log + 存档舰队状态）
"""
import sys
import json
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8")

DOC = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris"
FLAG = "ai_steward_war_offensive"
ENTRY = "mod/ai_steward_war.mod"


def mod_enabled():
    try:
        cfg = json.loads((DOC / "dlc_load.json").read_text(encoding="utf-8"))
        return ENTRY in (cfg.get("enabled_mods") or [])
    except Exception:
        return False


def snapshot():
    import situation_reader as sr

    sv, gs = sr.load()
    c0 = gs["country"]["0"]
    flags = c0.get("flags") or {}
    wars = gs.get("war") or {}
    own_wars = 0
    for w in wars.values():
        if not isinstance(w, dict):
            continue
        ids = []
        for key in ("attackers", "defenders"):
            for p in sr.as_list(w.get(key)):
                ids.append(str(p.get("country")) if isinstance(p, dict) else str(p))
        if "0" in ids:
            own_wars += 1
    fl = gs["fleet"]
    c0fm = c0.get("fleets_manager") or {}
    owned = [str(x.get("fleet")) for x in (c0fm.get("owned_fleets") or [])
             if isinstance(x, dict) and x.get("fleet") is not None]
    stance, move, military = Counter(), Counter(), 0
    for fid in owned:
        f = fl.get(fid)
        if not isinstance(f, dict) or f.get("ship_class") != "shipclass_military":
            continue
        military += 1
        stance[str(f.get("fleet_stance"))] += 1
        move[str((f.get("movement_manager") or {}).get("state"))] += 1
    return {
        "save": Path(sv).name,
        "date": gs.get("date"),
        "offensive": FLAG in flags,
        "own_wars": own_wars,
        "wars": len(wars),
        "military": military,
        "stance": dict(stance),
        "move": dict(move),
    }


def show():
    s = snapshot()
    print("save: %s | date: %s" % (s["save"], s["date"]))
    print("战争组件已挂载:", "是" if mod_enabled() else "否")
    print("进攻模式:", "开" if s["offensive"] else "关")
    print("我方参战: %d 处 | 全银河战争: %d 处" % (s["own_wars"], s["wars"]))
    print("机动军用舰队: %d 支 | stance=%s | move=%s"
          % (s["military"], s["stance"], s["move"]))


def toggle(on):
    import console_exec as ce

    h, pid, base = ce.open_game()
    ev = "ai_steward_war.10" if on else "ai_steward_war.11"
    r = ce.execute_command(h, base, "event " + ev)
    print("执行 event %s -> ok=%s message=%r" % (ev, r.get("ok"), r.get("message")))
    print("（若提示事件不存在：mod 尚未加载，需要重启游戏）")
    show()


def verify():
    static_ok = True
    try:
        import validate_war_mod as vwm
        problems = vwm.validate()
        print("静态校验:", "PASS" if not problems else "FAIL")
        for p in problems:
            print("  -", p)
        static_ok = not problems
    except Exception as e:
        print("静态校验: 跳过（%r）" % (e,))
    log = DOC / "logs" / "error.log"
    hits = []
    if log.exists():
        with log.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "ai_steward_war" in line or "AI Steward: War" in line:
                    hits.append(line.rstrip())
    print("战争组件已挂载:", "是" if mod_enabled() else "否")
    print("error.log 中 ai_steward_war 相关行:", len(hits))
    for line in hits[-10:]:
        print(" ", line[:200])
    s = snapshot()
    print("save: %s | date: %s" % (s["save"], s["date"]))
    print("进攻模式:", "开" if s["offensive"] else "关")
    print("我方参战: %d 处 | 机动军用舰队: %d 支 | stance=%s | move=%s"
          % (s["own_wars"], s["military"], s["stance"], s["move"]))
    ok = True
    if not static_ok:
        print("[FAIL] 战争组件静态校验未通过")
        ok = False
    if not mod_enabled():
        print("[FAIL] mod 未挂载")
        ok = False
    if hits:
        print("[FAIL] error.log 出现战争组件脚本错误")
        ok = False
    if s["own_wars"] and s["military"] and not s["stance"].get("aggressive"):
        print("[WAIT] 仍在战争但尚无 aggressive：可能尚未到月度脉冲/未重启")
        ok = False
    print("[PASS] 战争组件已加载，无脚本错误" if ok else "[CHECK] 见上方条目")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    if mode == "status":
        show()
    elif mode in ("on", "off"):
        toggle(mode == "on")
    elif mode == "verify":
        verify()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
