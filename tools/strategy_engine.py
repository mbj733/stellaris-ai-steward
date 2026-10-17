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
    # Hysteresis: do not flip back the moment the deficit disappears.
    # civilian -> balanced only with a healthy CG buffer; balanced -> civilian on deficit;
    # balanced -> military only at war with a large CG surplus.
    cur_mode = load_state().get("mode")
    if cur_mode == "military":
        mode = "military" if cg >= 200 else "balanced"
    elif cur_mode == "civilian":
        mode = "civilian" if cg <= 200 else "balanced"
    else:
        if own_wars and cg > 300:
            mode = "military"
        elif cg < 0:
            mode = "civilian"
        else:
            mode = "balanced"
    ov = c0.get("overlord")
    ov_mil = mine = 0.0
    loyalty = sa.f(c0.get("loyalty"))
    conserve = False
    if ov and str(ov) not in ("", "none", "4294967295"):
        ovc = (gs.get("country") or {}).get(str(ov)) or {}
        ov_mil = sa.f(ovc.get("military_power"))
        mine = sa.f(c0.get("military_power"))
        conserve = bool(loyalty < -50 and ov_mil and mine < ov_mil * 0.5)
    return {"save": Path(sv).name, "date": gs.get("date"), "own_wars": own_wars,
            "cg": cg, "alloy": alloy, "mode": mode,
            "overlord": str(ov) if ov else None, "ov_mil": ov_mil,
            "our_mil": mine, "loyalty": loyalty, "conserve": conserve}


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
    if s.get("overlord"):
        print("overlord=%s | ours=%.0f / overlord=%.0f | loyalty=%.0f | conserve=%s"
              % (s["overlord"], s["our_mil"], s["ov_mil"], s["loyalty"],
                 "ON" if s["conserve"] else "OFF"))


def apply():
    s = snapshot()
    st = load_state()
    show(s)
    changed = False
    import console_exec as ce
    h = pid = base = None
    if st.get("mode") != s["mode"]:
        h, pid, base = ce.open_game()
        ev = EVENT[s["mode"]]
        r = ce.execute_command(h, base, "event " + ev)
        print("apply %s -> %s ok=%s message=%r"
              % (s["mode"], ev, r.get("ok"), r.get("message")))
        if r.get("ok"):
            changed = True
    if bool(st.get("conserve")) != bool(s["conserve"]):
        if h is None:
            h, pid, base = ce.open_game()
        ev = "ai_steward_war.23" if s["conserve"] else "ai_steward_war.24"
        r = ce.execute_command(h, base, "event " + ev)
        print("conserve %s -> %s ok=%s message=%r"
              % ("ON" if s["conserve"] else "OFF", ev, r.get("ok"), r.get("message")))
        if r.get("ok"):
            changed = True
    if changed:
        STATE.write_text(json.dumps({"mode": s["mode"], "conserve": s["conserve"],
                                     "date": s["date"], "cg": s["cg"],
                                     "alloy": s["alloy"]}), encoding="utf-8")
    else:
        print("no change")


def research(area="physics", yes=False):
    """Optional 'oracle' mode: grant the audit's top tech instantly."""
    sv, gs = sr.load()
    c0 = (gs.get("country") or {}).get("0") or {}
    ts = c0.get("tech_status") or {}
    alts = (ts.get("alternatives") or {}).get(area) or []
    techs = {t.get("key"): t for t in sa.load_json(sa.TECHS, []) if t.get("key")}
    prof = sa.load_json(sa.PROFILE, {})
    loc = sa.load_json(sa.LOC, {})
    war = bool(c0.get("overlord")) or any(
        isinstance(w, dict) and ("0" in sa.side_ids(w, "attackers") or "0" in sa.side_ids(w, "defenders"))
        for w in (gs.get("war") or {}).values())
    cand = [x for x in alts if x in techs]
    scored = sorted(((sa.tech_score(techs[x], war, prof), x) for x in cand), reverse=True)
    q = ts.get(f"{area}_queue") or []
    cur = q[0].get("technology") if q and isinstance(q[0], dict) else None
    print("area:", area, "| current:", loc.get(cur, cur))
    for sc, x in scored[:5]:
        print("  %5.1f  %s  %s" % (sc, loc.get(x, x), x))
    if not scored:
        print("no alternatives")
        return
    top = scored[0][1]
    print("recommended:", loc.get(top, top), "(", top, ")")
    if not yes:
        print("dry-run; add --yes to grant it (oracle/cheat mode)")
        return
    import console_exec as ce
    h, pid, base = ce.open_game()
    r = ce.execute_command(h, base, "research_technology " + top)
    print("research_technology %s -> ok=%s message=%r" % (top, r.get("ok"), r.get("message")))


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
    elif mode == "research":
        area = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "physics"
        research(area, "--yes" in sys.argv)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
