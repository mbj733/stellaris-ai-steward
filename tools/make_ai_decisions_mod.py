# -*- coding: utf-8 -*-
"""「AI 决策增强」MOD 生成器 v2（整文件替换方案，2026-10-16 深夜重做）

v1 教训（实机实测）：同 id 事件重定义会被引擎拒绝（error.log "already exists"，
保留基础版）→ 改为 PDX 标准做法：**模组里放置同相对路径的整个文件 = 替换基础文件**。

内容：
  A. 38 个"设计者偏好明确"纯基权事件 → 赢家 factor=1000 / 其余=0（去随机化）；
  B. 自检事件 zcodexai.1（带 namespace 声明 + BOM 本地化）；
  C. 自检覆盖：akx.9330 插入 a:0 / b:1000（同一替换文件内），单次触发可判定：
     游戏评估器返回 1 = 替换方案生效；0 = 仍为基础版。

产物：<输出目录>/events/...（整文件替换件；请在本地对你自己安装的游戏使用）
      + data\\ai_decisions_manifest.json
用法: python _build\\make_ai_decisions_mod.py
"""
import json
import shutil
import sys
from pathlib import Path

AP = Path(__file__).resolve().parent.parent
GAME = Path(r"<改成你的游戏安装路径>")
OUT = Path(__file__).resolve().parent.parent / "mod_build_output"  # 产物目录，可修改
MODNAME = "ai_decisions"
MODDIR = OUT / MODNAME

EVENT_KINDS = {
    "country_event", "planet_event", "pop_event", "fleet_event", "system_event",
    "observer_event", "first_contact_event", "bypass_event", "archaeological_site_event",
    "leader_event", "espionage_operation_event", "carrier_event", "ambient_object_event",
    "starbase_event", "ship_event", "situation_event", "astral_rift_event",
}


class P2:
    """带区间的极简解析器：value() 返回 (kind, start, end, value)"""
    def __init__(s, t, i0=0, i1=None):
        s.t = t
        s.i = i0
        s.n = len(t) if i1 is None else i1

    def skip(s):
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
        s.skip()
        start = s.i
        if s.i >= s.n:
            return ("eof", s.i, s.i, None)
        c = s.t[s.i]
        if c == "{":
            s.i += 1
            items = []
            while True:
                s.skip()
                if s.i >= s.n:
                    break
                if s.t[s.i] == "}":
                    s.i += 1
                    break
                k = s.value()
                s.skip()
                if s.i < s.n and s.t[s.i] in "=<>":
                    op = s.t[s.i]
                    if op in "<>" and s.i + 1 < s.n and s.t[s.i + 1] == "=":
                        op += "="
                        s.i += 1
                    s.i += 1
                    v = s.value()
                    items.append(("kv", k[3], op, v))
                else:
                    items.append(("k", k[3], None, None))
            return ("blk", start, s.i, items)
        if c == '"':
            j = s.i + 1
            while j < s.n and s.t[j] != '"':
                j += 2 if s.t[j] == "\\" and j + 1 < s.n else 1
            s.i = j + 1
            return ("str", start, s.i, s.t[start + 1:s.i - 1])
        j = s.i
        while j < s.n and s.t[j] not in " \t\r\n{}=<>":
            j += 1
        s.i = j
        return ("tok", start, s.i, s.t[start:j])

    def root(s):
        items = []
        while True:
            s.skip()
            if s.i >= s.n:
                break
            k = s.value()
            s.skip()
            if s.i < s.n and s.t[s.i] in "=<>":
                op = s.t[s.i]
                if op in "<>" and s.i + 1 < s.n and s.t[s.i + 1] == "=":
                    op += "="
                    s.i += 1
                s.i += 1
                v = s.value()
                items.append(("kv", k[3], op, v))
            else:
                items.append(("k", k[3], None, None))
        return ("blk", 0, s.n, items)


def apply_edits(text, edits):
    """edits: [(s0, s1, newv), ...]，从后往前替换"""
    out = text
    for (s0, s1, newv) in sorted(edits, key=lambda e: -e[0]):
        out = out[:s0] + newv + out[s1:]
    return out


def find_event_in_top(text, top, eid, n_opts_expected):
    """在已解析的顶层里找事件 kv 项（返回 (kind, op, v)）"""
    for (typ, k, op, v) in top[3]:
        if typ != "kv" or v is None or v[0] != "blk":
            continue
        if not (k in EVENT_KINDS or (isinstance(k, str) and k.endswith("_event"))):
            continue
        idv = None
        n_opt = 0
        for (typ2, k2, op2, v2) in v[3]:
            if typ2 == "kv" and k2 == "id" and v2 and v2[0] in ("tok", "str"):
                idv = v2[3]
            elif typ2 == "kv" and k2 == "option" and v2 and v2[0] == "blk":
                n_opt += 1
        if idv == eid and n_opt == n_opts_expected:
            return (k, op, v)
    return None


