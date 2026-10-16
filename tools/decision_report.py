# -*- coding: utf-8 -*-
"""决策档案：把 decisions.log 汇总成可读报告（托管质量审计入口）

用法：
  python decision_report.py            # 全量摘要
  python decision_report.py --diff     # 只列"游戏选择 vs 参谋意见"的分歧明细
"""
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "decisions.log"


def load_lines():
    return LOG.read_text(encoding="utf-8", errors="ignore").splitlines()


def main():
    lines = load_lines()
    cat = Counter()
    ours = []          # 我方决策（R1/evt_select）
    game_dec = []      # 游戏决策（审计 human -1）
    opinions = []      # 参谋意见
    for l in lines:
        if "[审计] 游戏AI自动决策" in l:
            cat["游戏AI决策"] += 1
            game_dec.append(l)
        elif "[参谋意见]" in l:
            cat["参谋意见（分歧）"] += 1
            opinions.append(l)
        elif "[R1] 多选项事件决策" in l or "[R1] 单选项事件" in l:
            cat["我方事件决策"] += 1
            ours.append(l)
        elif "[evt_select]" in l:
            cat["选择执行"] += 1
        elif "[R2]" in l:
            cat["资源心跳"] += 1
        elif "[R5]" in l:
            cat["任务摘要"] += 1
        elif "[建议]" in l:
            cat["态势建议"] += 1
        elif "[R4]" in l:
            cat["离开模式"] += 1
        elif "[R3]" in l:
            cat["状态变迁"] += 1

    print("==== 决策档案摘要（%d 行日志）====" % len(lines))
    for k, v in cat.most_common():
        print("  %-12s %d" % (k, v))
    if game_dec:
        div = len(opinions) / max(1, len(game_dec))
        print("\n游戏决策 %d 个；参谋有异议 %d 个（%.0f%%）"
              % (len(game_dec), len(opinions), div * 100))
    if ours:
        advisor_used = sum(1 for l in ours if "参谋" in l)
        print("我方事件决策 %d 个，其中采纳参谋建议 %d 个" % (len(ours), advisor_used))

    if "--diff" in sys.argv or opinions:
        print("\n---- 参谋分歧明细（最近 30 条）----")
        for l in opinions[-30:]:
            print("  " + l)
        if not opinions:
            print("  （暂无——托管模式下才会积累）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
