# -*- coding: utf-8 -*-
"""事件多选项决策器（v1，2026-10-16）

决策优先级：
  1) 人工覆盖表 data\\evt_overrides.json：{"事件名": {"idx": N, "why": "理由"}}
  2) 脚本 ai_chance 基础权重（factor 的 base 值；条件 modifier 未计入，仅提示）
  3) 无权重 → 取"首个无触发条件选项"；全有触发 → 兜底选项 0
凡无法安全决策（未收录 / 选项数与脚本不符）→ 返回 None，调用方必须放弃自动执行。
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
_index = None
_loc = None
_over = None


def load():
    global _index, _loc, _over
    if _index is None:
        _index = json.loads((DATA / "event_index.json").read_text(encoding="utf-8"))
        _loc = json.loads((DATA / "loc.json").read_text(encoding="utf-8"))
        ov = DATA / "evt_overrides.json"
        try:
            _over = json.loads(ov.read_text(encoding="utf-8")) if ov.exists() else {}
        except Exception:
            _over = {}
    return _index, _loc, _over


def text(key):
    if not key:
        return ""
    _, loc, _ = load()
    return loc.get(key, key)


def title_text(name):
    idx_d, _, _ = load()
    e = idx_d.get(name) or {}
    return text(e.get("title"))


def option_text(name, idx):
    idx_d, _, _ = load()
    e = idx_d.get(name) or {}
    opts = e.get("options") or []
    if isinstance(idx, int) and 0 <= idx < len(opts):
        return text(opts[idx].get("name"))
    return ""


def decide(name, n_opts):
    """返回 (idx, reason) 或 (None, reason)。"""
    idx_d, _, over = load()
    if name in over:
        try:
            i = int(over[name].get("idx", 0))
        except Exception:
            i = -1
        if 0 <= i < (n_opts or 0):
            return i, "人工覆盖：" + str(over[name].get("why", ""))
    # 参谋（v2 态势感知）：高置信 + 无不确定项 + 正收益≥3 → 采纳
    try:
        import evt_analyze as ea
        ra = ea.analyze(name)
        if ra and "error" not in ra and ra.get("conf") == "high":
            sug = ra["suggest"]
            rs = ra["options"].get(sug, {})
            rsns = rs.get("reasons", [])
            solid = rs.get("score", 0) - sum(1 for r in rsns if "方向未判定" in r)
            if 0 <= sug < (n_opts or 0) and solid >= 3:
                return sug, "参谋（确定项净值 %g）：%s" % (solid, "；".join(rsns)[:60])
    except Exception:
        pass
    e = idx_d.get(name)
    if not e:
        return None, "事件未收录（可能来自 MOD/动态生成），不自动处理"
    opts = e.get("options") or []
    if n_opts is None or len(opts) != n_opts:
        return None, f"选项数不符（脚本 {len(opts)} vs 实机 {n_opts}，疑有运行时过滤），不自动处理"
    scored = []
    for i, o in enumerate(opts):
        ai = o.get("ai") or {}
        b = ai.get("base")
        if b is not None:
            scored.append((i, float(b), len(ai.get("mods") or [])))
    if scored:
        i, b, nmod = max(scored, key=lambda t: (t[1], -t[0]))
        reason = f"ai权重最高 base={b:g}"
        if nmod:
            reason += f"（另有 {nmod} 条条件修正未计入）"
        return i, reason
    for i, o in enumerate(opts):
        if not o.get("trigger"):
            return i, "无权重数据：取首个无触发条件选项"
    return 0, "无权重数据：兜底选项 0"


def option_has_trigger(name, idx):
    """该选项是否带 trigger 字段。True/False；事件未收录返回 None。"""
    idx_d, _, _ = load()
    e = idx_d.get(name) or {}
    opts = e.get("options") or []
    if isinstance(idx, int) and 0 <= idx < len(opts):
        return bool(opts[idx].get("trigger"))
    return None


def candidates(name, n_opts):
    """按偏好排序的全部候选项 [(idx, reason), ...]（供"探测天梯"依次尝试：
    第一个被游戏接受的选项 = 触发器合法的最高偏好解）。

    顺序：人工覆盖 > 参谋高置信 > ai权重降序（同重时无触发项优先）> 序号。
    未收录事件 → 按序号盲探（游戏侧会拒绝非法项，安全）。
    """
    idx_d, _, over = load()
    n = int(n_opts or 0)
    order = []

    def add(i, reason):
        if 0 <= i < n and not any(k == i for k, _ in order):
            order.append((i, reason))

    if name in over:
        try:
            i = int(over[name].get("idx", -1))
        except Exception:
            i = -1
        if 0 <= i < n:
            add(i, "人工覆盖：" + str(over[name].get("why", "")))
    try:
        import evt_analyze as ea
        ra = ea.analyze(name)
        if ra and "error" not in ra and ra.get("conf") == "high":
            sug = ra["suggest"]
            rs = ra["options"].get(sug, {})
            rsns = rs.get("reasons", [])
            solid = rs.get("score", 0) - sum(1 for r in rsns if "方向未判定" in r)
            if 0 <= sug < n and solid >= 3:
                add(sug, "参谋（确定项净值 %g）：%s" % (solid, "；".join(rsns)[:60]))
    except Exception:
        pass
    e = idx_d.get(name)
    rest = []
    if e:
        opts = e.get("options") or []
        for i, o in enumerate(opts):
            if i >= n:
                continue
            ai = o.get("ai") or {}
            b = ai.get("base")
            has_t = bool(o.get("trigger"))
            rest.append((i, (float(b) if b is not None else None), has_t))
        rest.sort(key=lambda t: (t[1] is None, -(t[1] if t[1] is not None else 0.0), t[2], t[0]))
        for i, b, has_t in rest:
            if b is not None:
                add(i, "ai权重 base=%g" % b)
            elif not has_t:
                add(i, "无触发条件（预期必合法）")
            else:
                add(i, "含触发器（待探测）")
    for i in range(n):
        add(i, "未收录/兜底（盲探序）")
    return order


if __name__ == "__main__":
    tests = [
        ("akx.9330", 2),
        ("ancrel.11020", 2),
        ("ancrel.12005", 2),
        ("ancrel.8070", 2),
        ("ambition.125", 1),
        ("nonexistent.1", 2),
    ]
    for nm, n in tests:
        i, r = decide(nm, n)
        t = title_text(nm)
        ot = option_text(nm, i) if i is not None else ""
        print(f"{nm} n={n} -> idx={i} | {r} | 标题:{t[:24]} 选项:{ot[:30]}")