def collect_edits_for_file(text, top, spec_list):
    """spec_list 元素: (eid, n_opts, win_idx_or_None, insert_factors_or_None)
    - win_idx 非 None：该事件选项顶层 factor/base → 1000/0（替换式编辑）
    - insert_factors 非 None：给选项"插入" ai_chance，如 [(0,0),(1,1000)]"""
    edits = []
    records = []
    for (eid, n_opts, win_idx, insert_factors) in spec_list:
        item = find_event_in_top(text, top, eid, n_opts)
        if item is None:
            records.append({"event": eid, "ok": False, "why": "块未找到"})
            continue
        _, _, v = item
        opts = [vv for (typ, k, op, vv) in v[3]
                if typ == "kv" and k == "option" and vv[0] == "blk"]
        if len(opts) != n_opts:
            records.append({"event": eid, "ok": False, "why": "选项数不符"})
            continue
        if insert_factors is not None:
            # 日志哨兵：证明"该替换文件里的这个事件"真的运行了（game.log 出现该行）
            for (typ, k, op, idv) in v[3]:
                if typ == "kv" and k == "id" and idv and idv[0] in ("tok", "str"):
                    edits.append((idv[2], idv[2],
                                  '\n\timmediate = { log = "ZCODEXAI_PROBE_v2_active" }'))
                    break
        n_ed = 0
        for oi, ov in enumerate(opts):
            if win_idx is not None:
                # 仅改动"有 ai_chance"的选项；没有权重的选项本就不在池内，保持原样
                for (typ, k, op, ai) in ov[3]:
                    if typ == "kv" and k == "ai_chance" and ai[0] == "blk":
                        for (t2, k2, o2, fv) in ai[3]:
                            if t2 == "kv" and k2 in ("factor", "base") and fv[0] in ("tok", "str"):
                                newv = "1000" if oi == win_idx else "0"
                                if fv[3] != newv:      # 跳过空编辑（0→0 等）
                                    edits.append((fv[1], fv[2], newv))
                                    n_ed += 1
                                break
                        break
            if insert_factors is not None:
                for (tgt, factor) in insert_factors:
                    if oi != tgt:
                        continue
                    namev = None
                    for (typ, k, op, nv) in ov[3]:
                        if typ == "kv" and k == "name" and nv and nv[0] in ("tok", "str"):
                            namev = nv
                            break
                    if namev is None:
                        records.append({"event": eid, "ok": False, "why": "选项%d 无 name" % oi})
                        continue
                    ins = "\n\t\tai_chance = { factor = %d }" % factor
                    edits.append((namev[2], namev[2], ins))
                    n_ed += 1
        records.append({"event": eid, "ok": n_ed > 0, "edits": n_ed})
    return edits, records


def calc_batch(idx):
    batch = []
    stats = {"ties": 0, "flat": 0, "single_positive": 0}
    for eid, e in idx.items():
        opts = e["options"]
        if len(opts) < 2:
            continue
        ais = [o.get("ai") for o in opts]
        if not any(ais):
            continue
        if any((a or {}).get("mods") for a in ais):
            continue
        ai_opts = [(i, a["base"]) for i, a in enumerate(ais) if a and a.get("base") is not None]
        if len(ai_opts) < 2:
            continue
        nz = sorted([b for _, b in ai_opts], reverse=True)
        if nz[0] <= 0:
            continue
        if len([b for b in nz if b > 0]) < 2:
            stats["single_positive"] += 1
            continue
        if nz[0] == nz[1]:
            stats["ties"] += 1
            continue
        if nz[0] < 2 * nz[1]:
            stats["flat"] += 1
            continue
        win = max(ai_opts, key=lambda t: (t[1], -t[0]))
        batch.append((eid, e, win[0]))
    return batch, stats


