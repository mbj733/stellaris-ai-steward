# -*- coding: utf-8 -*-
"""构建事件索引与本地化索引（AI 决策引擎的数据基础）。

输出：
  data\\event_index.json  {event_id: {file, title, desc, flags, options:[{name, ai, trigger, effects}]}}
  data\\loc.json          {loc_key: 文本}（游戏当前语言；去 $变量$ 符号）

用法：python evt_index_build.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = Path(r"<改成你的游戏安装路径>")
DOCS = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris"
DATA = ROOT / "data"

EVENT_KINDS = {
    "country_event", "planet_event", "pop_event", "fleet_event", "system_event",
    "observer_event", "first_contact_event", "bypass_event", "archaeological_site_event",
    "leader_event", "espionage_operation_event", "carrier_event", "ambient_object_event",
    "starbase_event", "ship_event", "situation_event", "astral_rift_event",
}


class P:
    """极简 Clausewitz 脚本解析器（容忍注释/引号/操作符）"""
    def __init__(s, t):
        s.t = t
        s.i = 0
        s.n = len(t)

    def skip_ws(s):
        while s.i < s.n:
            c = s.t[s.i]
            if c == "#":
                j = s.t.find("\n", s.i)
                s.i = s.n if j < 0 else j + 1
            elif c in " \t\r\n":
                s.i += 1
            else:
                break

    def value(s):
        s.skip_ws()
        if s.i >= s.n:
            return ("eof", "")
        c = s.t[s.i]
        if c == "{":
            return s.block()
        if c == '"':
            j = s.i + 1
            out = []
            while j < s.n and s.t[j] != '"':
                if s.t[j] == "\\" and j + 1 < s.n:
                    out.append(s.t[j + 1]); j += 2
                else:
                    out.append(s.t[j]); j += 1
            s.i = j + 1
            return ("str", "".join(out))
        j = s.i
        while j < s.n and s.t[j] not in " \t\r\n{}=<>":
            j += 1
        tok = s.t[s.i:j]
        s.i = j
        return ("tok", tok)

    def block(s):
        assert s.t[s.i] == "{"
        s.i += 1
        items = []
        while True:
            s.skip_ws()
            if s.i >= s.n:
                break
            if s.t[s.i] == "}":
                s.i += 1
                break
            k = s.value()
            s.skip_ws()
            if s.i < s.n and s.t[s.i] in "=<>":
                op = s.t[s.i]
                if op in "<>" and s.i + 1 < s.n and s.t[s.i + 1] == "=":
                    op += "="
                    s.i += 1
                s.i += 1
                v = s.value()
                items.append(("kv", k[1], op, v))
            else:
                items.append(("k", k[1], None, None))
        return ("blk", items)

    def root(s):
        """顶层：连续的 键=值 序列（文件不以 { 开头）"""
        items = []
        while True:
            s.skip_ws()
            if s.i >= s.n:
                break
            k = s.value()
            s.skip_ws()
            if s.i < s.n and s.t[s.i] in "=<>":
                op = s.t[s.i]
                if op in "<>" and s.i + 1 < s.n and s.t[s.i + 1] == "=":
                    op += "="
                    s.i += 1
                s.i += 1
                v = s.value()
                items.append(("kv", k[1], op, v))
            else:
                items.append(("k", k[1], None, None))
        return ("blk", items)


def kv_items(blk):
    return [(k, v) for (typ, k, op, v) in blk[1] if typ == "kv"]


def get_one(blk, key):
    for (typ, k, op, v) in blk[1]:
        if typ == "kv" and k == key:
            return v
    return None


def tok_of(v):
    return v[1] if v and v[0] in ("tok", "str") else None


def num_of(v):
    try:
        return float(v[1])
    except Exception:
        return None


def parse_ai_chance(blk):
    """格式：ai_chance = { factor = <base数字>  modifier = { factor/add = x  条件… } ... }
    返回 {"base": 数字或None, "mods": [[mult, add, 有额外条件], ...]}
    （条件求值需要游戏状态，静态只取 base；mods 记录供显示"存在条件修正"）"""
    base = None
    mods = []
    for (typ, k, op, v) in blk[1]:
        if typ == "kv" and k in ("factor", "base"):
            b = num_of(v)
            if b is not None:
                base = b
        elif typ == "kv" and k == "modifier" and v[0] == "blk":
            mult = None
            add = None
            nkeys = 0
            for (typ2, k2, op2, v2) in v[1]:
                nkeys += 1
                if typ2 == "kv" and k2 == "factor":
                    f = num_of(v2)
                    if f is not None:
                        mult = f
                elif typ2 == "kv" and k2 == "add":
                    a = num_of(v2)
                    if a is not None:
                        add = a
            mods.append([mult, add, nkeys > 1])
    return {"base": base, "mods": mods}


def collect_effect_keys(blk, bag=None, depth=0):
    if bag is None:
        bag = set()
    if depth > 6 or blk[0] != "blk":
        return bag
    for (typ, k, op, v) in blk[1]:
        if typ == "kv":
            bag.add(k)
            if v[0] == "blk":
                collect_effect_keys(v, bag, depth + 1)
        elif typ == "k":
            bag.add(k)
    return bag


def parse_events():
    evdir = GAME / "events"
    index = {}
    files = sorted(evdir.rglob("*.txt"))
    n_ev = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "event" not in text[:200000]:
            pass
        p = P(text)
        try:
            top = p.root()
        except Exception:
            continue
        for (typ, k, op, v) in top[1]:
            if typ != "kv" or k not in EVENT_KINDS or v[0] != "blk":
                continue
            eid = tok_of(get_one(v, "id"))
            if not eid:
                continue
            flags = []
            for fk in ("is_triggered_only", "hide_window", "fire_only_once",
                       "is_advisor_event", "major", "diplomatic", "war_dialog"):
                if get_one(v, fk) is not None:
                    flags.append(fk)
            chain = tok_of(get_one(v, "event_chain"))
            imm = get_one(v, "immediate")
            aft = get_one(v, "after")
            imm_keys = sorted(collect_effect_keys(imm)) if (imm and imm[0] == "blk") else []
            aft_keys = sorted(collect_effect_keys(aft)) if (aft and aft[0] == "blk") else []
            opts = []
            for (typ2, k2, op2, v2) in v[1]:
                if typ2 == "kv" and k2 == "option" and v2[0] == "blk":
                    name = tok_of(get_one(v2, "name"))
                    ai = None
                    ac = get_one(v2, "ai_chance")
                    if ac and ac[0] == "blk":
                        ai = parse_ai_chance(ac)
                    trg = get_one(v2, "trigger")
                    eff = sorted(collect_effect_keys(v2)) if v2[0] == "blk" else []
                    opts.append({
                        "name": name,
                        "ai": ai,
                        "trigger": bool(trg),
                        "effects": [e for e in eff if e not in
                                    ("name", "ai_chance", "trigger", "trigger_else")][:12],
                    })
            index[eid] = {
                "file": str(f.relative_to(GAME)),
                "title": tok_of(get_one(v, "title")),
                "desc": tok_of(get_one(v, "desc")),
                "flags": flags,
                "chain": chain,
                "immediate": imm_keys,
                "after": aft_keys,
                "options": opts,
            }
            n_ev += 1
    return index, len(files), n_ev


def parse_loc():
    settings = DOCS / "settings.txt"
    lang = "l_simp_chinese"
    try:
        t = settings.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"language\s*=\s*\"?([\w_]+)", t)
        if m:
            lang = m.group(1)
    except Exception:
        pass
    folder = lang[2:] if lang.startswith("l_") else lang
    locdir = GAME / "localisation" / folder
    out = {}
    if locdir.exists():
        for f in locdir.rglob("*.yml"):
            try:
                for line in f.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or ":" not in line:
                        continue
                    m = re.match(r'^([\w.\-]+):\d*\s+"(.*)"\s*$', line)
                    if m:
                        txt = re.sub(r"\$[^$]*\$", "", m.group(2))
                        out[m.group(1)] = txt.strip()
            except Exception:
                continue
    return lang, out


def main():
    DATA.mkdir(exist_ok=True)
    idx, nf, ne = parse_events()
    (DATA / "event_index.json").write_text(
        json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"事件索引：{len(idx)} 个事件（来自 {nf} 个文件）→ data\\event_index.json")
    lang, loc = parse_loc()
    (DATA / "loc.json").write_text(
        json.dumps(loc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"本地化：{lang}，{len(loc)} 条 → data\\loc.json")
    for probe in ("ambition.125",):
        if probe in idx:
            print("样例:", json.dumps(idx[probe], ensure_ascii=False)[:400])


if __name__ == "__main__":
    sys.exit(main())
