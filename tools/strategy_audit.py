# -*- coding: utf-8 -*-
"""Strategic audit: research / traditions / policies / economy / war.

Read-only. Shows whether the game AI's current choices match the steward's
policy profile, and where the AI is likely making a bad trade.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8")

import situation_reader as sr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "policy" / "tech_profile.json"
TRAD_ORDER = ROOT / "policy" / "tradition_order.json"
LOC = ROOT / "data" / "loc.json"
TECHS = Path(os.environ.get("STELLARIS_TECHS_JSON",
                            str(ROOT / "data" / "techs.json")))

MIL_CATS = {"particles", "voidcraft", "military_theory", "propulsion"}
KEYS = ("energy", "minerals", "food", "alloys", "consumer_goods",
        "physics_research", "society_research", "engineering_research",
        "unity", "influence")


def f(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def leaves_sum(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                leaves_sum(v, out)
            elif k in KEYS:
                try:
                    out[k] += float(v)
                except Exception:
                    pass
    elif isinstance(node, list):
        for v in node:
            leaves_sum(v, out)


def side_ids(w, key):
    out = []
    for p in sr.as_list(w.get(key)):
        if isinstance(p, dict) and p.get("country") is not None:
            out.append(str(p["country"]))
    return out


def tech_score(t, war, prof):
    cats = t.get("categories") or []
    w = sum(float((prof.get("category_weights") or {}).get(c, 0.8)) for c in cats)
    tier = t.get("tier")
    try:
        tier = float(str(tier).lstrip("@").replace("repeatableTechTier", "6"))
    except Exception:
        tier = 6.0
    sc = w + tier * float(prof.get("tier_weight", 0.6))
    if t.get("rare"):
        sc += float(prof.get("rare_bonus", 0.8))
    if war and MIL_CATS & set(cats):
        sc += 1.5
    return sc


def main():
    sv, gs = sr.load()
    c0 = (gs.get("country") or {}).get("0") or {}
    loc = load_json(LOC, {})
    prof = load_json(PROFILE, {})
    order = load_json(TRAD_ORDER, {}).get("order", [])
    techs = {t.get("key"): t for t in load_json(TECHS, []) if t.get("key")}

    wars = gs.get("war") or {}
    our_side, enemy_side = set(), set()
    our_ex = enemy_ex = 0.0
    for wid, w in wars.items():
        if not isinstance(w, dict):
            continue
        A, D = side_ids(w, "attackers"), side_ids(w, "defenders")
        if "0" not in A and "0" not in D:
            continue
        mine, theirs = (A, D) if "0" in A else (D, A)
        our_side.update(mine)
        enemy_side.update(theirs)
        ax, dx = f(w.get("attacker_war_exhaustion")), f(w.get("defender_war_exhaustion"))
        our_ex, enemy_ex = (ax, dx) if "0" in A else (dx, ax)
    war = bool(our_side)

    print("save:", Path(sv).name, "| date:", gs.get("date"), "| at_war:", war)
    print("=" * 62)

    # ---- research ----
    ts = c0.get("tech_status") or {}
    alts = ts.get("alternatives") or {}
    print("\n== research (game AI's current queue vs steward profile) ==")
    for area in ("physics", "society", "engineering"):
        q = ts.get(f"{area}_queue") or []
        cur = q[0].get("technology") if q and isinstance(q[0], dict) else None
        cand = [x for x in (alts.get(area) or []) if x in techs]
        scored = sorted(((tech_score(techs[x], war, prof), x) for x in cand), reverse=True)
        cur_sc = tech_score(techs[cur], war, prof) if cur in techs else None
        rank = next((i + 1 for i, (_, x) in enumerate(scored) if x == cur), None)
        cname = (techs.get(cur) or {}).get("zh", cur)
        print("  %-11s current=%s (score %s, rank %s/%d)"
              % (area, cname, ("%.1f" % cur_sc) if cur_sc is not None else "?",
                 rank or "?", len(scored)))
        for sc, x in scored[:3]:
            mark = " <= current" if x == cur else ""
            print("      %5.1f  %s%s" % (sc, (techs.get(x) or {}).get("zh", x), mark))
        if cur_sc is not None and scored and cur_sc < scored[0][0] - 0.5:
            print("      → 建议：当前研究不是评分最高项，优先 %s"
                  % (techs.get(scored[0][1]) or {}).get("zh", scored[0][1]))

    # ---- traditions ----
    cur_tr = set(c0.get("traditions") or [])
    adopted, finished = [], []
    for k in cur_tr:
        if k.endswith("_adopt"):
            tree = k[len("tr_"):-len("_adopt")]
            adopted.append(tree)
        if k.endswith("_finish"):
            finished.append(k[len("tr_"):-len("_finish")])
    print("\n== traditions ==")
    for tree in adopted:
        name = loc.get(f"tr_{tree}_adopt", tree)
        done = tree in finished
        rank = next((i + 1 for i, n in enumerate(order) if n and n in name), "?")
        print("  %-14s %s | order_rank=%s" % (name, "完成" if done else "未完成", rank))
    if len(adopted) > len(finished):
        print("  → 有未完成传统树，优先收尾（完成奖励通常强于再开一棵）")

    # ---- policies ----
    print("\n== policies ==")
    pol = {p.get("policy"): p.get("selected") for p in (c0.get("active_policies") or [])
           if isinstance(p, dict)}
    for k, v in pol.items():
        nm = loc.get(v, v)
        if k in ("war_philosophy", "diplomatic_stance", "orbital_bombardment",
                 "artificial_intelligence_policy", "resettlement"):
            print("  %-26s %s" % (k, nm))
    if war and pol.get("war_philosophy") == "defensive_wars":
        print("  → 战时仍为防御战争哲学：无法主动宣战/扩张，胜利后想割地需调整")
    if pol.get("orbital_bombardment") == "orbital_bombardment_indiscriminate":
        print("  → 无差别轰炸会破坏可占领星球，征服战建议选择性轰炸")

    # ---- economy ----
    b = ((c0.get("budget") or {}).get("current_month") or {})
    inc, exp = {k: 0.0 for k in KEYS}, {k: 0.0 for k in KEYS}
    leaves_sum(b.get("income") or {}, inc)
    leaves_sum(b.get("expenses") or {}, exp)
    print("\n== economy (monthly net) ==")
    for k in KEYS:
        net = inc[k] - exp[k]
        if abs(net) >= 1:
            print("  %-18s %+9.1f  (in %.1f / out %.1f)" % (k, net, inc[k], exp[k]))
    for k in ("energy", "food", "consumer_goods"):
        if inc[k] - exp[k] < 0:
            print("  → %s 月净支出为负，战时容易断供" % k)
            if k == "consumer_goods":
                print("     建议：补消费品建筑/岗位，或临时民用经济；不要切军事经济")
    if war and inc.get("alloys", 0) - exp.get("alloys", 0) < 0:
        print("  → 合金净支出为负：舰队/建筑会挤占，优先补合金产能")

    # ---- war summary ----
    if war:
        our_mil = sum(f((gs["country"].get(x) or {}).get("military_power")) for x in our_side
                      if isinstance(gs["country"].get(x), dict))
        enemy_mil = sum(f((gs["country"].get(x) or {}).get("military_power")) for x in enemy_side
                        if isinstance(gs["country"].get(x), dict))
        print("\n== war ==")
        print("  side military %.0f vs %.0f | exhaustion %.2f vs %.2f"
              % (our_mil, enemy_mil, our_ex, enemy_ex))
        print("  （详细局部兵力/集中度见 war_audit.py）")


if __name__ == "__main__":
    main()
