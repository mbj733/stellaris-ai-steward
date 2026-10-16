# -*- coding: utf-8 -*-
"""事件参谋 v1：基于选项效果的启发式评分器（离线文本分析，零游戏风险）

输入：事件名（在 data\\event_index.json 收录）→ 解析原始定义（含参数）→
对每个选项给出 {score, confidence, reasons}，并给出建议选项。

评分规则（v1，粗糙但方向明确；命中即记理由）：
  +4  add_relic / add_specimen / give_technology / add_trait_species
  +3  add_modifier（永久或长时加成）、add_planet_modifier、add_deposit、
      add_monthly_resource_mult（持续月收益）
  +2  enable_special_project、unlock_*、add_techprogress、research_* 加成类
  +1  add_resource（一次性资源）、add_opinion_modifier、add_fleet、create_*、
      add_leader、gain_*
  -1  remove_*（不含 remove_country_flag 等流程标记）、disband_*
  -2  kill_* / destroy_* / lose_*（损失类）
   0  其余（触发器/流程/标记/事件调度等）
建议 = 最高分；置信 = 分差 ≥ 3 为 high，否则 low。

用法：
  python evt_analyze.py <event_id> [<event_id> ...]   # 单个/批量分析
  python evt_analyze.py --scan                        # 全库扫描：策略分歧统计
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

AP = Path(__file__).resolve().parent.parent
GAME = Path(r"<改成你的游戏安装路径>")

P2 = None
try:
    _modgen_path = Path(__file__).resolve().parent / "make_ai_decisions_mod.py"
    if _modgen_path.exists():
        spec = importlib.util.spec_from_file_location("modgen", str(_modgen_path))
        modgen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modgen)
        P2 = modgen.P2
except Exception:
    P2 = None  # 降级：缺解析器时仍可运行（分析能力受限，不崩溃）

# 中性键（不计分、不列理由）
NEUTRAL = {
    "name", "ai_chance", "trigger", "allow", "hidden_effect", "custom_tooltip",
    "show_sound", "picture", "desc", "title", "id", "factor", "days", "if", "else",
    "else_if", "limit", "AND", "OR", "NOT", "nor", "switch", "value", "modifier",
    "resource", "min", "max", "mult", "who", "target", "owner", "type", "key",
    "location", "set_variable", "change_variable", "variable", "tooltip", "flag",
    "city_level", "portrait", "room", "planet_background", "graphical_culture",
}

POS4 = {"add_relic", "add_specimen", "give_technology", "add_trait_species",
        "add_techprogress", "unlock_technology"}
POS3 = {"add_deposit", "add_monthly_resource_mult",
        "add_monthly_resource"}
UNCERTAIN = {"add_planet_modifier", "add_country_modifier",
             "add_pop_group_modifier", "create_fleet", "add_fleet"}
POS2 = {"enable_special_project", "unlock_decision", "unlock_edict", "research_technology",
        "add_research_option", "start_situation", "add_anomaly", "add_archaeological_site"}
POS1 = {"add_opinion_modifier", "add_leader",
        "gain_resource", "gain_ship", "add_experience", "add_command_capacity"}
NEG1 = {"remove_fleet", "remove_leader", "disband_fleet",
        "remove_planet_modifier", "remove_deposit", "remove_relic"}
NEG2 = {"kill_leader", "kill_pop", "destroy_fleet", "destroy_planet", "lose_leader",
        "kill_army", "destroy_station", "scrap_fleet"}


def _walk_keys(blk, bag, depth=0):
    if depth > 8 or blk is None or blk[0] != "blk":
        return
    for (typ, k, op, v) in blk[3]:
        if typ == "kv":
            if k not in NEUTRAL:
                bag.append(k)
            if v[0] == "blk":
                _walk_keys(v, bag, depth + 1)
        elif typ == "k" and k not in NEUTRAL:
            bag.append(k)


_INDEX = None
_FILE_CACHE = {}
_CTX_CACHE = {"t": 0, "ctx": None}
_MOD_IDX = None


def _mod_index():
    global _MOD_IDX
    if _MOD_IDX is None:
        try:
            _MOD_IDX = json.loads((AP / "data" / "modifier_index.json").read_text(encoding="utf-8"))
        except Exception:
            _MOD_IDX = {}
    return _MOD_IDX


def _collect_mod_refs(blk, out, depth=0):
    """递归收集 add_modifier / remove_modifier 引用：[(动作, 名称, days)]"""
    if depth > 10 or blk is None or blk[0] != "blk":
        return
    for (typ, k, op, v) in blk[3]:
        if typ != "kv" or v is None or v[0] != "blk":
            continue
        if k in ("add_modifier", "remove_modifier"):
            name = None
            days = None
            for (t2, k2, o2, v2) in v[3]:
                if t2 == "kv" and k2 == "modifier" and v2 and v2[0] in ("tok", "str"):
                    name = v2[3]
                if t2 == "kv" and k2 == "days" and v2 and v2[0] in ("tok", "str"):
                    try:
                        days = float(v2[3])
                    except Exception:
                        pass
            out.append((k, name, days))
        else:
            _collect_mod_refs(v, out, depth + 1)


def _mod_duration_factor(days):
    if days is None:
        return 0.7
    if days < 0:
        return 1.0
    if days >= 3600:
        return 0.9
    if days >= 1000:
        return 0.7
    return 0.5

RES_NAMES = {"energy", "minerals", "food", "physics_research", "society_research",
             "engineering_research", "influence", "unity", "trade", "consumer_goods",
             "alloys", "minor_artifacts"}
CAPS = {"energy": 25000, "minerals": 25000, "food": 25000, "influence": 1000}
IMPORTANCE = {"alloys": 1.3, "unity": 1.1, "physics_research": 1.2,
              "society_research": 1.2, "engineering_research": 1.2,
              "influence": 1.0, "energy": 1.0, "minerals": 1.0, "food": 0.8,
              "trade": 0.9, "consumer_goods": 0.9, "minor_artifacts": 1.1}


def load_context(max_age=600):
    """态势上下文：live 资源（_brain_res.json）+（可选）存档战争数。带 TTL 缓存。"""
    import time
    if _CTX_CACHE["ctx"] is not None and time.time() - _CTX_CACHE["t"] < max_age:
        return _CTX_CACHE["ctx"]
    ctx = {"resources": {}, "wars": None, "year": None}
    try:
        rp = Path(__file__).resolve().parent / "_brain_res.json"
        d = json.loads(rp.read_text(encoding="utf-8"))
        ctx["resources"] = dict(d.get("vals", {}))
    except Exception:
        pass
    try:
        import situation_reader as sr
        _sv, gs = sr.load()
        import re as _re
        m = _re.search(r"(\d{4})\.\d{2}\.\d{2}", str(_sv))
        if m:
            ctx["year"] = int(m.group(1))
        wars = gs.get("war", {})
        n = 0
        if isinstance(wars, dict):
            for _wid, w in wars.items():
                if not isinstance(w, dict):
                    continue
                for p in (w.get("attackers") or []) + (w.get("defenders") or []):
                    if isinstance(p, dict) and str(p.get("country")) == "0":
                        n += 1
                        break
        ctx["wars"] = n
    except Exception:
        pass
    _CTX_CACHE["t"] = time.time()
    _CTX_CACHE["ctx"] = ctx
    return ctx


def _stage_factor(res, ctx):
    """游戏阶段维度：早期偏科研、后期偏合金（mid=1.0）"""
    y = ctx.get("year")
    if not y:
        return 1.0
    research = {"physics_research", "society_research", "engineering_research"}
    if y < 2250:
        if res in research:
            return 1.2
        if res == "alloys":
            return 0.9
    elif y >= 2350:
        if res in research:
            return 0.9
        if res == "alloys":
            return 1.2
    return 1.0


def _amount_score(amount):
    a = abs(amount)
    if a >= 1000:
        s = 4
    elif a >= 200:
        s = 3
    elif a >= 50:
        s = 2
    else:
        s = 1
    return s if amount > 0 else -s


def _pairs_of(block):
    """从 add_resource 块提取 [(资源, 数量), ...]（两种书写风格）"""
    items = block[3]
    pairs = []
    have_kv = {k: v for (typ, k, op, v) in items if typ == "kv"}
    if "resource" in have_kv and "amount" in have_kv:
        try:
            pairs.append((have_kv["resource"][3], float(have_kv["amount"][3])))
        except Exception:
            pass
    else:
        for (typ, k, op, v) in items:
            if typ == "kv" and (k in RES_NAMES or str(k).startswith("sr_")) \
                    and v and v[0] in ("tok", "str"):
                try:
                    pairs.append((k, float(v[3])))
                except Exception:
                    pass
    return pairs


def _collect_resources(blk, out, depth=0):
    """递归收集选项树里的 add_resource（互斥分支的同类资源后续取最大绝对值去重）"""
    if depth > 10 or blk is None or blk[0] != "blk":
        return
    for (typ, k, op, v) in blk[3]:
        if typ != "kv" or v is None:
            continue
        if k == "add_resource" and v[0] == "blk":
            out.extend(_pairs_of(v))
        elif v[0] == "blk":
            _collect_resources(v, out, depth + 1)


def _resource_gain(pairs, ctx, reasons, score):
    """按资源去重（保留绝对值最大者）后打分；含负数成本 / 顶上限 / 低储备加权"""
    best = {}
    for (res, amt) in pairs:
        cur = best.get(res)
        if cur is None or abs(amt) > abs(cur):
            best[res] = amt
    for (res, amt) in best.items():
        s = _amount_score(amt) * IMPORTANCE.get(res, 1.0) * _stage_factor(res, ctx)
        note = "%+g %s" % (amt, res)
        if amt > 0 and res in CAPS and ctx["resources"].get(res) is not None \
                and ctx["resources"][res] >= CAPS[res] - 2:
            s = 0
            note += "（已顶上限，价值≈0）"
        elif amt > 0 and ctx["resources"].get(res) is not None:
            low = 8000 if res == "energy" and ctx.get("wars") else 3000
            if ctx["resources"][res] < low:
                s *= 1.5
                note += "（当前储备偏低，价值提升）"
        score += s
        reasons.append("%+g → %s" % (s, note))
    return score


def _load_event(eid):
    global _INDEX
    if _INDEX is None:
        _INDEX = json.loads((AP / "data" / "event_index.json").read_text(encoding="utf-8"))
    e = _INDEX.get(eid)
    if not e:
        return None, None
    key = e["file"]
    if key not in _FILE_CACHE:
        text = (GAME / key).read_text(encoding="utf-8", errors="ignore")
        _FILE_CACHE[key] = (text, P2(text).root())
    text, top = _FILE_CACHE[key]
    item = modgen.find_event_in_top(text, top, eid, len(e["options"]))
    if item is None:
        return e, None
    return e, item[2]


def analyze(eid):
    """返回 {opt_idx: {"score":int,"keys":[...],"reasons":[...]}, "suggest":idx, "conf":"high/low"}"""
    e, v = _load_event(eid)
    if e is None:
        return None
    if v is None:
        return {"error": "块定位失败"}
    ctx = load_context()
    opts = []
    for (typ, k, op, ov) in v[3]:
        if typ == "kv" and k == "option" and ov[0] == "blk":
            opts.append(ov)
    out = {}
    for i, ov in enumerate(opts):
        bag = []
        _walk_keys(ov, bag)
        seen = set()
        score = 0
        reasons = []
        for key in bag:
            if key in seen:
                continue
            seen.add(key)
            if key in POS4:
                score += 4
                reasons.append("+4 " + key)
            elif key in POS3:
                score += 3
                reasons.append("+3 " + key)
            elif key in UNCERTAIN:
                score += 1
                reasons.append("+1 " + key + "（方向未判定）")
            elif key in POS2:
                score += 2
                reasons.append("+2 " + key)
            elif key in POS1:
                score += 1
                reasons.append("+1 " + key)
            elif key in NEG1:
                score -= 1
                reasons.append("-1 " + key)
            elif key in NEG2:
                score -= 2
                reasons.append("-2 " + key)
        # 参数感知：递归收集 add_resource（含负数成本 / 顶上限 / 低储备加权，互斥分支去重）
        pairs = []
        _collect_resources(ov, pairs)
        if pairs:
            score = _resource_gain(pairs, ctx, reasons, score)
        # 参数感知：add_modifier / remove_modifier（方向由 modifier_index 判定，时长加权）
        mods = []
        _collect_mod_refs(ov, mods)
        best_mod = {}
        for (act, mname, mdays) in mods:
            keym = (act, mname)
            if keym not in best_mod or _mod_duration_factor(mdays) > _mod_duration_factor(best_mod[keym]):
                best_mod[keym] = mdays
        m_idx = _mod_index()
        for (act, mname), mdays in best_mod.items():
            if not mname:
                score += 1 if act == "add_modifier" else -1
                reasons.append("±1 %s（未命名，方向未判定）" % act)
                continue
            ent = m_idx.get(mname)
            msc = ent.get("score") if isinstance(ent, dict) else None
            if not msc:
                score += 1 if act == "add_modifier" else -1
                reasons.append("±1 %s %s（未收录/中性，方向未判定）" % (act, mname))
                continue
            v = msc * _mod_duration_factor(mdays)
            if act == "remove_modifier":
                v = -v
            score += v
            reasons.append("%+.1f %s %s" % (v, act, mname))
        # 持续月收益的顶上限提示（递归）
        def _note_monthly(blk, depth=0):
            if depth > 10 or blk is None or blk[0] != "blk":
                return
            for (t2, k2, o2, v2) in blk[3]:
                if t2 != "kv" or v2 is None:
                    continue
                if k2 == "add_monthly_resource_mult" and v2[0] == "blk":
                    res = None
                    for (t3, k3, o3, v3) in v2[3]:
                        if t3 == "kv" and k3 == "resource" and v3 and v3[0] in ("tok", "str"):
                            res = v3[3]
                    if res and res in CAPS and ctx["resources"].get(res) is not None \
                            and ctx["resources"][res] >= CAPS[res] - 2:
                        reasons.append("→ 持续 %s 收益（已顶上限，价值降低）" % res)
                elif v2[0] == "blk":
                    _note_monthly(v2, depth + 1)
        _note_monthly(ov)
        out[i] = {"score": round(score, 1), "keys": sorted(seen), "reasons": reasons}
    if not out:
        return {"error": "无选项"}
    best = max(out.items(), key=lambda t: (t[1]["score"], -t[0]))
    second = sorted([s["score"] for i, s in out.items() if i != best[0]], reverse=True)
    gap = best[1]["score"] - (second[0] if second else best[1]["score"] - 99)
    return {"options": out, "suggest": best[0], "conf": "high" if gap >= 3 else "low"}


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    if args[0] == "--scan":
        idx = json.loads((AP / "data" / "event_index.json").read_text(encoding="utf-8"))
        multi = [(eid, e) for eid, e in idx.items() if len(e["options"]) >= 2]
        diff_ai = diff_hi = 0
        total = 0
        samples = []
        for eid, e in multi:
            r = analyze(eid)
            if not r or "error" in r:
                continue
            total += 1
            # 与 ai base 策略对比
            ai_opts = [(i, o["ai"]["base"]) for i, o in enumerate(e["options"])
                       if o.get("ai") and o["ai"].get("base") is not None]
            if ai_opts:
                ai_pick = max(ai_opts, key=lambda t: (t[1], -t[0]))[0]
                if ai_pick != r["suggest"]:
                    diff_ai += 1
                    if r["conf"] == "high" and len(samples) < 15:
                        samples.append((eid, ai_pick, r["suggest"],
                                        r["options"][r["suggest"]]["score"],
                                        r["options"][ai_pick]["score"]))
            if r["conf"] == "high":
                diff_hi += 1
        print("可分析事件 %d | 建议高置信 %d | 与 ai 权重选择分歧 %d" % (total, diff_hi, diff_ai))
        print("分歧样例（事件 / ai选 / 参谋选 / 分差）：")
        for s in samples:
            print("  ", s)
        return 0
    for eid in args:
        r = analyze(eid)
        if r is None:
            print(eid, "→ 未收录")
            continue
        if "error" in r:
            print(eid, "→", r["error"])
            continue
        print("== %s | 建议选项 %s（置信 %s）==" % (eid, r["suggest"], r["conf"]))
        for i, s in sorted(r["options"].items()):
            print("   选项%d 得分 %+d | %s" % (i, s["score"], ", ".join(s["reasons"]) or "（无计分键）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
