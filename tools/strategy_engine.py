# -*- coding: utf-8 -*-
"""Strategy engine v1: counter-cyclical economic policy automation.

Reads the latest save, decides:
  - at war + consumer goods surplus > 300 -> military economy
  - consumer goods deficit + alloy surplus > 200 -> civilian economy
  - otherwise -> balanced economy

Commands:
  python strategy_engine.py status   # show nets / mode / last applied
  python strategy_engine.py apply    # apply if mode changed
  python strategy_engine.py on|off   # enable/disable auto-apply by brain
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8")

import situation_reader as sr  # noqa: E402
import strategy_audit as sa  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "tools" / "_strategy_state.json"
AUTO = ROOT / "tools" / "_strategy_auto.flag"
EVENT = {"military": "ai_steward_war.20",
         "civilian": "ai_steward_war.21",
         "balanced": "ai_steward_war.22"}


def snapshot():
    sv, gs = sr.load()
    c0 = (gs.get("country") or {}).get("0") or {}
    b = ((c0.get("budget") or {}).get("current_month") or {})
    inc = {k: 0.0 for k in sa.KEYS}
    exp = {k: 0.0 for k in sa.KEYS}
    sa.leaves_sum(b.get("income") or {}, inc)
    sa.leaves_sum(b.get("expenses") or {}, exp)
    cg = inc["consumer_goods"] - exp["consumer_goods"]
    alloy = inc["alloys"] - exp["alloys"]
    own_wars = 0
    for _wid, w in (gs.get("war") or {}).items():
        if not isinstance(w, dict):
            continue
        ids = sa.side_ids(w, "attackers") + sa.side_ids(w, "defenders")
        if "0" in ids:
            own_wars += 1
    if own_wars and cg > 300:
        mode = "military"
    elif cg < 0 and alloy > 200:
        mode = "civilian"
    else:
        mode = "balanced"
    return {"save": Path(sv).name, "date": gs.get("date"), "own_wars": own_wars,
            "cg": cg, "alloy": alloy, "mode": mode}


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def show(s):
    st = load_state()
    print("save:", s["save"], "| date:", s["date"], "| wars:", s["own_wars"])
    print("consumer_goods net=%+.1f | alloys net=%+.1f" % (s["cg"], s["alloy"]))
    print("recommended:", s["mode"], "| last applied:", st.get("mode", "?"),
          "| auto:", "ON" if AUTO.exists() else "OFF")


def apply():
    s = snapshot()
    st = load_state()
    show(s)
    if st.get("mode") == s["mode"]:
        print("no change")
        return
    import console_exec as ce
    h, pid, base = ce.open_game()
    ev = EVENT[s["mode"]]
    r = ce.execute_command(h, base, "event " + ev)
    print("apply %s -> %s ok=%s message=%r"
          % (s["mode"], ev, r.get("ok"), r.get("message")))
    if r.get("ok"):
        STATE.write_text(json.dumps({"mode": s["mode"], "date": s["date"],
                                     "cg": s["cg"], "alloy": s["alloy"]}),
                         encoding="utf-8")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    if mode == "status":
        show(snapshot())
    elif mode == "apply":
        apply()
    elif mode == "on":
        AUTO.touch()
        print("strategy auto: ON")
    elif mode == "off":
        if AUTO.exists():
            AUTO.unlink()
        print("strategy auto: OFF")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
