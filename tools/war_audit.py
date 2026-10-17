# -*- coding: utf-8 -*-
"""War/strategy audit from the latest save.

Answers: are our fleets concentrated? are we outnumbered locally? is our side
winning on exhaustion? what should the steward do (defend / concentrate / attack / peace)?
Read-only.
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8")

import situation_reader as sr  # noqa: E402


def f(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def cname(gs, cid):
    c = (gs.get("country") or {}).get(str(cid))
    if not isinstance(c, dict):
        return str(cid)
    n = c.get("name")
    if isinstance(n, dict):
        return str(n.get("key") or cid)[:28]
    return str(n or cid)[:28]


def side_ids(w, key):
    out = []
    for p in sr.as_list(w.get(key)):
        if isinstance(p, dict) and p.get("country") is not None:
            out.append(str(p["country"]))
    return out


def main():
    sv, gs = sr.load()
    countries = gs.get("country") or {}
    fleets = gs.get("fleet") or {}
    wars = gs.get("war") or {}

    # fleet -> owner
    owner = {}
    for cid, c in countries.items():
        if not isinstance(c, dict):
            continue
        fm = c.get("fleets_manager") or {}
        for x in (fm.get("owned_fleets") or []):
            if isinstance(x, dict) and x.get("fleet") is not None:
                owner[str(x["fleet"])] = cid

    # system -> starbase owner
    sysown = {}
    for fid, cid in owner.items():
        fl = fleets.get(fid)
        if not isinstance(fl, dict) or fl.get("ship_class") != "shipclass_starbase":
            continue
        sid = ((fl.get("movement_manager") or {}).get("coordinate") or {}).get("origin")
        if sid:
            sysown[str(sid)] = cid

    print("save:", Path(sv).name, "| date:", gs.get("date"))
    c0 = countries.get("0") or {}
    print("us:", cname(gs, 0),
          "mil=%.0f" % f(c0.get("military_power")),
          "fleet_size=%.0f" % f(c0.get("fleet_size")),
          "used_naval=%.0f" % f(c0.get("used_naval_capacity")))

    our_side, enemy_side = set(), set()
    print("\n== wars involving us ==")
    for wid, w in wars.items():
        if not isinstance(w, dict):
            continue
        A, D = side_ids(w, "attackers"), side_ids(w, "defenders")
        if "0" not in A and "0" not in D:
            continue
        mine, theirs = (A, D) if "0" in A else (D, A)
        our_side.update(mine)
        enemy_side.update(theirs)
        mp = sum(f((countries.get(x) or {}).get("military_power")) for x in mine
                 if isinstance(countries.get(x), dict))
        ep = sum(f((countries.get(x) or {}).get("military_power")) for x in theirs
                 if isinstance(countries.get(x), dict))
        ax = f(w.get("attacker_war_exhaustion"))
        dx = f(w.get("defender_war_exhaustion"))
        our_ex, their_ex = (ax, dx) if "0" in A else (dx, ax)
        goal = w.get("attacker_war_goal") if "0" in A else w.get("defender_war_goal")
        print("war %-9s %s | side_mil %.0f vs %.0f | exhaustion %.2f vs %.2f | goal=%s"
              % (wid, w.get("name", {}).get("key") if isinstance(w.get("name"), dict) else "?",
                 mp, ep, our_ex, their_ex,
                 goal.get("type") if isinstance(goal, dict) else "?"))
    if not our_side:
        print("no war involving us")
        return

    # fleets
    def fleet_rows(owners):
        rows = []
        for fid, cid in owner.items():
            if cid not in owners:
                continue
            fl = fleets.get(fid)
            if not isinstance(fl, dict) or fl.get("ship_class") != "shipclass_military":
                continue
            mm = fl.get("movement_manager") or {}
            sid = str((mm.get("coordinate") or {}).get("origin"))
            if sid in ("4294967295", "None", ""):
                continue
            rows.append({"fid": fid, "cid": cid, "power": f(fl.get("military_power")),
                         "sys": sid, "state": mm.get("state"),
                         "stance": fl.get("fleet_stance")})
        return rows

    ours = fleet_rows({"0"})
    allies = fleet_rows(our_side - {"0"})
    enemies = fleet_rows(enemy_side)
    print("\n== our military fleets ==")
    for r in sorted(ours, key=lambda x: -x["power"]):
        print("  %9.1f  sys=%-5s owner=%-5s stance=%-10s move=%-12s"
              % (r["power"], r["sys"], sysown.get(r["sys"], "?"),
                 r["stance"], r["state"]))
    print("our total=%.1f | allies nearby total=%.1f | enemy total=%.1f"
          % (sum(r["power"] for r in ours), sum(r["power"] for r in allies),
             sum(r["power"] for r in enemies)))

    # system balance
    bal = defaultdict(lambda: {"us": 0.0, "ally": 0.0, "enemy": 0.0, "usn": 0, "an": 0, "en": 0})
    for r in ours:
        bal[r["sys"]]["us"] += r["power"]
        bal[r["sys"]]["usn"] += 1
    for r in allies:
        bal[r["sys"]]["ally"] += r["power"]
        bal[r["sys"]]["an"] += 1
    for r in enemies:
        bal[r["sys"]]["enemy"] += r["power"]
        bal[r["sys"]]["en"] += 1
    contested = [(s, v) for s, v in bal.items() if v["en"] and (v["usn"] + v["an"])]
    contested.sort(key=lambda kv: -(kv[1]["enemy"] - kv[1]["us"] - kv[1]["ally"]))
    print("\n== contested systems (enemy vs friendly local power) ==")
    for s, v in contested[:12]:
        friend = v["us"] + v["ally"]
        print("  sys=%-5s owner=%-5s us=%8.0f(%d) ally=%8.0f(%d) enemy=%8.0f(%d) ratio=%.2f"
              % (s, sysown.get(s, "?"), v["us"], v["usn"], v["ally"], v["an"],
                 v["enemy"], v["en"], friend / v["enemy"] if v["enemy"] else 0))

    # concentration
    bysys = defaultdict(float)
    for r in ours:
        bysys[r["sys"]] += r["power"]
    top = max(bysys.values()) if bysys else 0.0
    total = sum(bysys.values()) or 1.0
    print("\n== concentration ==")
    print("  systems=%d | largest group=%.0f%% of our power"
          % (len(bysys), 100.0 * top / total))

    # recommendation
    our_mil = sum(f((countries.get(x) or {}).get("military_power")) for x in our_side
                  if isinstance(countries.get(x), dict))
    enemy_mil = sum(f((countries.get(x) or {}).get("military_power")) for x in enemy_side
                    if isinstance(countries.get(x), dict))
    ratio = our_mil / enemy_mil if enemy_mil else 0
    danger = [s for s, v in contested
              if s not in ("4294967295", "None", "")
              and v["enemy"] > 1.5 * (v["us"] + v["ally"])]
    enemy_ex = 0.0
    our_ex = 0.0
    for wid, w in wars.items():
        if not isinstance(w, dict):
            continue
        A = side_ids(w, "attackers")
        if "0" not in A and "0" not in side_ids(w, "defenders"):
            continue
        ax, dx = f(w.get("attacker_war_exhaustion")), f(w.get("defender_war_exhaustion"))
        our_ex, enemy_ex = (ax, dx) if "0" in A else (dx, ax)
    print("\n== recommendation ==")
    print("  side power ratio=%.2f | exhaustion %.2f vs %.2f | local danger=%s"
          % (ratio, our_ex, enemy_ex, danger[:6]))
    if enemy_ex >= 5 and ratio >= 2:
        print("  PRESS/PEACE: enemy is collapsed on exhaustion; take the war goal or status quo,"
              " avoid unnecessary fleet losses.")
    elif ratio < 0.8 or our_ex > enemy_ex + 2:
        print("  DEFEND: do not push; concentrate at capital/chokepoint, avoid enemy doomstacks.")
    elif ratio > 1.25 and not danger:
        print("  ATTACK: side has advantage; push nearest weak enemy system after concentrating.")
    else:
        print("  HOLD: keep fleets concentrated, engage only locally favorable fights.")


if __name__ == "__main__":
    main()
