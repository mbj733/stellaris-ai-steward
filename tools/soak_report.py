# -*- coding: utf-8 -*-
"""挂机质量报告：解析 decisions.log（[R6]/[R1]/[evt_select]/[审计]）输出统计摘要。

用法:
    python soak_report.py                    # 全天
    python soak_report.py --since "2026-10-16 22:53"   # 指定起点
"""
import re
import sys
from collections import Counter
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "logs" / "decisions.log"


def main():
    since = None
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]
    lines = LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
    if since:
        lines = [l for l in lines if re.match(r"\d{4}-", l) and l[:16] >= since]
    stats = Counter()
    first = last = None
    r6 = []
    fails = []
    for l in lines:
        if re.match(r"\d{4}-\d{2}-\d{2}", l):
            first = first or l[:19]
            last = l[:19]
        if "[R6]" in l:
            r6.append(l)
        if "执行=成功" in l and "多选项" in l:
            stats["ladder_ok"] += 1
        if "候选全被拒" in l:
            stats["ladder_fail"] += 1
            fails.append(l)
        if "单选项事件已自动处理" in l:
            stats["single_ok"] += 1
        if "单选项事件处理失败" in l:
            stats["single_fail"] += 1
            fails.append(l)
        if "已武装(按名)" in l:
            stats["armed_rules"] += 1
        if "[审计]" in l:
            stats["audit_game"] += 1
        if "改写生效" in l:
            stats["rw_visible"] += 1
        if "改写执行" in l:
            stats["rw_same"] += 1
        if "事件处理后已自动恢复运行" in l:
            stats["resume_ok"] += 1
        if "已自动继续运行" in l:
            stats["r4_resume"] += 1
        if "异常" in l and "[R6] 健康" not in l:
            stats["exceptions"] += 1
            fails.append(l)
    print("时段: %s → %s（共 %d 行）" % (first, last, len(lines)))
    for k in ["ladder_ok", "ladder_fail", "single_ok", "single_fail", "armed_rules",
              "rw_visible", "rw_same", "audit_game", "resume_ok", "r4_resume", "exceptions"]:
        print("  %-12s %d" % (k, stats[k]))
    if fails:
        print("异常/失败行（最近 10）:")
        for l in fails[-10:]:
            print("  ", l[:165])
    if r6:
        print("R6 心跳 %d 条（最近 4）:" % len(r6))
        for l in r6[-4:]:
            print("  ", l[:175])


if __name__ == "__main__":
    main()
