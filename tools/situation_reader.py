# -*- coding: utf-8 -*-
"""读取最新存档 → 输出玩家"决策输入清单"（决策引擎的数据源）。

覆盖内容（对应游戏里"核心日志 / 其他"两大分页的底层数据）：
  - 进行中的特殊情况 situations（含进度/方针）
  - 特殊项目 special_project（含进行中/未完成）
  - 兴趣点 poi（任务提示类条目）
  - 进行中的事件链 event_chain

用法：python situation_reader.py
"""
import sys
import zipfile

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import read_save as rs  # noqa: E402


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def load(sv=None):
    """读最新（或指定）存档 → (存档路径, gamestate 树)。"""
    sv = sv or rs.latest_save()
    with zipfile.ZipFile(sv) as z:
        txt, _ = rs.decode(z.read("gamestate"))
    root = rs.Parser(txt).top()
    return sv, root.get("gamestate", root)


def digest(gs):
    """任务面摘要（供决策日志使用）。"""
    c0 = gs["country"]["0"]
    ev = c0.get("events", {})
    sits_root = gs.get("situations", {})
    sits = sits_root.get("situations", {}) if isinstance(sits_root, dict) else {}
    n_sit = 0
    if isinstance(sits, dict):
        for v in sits.values():
            if isinstance(v, dict) and str(v.get("country")) == "0":
                n_sit += 1
    sps = [p for p in as_list(ev.get("special_project")) if isinstance(p, dict)]
    act = [p.get("special_project") for p in sps
           if p.get("status") != "completed" and p.get("special_project")]
    pois = [p.get("name") for p in as_list(ev.get("poi")) if isinstance(p, dict)]
    chains = [c.get("event_chain") for c in as_list(ev.get("event_chain")) if isinstance(c, dict)]
    try:
        mp = float(c0.get("military_power", "0"))
    except Exception:
        mp = 0.0
    try:
        fs = float(c0.get("fleet_size", "0"))
    except Exception:
        fs = 0.0
    wars = gs.get("war", {})
    n_wars = len(wars) if isinstance(wars, (dict, list)) else 0
    own_wars = 0
    if isinstance(wars, dict):
        for _wid, w in wars.items():
            if not isinstance(w, dict):
                continue
            for p in as_list(w.get("attackers")) + as_list(w.get("defenders")):
                if isinstance(p, dict) and str(p.get("country")) == "0":
                    own_wars += 1
                    break
    def _f(k, d=0.0):
        try:
            return float(c0.get(k, d))
        except Exception:
            return d
    ts = c0.get("tech_status")
    techs = as_list(ts.get("technology")) if isinstance(ts, dict) else []
    return {"situations": n_sit, "projects": act, "pois": pois, "chains": chains,
            "military_power": mp, "fleet_size": fs, "wars": n_wars,
            "starbase_cap": _f("starbase_capacity"), "starbase_used": _f("starbase_capacity_used"),
            "naval_used": _f("used_naval_capacity"), "economy_power": _f("economy_power"),
            "empire_size": _f("empire_size"),
            "planets": len(as_list(c0.get("owned_planets"))),
            "techs": len(techs), "own_wars": own_wars}


def digest_line(gs):
    d = digest(gs)
    proj = ("（" + "、".join(str(x) for x in d["projects"][:4]) + "）") if d["projects"] else ""
    return (f"[{gs.get('date', '?')}] 特殊情况 {d['situations']}；未完成特殊项目 {len(d['projects'])}{proj}；"
            f"兴趣点 {len(d['pois'])}；事件链 {len(d['chains'])}；"
            f"军力 {d['military_power']:.0f}；银河战争 {d['wars']}；我方战争 {d['own_wars']}；"
            f"星基 {d['starbase_used']:.0f}/{d['starbase_cap']:.0f}；"
            f"舰队 {d['fleet_size']:.0f} 艘；星球 {d['planets']}；帝国规模 {d['empire_size']:.0f}；"
            f"科技 {d['techs']} 项")


def main():
    sv, gs = load()
    c0 = gs["country"]["0"]
    ev = c0.get("events", {})

    print("存档:", sv.rsplit("\\", 1)[-1])
    print("日期:", gs.get("date"), " 帝国:", c0.get("name"))
    print("=" * 46)

    # 1) 进行中的特殊情况（国家 0）
    sits_root = gs.get("situations", {})
    sits = sits_root.get("situations", {}) if isinstance(sits_root, dict) else {}
    mine = []
    if isinstance(sits, dict):
        for sid, v in sits.items():
            if isinstance(v, dict) and str(v.get("country")) == "0":
                mine.append((sid, v))
    print(f"== 进行中的特殊情况（{len(mine)} 条） ==")
    for sid, v in mine[:20]:
        print(f"  [{sid}] {v.get('type')}  进度={v.get('progress')} 方针={v.get('approach')}")
    if len(mine) > 20:
        print(f"  ...共 {len(mine)} 条")

    # 2) 特殊项目
    sps = [p for p in as_list(ev.get("special_project")) if isinstance(p, dict)]
    active = [p for p in sps if p.get("status") != "completed"]
    done = len(sps) - len(active)
    print(f"\n== 特殊项目（未完成 {len(active)} 条 / 已完成 {done} 条） ==")
    for p in active[:20]:
        print(f"  [{p.get('id')}] {p.get('special_project')}  状态={p.get('status')}  日期={p.get('ai_research_date')}")

    # 3) 兴趣点（任务类条目）
    pois = [p for p in as_list(ev.get("poi")) if isinstance(p, dict)]
    print(f"\n== 兴趣点/任务（{len(pois)} 条） ==")
    for p in pois[:20]:
        print(f"  {p.get('name')}  (链: {p.get('event_chain')})")

    # 4) 进行中的事件链
    chains = [c for c in as_list(ev.get("event_chain")) if isinstance(c, dict)]
    print(f"\n== 进行中的事件链（{len(chains)} 条） ==")
    for c in chains[:20]:
        print(f"  {c.get('event_chain')}")


if __name__ == "__main__":
    main()