def main():
    idx = json.loads((AP / "data" / "event_index.json").read_text(encoding="utf-8"))
    loc = json.loads((AP / "data" / "loc.json").read_text(encoding="utf-8"))
    batch, stats = calc_batch(idx)

    groups = {}
    for (eid, e, wi) in batch:
        groups.setdefault(e["file"], []).append((eid, e, wi))
    akxf = (idx.get("akx.9330") or {}).get("file")
    if not akxf:
        print("!! 找不到 akx.9330 源文件")
        return 2
    groups.setdefault(akxf, []).append(("akx.9330", idx["akx.9330"], None))

    if MODDIR.exists():
        shutil.rmtree(MODDIR)
    (MODDIR / "events").mkdir(parents=True)
    (MODDIR / "localisation" / "simp_chinese").mkdir(parents=True)
    (MODDIR / "localisation" / "english").mkdir(parents=True)

    manifest = []
    total_edits = 0
    replaced = []
    problems = []
    to_write = []
    for rel, evs in sorted(groups.items()):
        src = GAME / rel
        text = src.read_text(encoding="utf-8", errors="ignore")
        top = P2(text).root()
        specs = []
        for (eid, e, wi) in evs:
            if wi is None:
                specs.append((eid, len(e["options"]), None, [(0, 1), (1, 1000)]))
            else:
                specs.append((eid, len(e["options"]), wi, None))
        edits, records = collect_edits_for_file(text, top, specs)
        bad = [r for r in records if not r.get("ok")]
        if bad or not edits:
            problems.append((rel, bad[:4]))
            continue
        new_text = apply_edits(text, edits)
        to_write.append((rel, new_text, evs, len(edits)))

    if problems:
        print("!! 全量计算未通过，未写任何文件。问题文件：")
        for rel, bad in problems:
            print("   ", rel, bad)
        return 3

    for (rel, new_text, evs, n_ed) in to_write:
        dst = MODDIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(new_text, encoding="utf-8")
        replaced.append(rel)
        total_edits += n_ed
        for (eid, e, wi) in evs:
            title = loc.get(e.get("title") or "", "")
            if wi is None:
                manifest.append({"event": eid, "file": rel, "title": title,
                                 "kind": "selftest-insert", "winner_idx": 1,
                                 "n_options": len(e["options"]),
                                 "note": "期望游戏评估器返回 1（替换生效）"})
            else:
                oname = loc.get((e["options"][wi].get("name") or ""),
                                e["options"][wi].get("name"))
                manifest.append({"event": eid, "file": rel, "title": title,
                                 "kind": "derandom", "winner_idx": wi,
                                 "winner_option": oname, "n_options": len(e["options"])})
        print("  替换:", rel, "(%d 个事件, %d 处编辑)" % (len(evs), n_ed))

    (MODDIR / "events" / "zz_ai_decisions_selftest.txt").write_text(
        "# AI Decisions Enhanced 自检：\n"
        "# `event zcodexai.1` 可执行 = MOD 已加载（期望评估器选 idx0）\n"
        "namespace = zcodexai\n\n"
        "country_event = {\n"
        "\tid = zcodexai.1\n"
        "\ttitle = zcodexai.1.name\n"
        "\tdesc = zcodexai.1.desc\n"
        "\tpicture = GFX_evt_star_chart\n"
        "\tis_triggered_only = yes\n"
        "\toption = {\n\t\tname = zcodexai.1.a\n\t\tai_chance = { factor = 1 }\n\t}\n"
        "\toption = {\n\t\tname = zcodexai.1.b\n\t\tai_chance = { factor = 5 }\n\t}\n"
        "}\n", encoding="utf-8")
    (MODDIR / "localisation" / "simp_chinese" / "ai_decisions_l_simp_chinese.yml").write_text(
        'l_simp_chinese:\n'
        ' zcodexai.1.name:0 "AI 决策增强 · 自检事件"\n'
        ' zcodexai.1.desc:0 "看到这个窗口说明《AI 决策增强》MOD 已正确加载。任意选项均可，无任何影响。"\n'
        ' zcodexai.1.a:0 "确认（选项 A）"\n'
        ' zcodexai.1.b:0 "忽略（选项 B）"\n', encoding="utf-8-sig")
    (MODDIR / "localisation" / "english" / "ai_decisions_l_english.yml").write_text(
        'l_english:\n'
        ' zcodexai.1.name:0 "AI Decisions Enhanced - Self Test"\n'
        ' zcodexai.1.desc:0 "If you can see this window, the mod loaded correctly."\n'
        ' zcodexai.1.a:0 "Confirm (Option A)"\n'
        ' zcodexai.1.b:0 "Ignore (Option B)"\n', encoding="utf-8-sig")

    (MODDIR / "descriptor.mod").write_text(
        'version="2.0.0"\n'
        'tags={\n\t"Gameplay"\n}\n'
        'name="AI Decisions Enhanced (4.5)"\n'
        'supported_version="4.5.*"\n'
        'remote_file_id=""\n', encoding="utf-8")
    (OUT / (MODNAME + ".mod")).write_text(
        'version="2.0.0"\n'
        'tags={\n\t"Gameplay"\n}\n'
        'name="AI Decisions Enhanced (4.5)"\n'
        'supported_version="4.5.*"\n'
        'remote_file_id=""\n'
        'path="mod/%s"\n' % MODNAME, encoding="utf-8")

    summary = {
        "version": 2,
        "method": "file-replacement",
        "events": manifest,
        "replaced_files": replaced,
        "total_edits": total_edits,
        "stats": stats,
    }
    (AP / "data" / "ai_decisions_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (AP / "data" / "ai_decisions_selftest.json").write_text(json.dumps({
        "zcodexai.1": {"purpose": "MOD 已加载 + 权重是否被读取",
                       "weights": "a:1 / b:5",
                       "signal": "多次调用评估器：出现过选项1 ⇒ 权重驱动；从不出现 ⇒ 权重未被读取"},
        "akx.9330": {"purpose": "整文件替换是否生效",
                     "signal": "触发后 game.log 应出现 ZCODEXAI_PROBE_v2_active；"
                               "评估器期望返回 1（权重 b:1000 主导）",
                     "weights": "a:1 / b:1000"},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("完成：%d 个条目（含 1 自检插入）| 替换文件 %d 个 | 编辑 %d 处 | 跳过 %s"
          % (len(manifest), len(replaced), total_edits,
             {k: v for k, v in stats.items() if v}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
