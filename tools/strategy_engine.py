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
    dyn = sa.load_json(ROOT / "policy" / "strategy_dynamic.json", {})
    cg_income = max(1.0, inc["consumer_goods"])
    cg_safe = max(100.0, cg_income * float(dyn.get("cg_safe_ratio", 0.15)))
    mil_thr = cg_income * float(dyn.get("military_econ_cg_ratio", 0.25))
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
        mode = "military" if cg >= cg_safe else "balanced"
    elif cur_mode == "civilian":
        mode = "civilian" if cg <= cg_safe else "balanced"
    else:
        if own_wars and cg > mil_thr:
            mode = "military"
        elif cg < 0:
            mode = "civilian"
        else:
            mode = "balanced"
    ov = c0.get("overlord")
    ov_mil = mine = 0.0
    loyalty = sa.f(c0.get("loyalty"))
    ov_ex = 0.0
    conserve = False
    if ov and str(ov) not in ("", "none", "4294967295"):
        ovc = (gs.get("country") or {}).get(str(ov)) or {}
        ov_mil = sa.f(ovc.get("military_power"))
        mine = sa.f(c0.get("military_power"))
        conserve = bool(loyalty < -50 and ov_mil
                        and mine < ov_mil * float(dyn.get("conserve_ratio", 0.5)))
        for w in (gs.get("war") or {}).values():
            if not isinstance(w, dict):
                continue
            A, D = sa.side_ids(w, "attackers"), sa.side_ids(w, "defenders")
            if str(ov) in A:
                ov_ex = max(ov_ex, sa.f(w.get("attacker_war_exhaustion")))
            elif str(ov) in D:
                ov_ex = max(ov_ex, sa.f(w.get("defender_war_exhaustion")))
    ratio = (mine / ov_mil) if ov_mil else 0.0
    ren_ratio = float(dyn.get("renegotiate_ratio", 0.6))
    ind_ratio = float(dyn.get("independence_ratio", 0.9))
    renegotiate_ready = ratio >= ren_ratio or (ov_ex >= 20 and ratio >= 0.25)
    independence_ready = ratio >= ind_ratio or (ov_ex >= 50 and ratio >= 0.5)
    return {"save": Path(sv).name, "date": gs.get("date"), "own_wars": own_wars,
            "cg": cg, "alloy": alloy, "mode": mode,
            "cg_safe": cg_safe, "mil_thr": mil_thr,
            "overlord": str(ov) if ov else None, "ov_mil": ov_mil,
            "our_mil": mine, "loyalty": loyalty, "conserve": conserve,
            "ratio": ratio, "overlord_exhaustion": ov_ex,
            "renegotiate_ratio": ren_ratio, "independence_ratio": ind_ratio,
            "renegotiate_ready": renegotiate_ready,
            "independence_ready": independence_ready}


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def show(s):
    st = load_state()
    print("save:", s["save"], "| date:", s["date"], "| wars:", s["own_wars"])
    print("consumer_goods net=%+.1f (safe %.0f / military %.0f) | alloys net=%+.1f"
          % (s["cg"], s["cg_safe"], s["mil_thr"], s["alloy"]))
    print("recommended:", s["mode"], "| last applied:", st.get("mode", "?"),
          "| auto:", "ON" if AUTO.exists() else "OFF")
    if s.get("overlord"):
        print("overlord=%s | ours=%.0f / overlord=%.0f | loyalty=%.0f | conserve=%s"
              % (s["overlord"], s["our_mil"], s["ov_mil"], s["loyalty"],
                 "ON" if s["conserve"] else "OFF"))
        print("ratio=%.3f | overlord_exhaustion=%.1f | renegotiate_ready=%s | independence_ready=%s"
              % (s["ratio"], s["overlord_exhaustion"],
                 "YES" if s["renegotiate_ready"] else "no",
                 "YES" if s["independence_ready"] else "no"))


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


def independence(yes=False):
    s = snapshot()
    show(s)
    if not s.get("overlord"):
        print("no overlord")
        return
    if not s["independence_ready"] and "--force" not in sys.argv:
        print("not ready (ratio %.3f < %.2f); use --force only if you accept the risk"
              % (s["ratio"], s["independence_ratio"]))
        return
    cmd = "war 0 %s wg_independence" % s["overlord"]
    print("declare independence:", cmd)
    if not yes:
        print("dry-run; add --yes to execute")
        return
    import console_exec as ce
    h, pid, base = ce.open_game()
    r = ce.execute_command(h, base, cmd)
    print("war -> ok=%s message=%r" % (r.get("ok"), r.get("message")))


def renegotiate(yes=False):
    s = snapshot()
    show(s)
    if not s["renegotiate_ready"] and "--force" not in sys.argv:
        print("not ready (ratio %.3f < %.2f); use --force only if you accept the risk"
              % (s["ratio"], s["renegotiate_ratio"]))
        return
    print("improve agreement: expand_with_tithe / join overlord wars defensive / vote yes")
    if not yes:
        print("dry-run; add --yes to execute")
        return
    import console_exec as ce
    h, pid, base = ce.open_game()
    r = ce.execute_command(h, base, "event ai_steward_war.25")
    print("event ai_steward_war.25 -> ok=%s message=%r" % (r.get("ok"), r.get("message")))


def build_cg(yes=False):
    s = snapshot()
    show(s)
    if s["cg"] >= 0:
        print("consumer goods net is non-negative; no factory-world change needed")
        return
    print("set the largest non-capital colony to factory world (col_factory)")
    if not yes:
        print("dry-run; add --yes to execute")
        return
    import console_exec as ce
    h, pid, base = ce.open_game()
    r = ce.execute_command(h, base, "event ai_steward_war.26")
    print("event ai_steward_war.26 -> ok=%s message=%r" % (r.get("ok"), r.get("message")))


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
    elif mode == "independence":
        independence("--yes" in sys.argv)
    elif mode == "renegotiate":
        renegotiate("--yes" in sys.argv)
    elif mode == "build-cg":
        build_cg("--yes" in sys.argv)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
