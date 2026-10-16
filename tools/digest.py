# -*- coding: utf-8 -*-
"""回归摘要：把离开模式期间发生的一切浓缩成一页。

用法:
    python digest.py               # 默认最近 8 小时
    python digest.py --hours 3     # 指定时长
"""
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DL = ROOT / "logs" / "decisions.log"


def main():
    hours = 8
    if "--hours" in sys.argv:
        hours = float(sys.argv[sys.argv.index("--hours") + 1])
    since = (datetime.datetime.now() - datetime.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    lines = [l for l in DL.read_text(encoding="utf-8", errors="ignore").splitlines()
             if re.match(r"\d{4}-", l) and l[:19] >= since]
    print("=" * 56)
    print("  AI 托管 · 回归摘要（最近 %g 小时）" % hours)
    print("=" * 56)
    if not lines:
        print("（该时段无日志）")
        return
    print("时段：%s  →  %s" % (lines[0][:19], lines[-1][:19]))

    cnt = {"ladder": 0, "single": 0, "fail": 0, "r4off": 0, "rw_new": 0, "rw_same": 0, "exc": 0}
    rw_list = []
    fail_last = None
    r5 = None
    r6 = None
    r2 = None
    for l in lines:
        if "执行=成功" in l and "多选项" in l:
            cnt["ladder"] += 1
        if "单选项事件已自动处理" in l:
            cnt["single"] += 1
        if "执行=失败" in l or "候选全被拒" in l or "处理失败" in l:
            cnt["fail"] += 1
            fail_last = l
        if "托管OFF" in l and "自动继续运行" in l:
            cnt["r4off"] += 1
        if "改写生效" in l:
            cnt["rw_new"] += 1
            rw_list.append(l)
        if "改写执行" in l:
            cnt["rw_same"] += 1
        if ("异常" in l) or ("[ERR]" in l):
            cnt["exc"] += 1
        if "[R5] 任务摘要" in l:
            r5 = l
        if "[R6] 健康" in l:
            r6 = l
        if "[R2] 资源" in l:
            r2 = l
    print()
    print("★ 自动处理：多选项 %d 个 · 单选项 %d 个 · 失败 %d  ·  空闲恢复运行 %d 次"
          % (cnt["ladder"], cnt["single"], cnt["fail"], cnt["r4off"]))
    if fail_last:
        print("     最近一次失败：", fail_last[:100])
    print("★ 决策改写：%d 次数值变更 · %d 次同值执行" % (cnt["rw_new"], cnt["rw_same"]))
    for l in rw_list[-5:]:
        print("     ", l[:150])
    if cnt["exc"]:
        print("★ 异常/错误 %d 条（见 decisions.log grep 异常）" % cnt["exc"])
    print()
    if r5:
        print("★ 帝国近况：", r5.split("任务摘要：", 1)[-1][:120])
    if r2:
        print("★ 资源：", r2.split("资源（对标 缓存）：", 1)[-1][:130])
    if r6:
        print("★ 健康：", r6.split("健康：", 1)[-1][:130])
    dates = re.findall(r"\[(\d{4}\.\d{2}\.\d{2})\]", "\n".join(lines))
    if len(dates) >= 2:
        print("★ 游戏时间推进：%s → %s（依据任务摘要时间戳）" % (dates[0], dates[-1]))
    print()
    tp = ROOT / "data" / "evt_tpl_map.json"
    try:
        m = json.loads(tp.read_text(encoding="utf-8"))
        print("★ 已学习事件家族 %d 个（模板缓存）" % len(m))
    except Exception:
        pass
    sp = ROOT / "data" / "evt_standing.json"
    try:
        s = json.loads(sp.read_text(encoding="utf-8"))
        if s:
            print("★ 当前武装家族：", "、".join(list(s)[:10]))
    except Exception:
        pass
    try:
        away = (ROOT / "tools" / "_away_mode.flag").exists()
        hai = None
        for l in lines:
            m = re.search(r"\[R3\] 托管开关：(开|关) → (开|关)", l)
            if m:
                hai = m.group(2)
        if away and hai == "关":
            print("★ 提示：离开模式开 + 托管关 —— 事件全自动，但帝国发展不由 AI 推进；")
            print("       需要挂机自动发展，请在面板点亮『切换　开 / 关』（即托管开）。")
    except Exception:
        pass
    print("=" * 56)


if __name__ == "__main__":
    main()
