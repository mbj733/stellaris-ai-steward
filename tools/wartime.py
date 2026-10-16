# -*- coding: utf-8 -*-
"""战时工具箱（wartime）——战争态势查询 + 应急操作（全部走控制台通道，零崩溃风险）。

只读/安全类：
  python wartime.py status            查看 attackallfleets 开关字节（只读）
  python wartime.py wars              从最新存档列出全部战争（只读，含我方参战标记）
  python wartime.py attack_on/off     切换「全面交战模式」（attackallfleets；风险见下）

应急操作（作弊级，请明确知情后使用；游戏内会提示已启用控制台）：
  python wartime.py navy [pct]        按海军容量爆舰队（create_navy，默认 1.0=100%，上限1.5）
  python wartime.py invincible        切换「己方舰船免伤」（保舰队用）

核弹级（需要额外 --yes 才真正执行；不带 --yes 只打印将要执行的命令）：
  python wartime.py win <敌国id> <战争id> --yes
      令该敌国向所有要求投降（surrender <cid> <warid>）——等于我方赢得该战争。
      ⚠ 请先自行确认 warid 归属（用 wars 子命令看）。
  python wartime.py independence
      打印「对宗主打独立战争」的完整两步指令（不自动执行）。

风险说明：
  - attackallfleets：官方描述「所有舰队瞄准所有其他舰队」，反编译显示会放松目标合法性判定；
    无法 100% 排除波及盟友，请在周围无友方舰队时谨慎开关。
  - surrender 对「天堂之战」等复杂多边战争的适用性未验证；对觉醒帝国投降可能换主子（慎）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import console_exec as ce  # noqa: E402

FLAG_VA = 0x1428147E0  # attackallfleets 开关字节区（handler 读 0x7E0、写 0x7E1）


def read_flag(h, base):
    b = ce.rpm(h, base + (FLAG_VA - 0x140000000), 2)
    return (b[0], b[1]) if b and len(b) == 2 else (None, None)


def show_wars():
    import situation_reader as sr

    sv, gs = sr.load()
    wars = gs.get("war") or {}
    country = gs.get("country") or {}

    def nm(cid):
        try:
            e = country.get(str(cid))
            if not isinstance(e, dict):
                return str(cid)
            n = e.get("name")
            if isinstance(n, dict):
                if n.get("key") == "%ADJECTIVE%":
                    parts = []
                    for v in n.get("variables", []):
                        val = v.get("value")
                        parts.append(str(val.get("key")) if isinstance(val, dict) else str(val))
                    return "+".join(parts)[:44]
                return str(n.get("key"))[:44]
            return str(n if n else cid)[:44]
        except Exception:
            return str(cid)

    def pid_of(p):
        return str(p.get("country")) if isinstance(p, dict) else str(p)

    print("save:", Path(sv).name, "| date:", gs.get("date"))
    for wid, w in wars.items():
        if not isinstance(w, dict):
            continue
        try:
            A = [pid_of(p) for p in sr.as_list(w.get("attackers"))]
            D = [pid_of(p) for p in sr.as_list(w.get("defenders"))]
        except Exception as e:
            print("war", wid, "parse err:", e)
            continue
        has_us = "0" in A or "0" in D
        mark = " ← 我方参战" if has_us else ""
        print("war %-9s | start %s | A(%d): %s | D(%d): %s%s"
              % (wid, w.get("start_date"), len(A), [nm(c) for c in A][:4],
                 len(D), [nm(c) for c in D][:4], mark))
        if has_us:
            g = w.get("attacker_war_goal")
            if isinstance(g, dict):
                print("     目标:", g.get("type"))


def main():
    args = sys.argv[1:]
    mode = args[0] if args else "status"

    if mode == "wars":
        show_wars()
        return

    if mode == "independence":
        print("独立战争操作指引（两步，均需自行确认后执行）：")
        print("  1) 对宗主宣战（宗主=你的 overlord 国家 id，当前为 1）：")
        print("       war 0 1 wg_independence")
        print("  2) （可选·核弹）开战后从 wars 子命令读出新战争 id，然后：")
        print("       python wartime.py win 1 <warid> --yes")
        print("  注意：天堂之战期间打独立会失去宗主阵营的保护，请评估后再动手。")
        return

    h, pid, base = ce.open_game()

    if mode == "status":
        a, b = read_flag(h, base)
        print("attackallfleets 状态字节: [0x%X]=%r  [0x%X]=%r（1=ON / 0=OFF）"
              % (FLAG_VA, a, FLAG_VA + 1, b))
        return

    if mode in ("attack_on", "attack_off", "on", "off"):
        if mode in ("attack_on", "on"):
            print("⚠ 提醒：该模式可能波及盟友/宗主/中立舰队——确认周围没有友方舰队再继续。")
        r = ce.execute_command(h, base, "attackallfleets")
        a1, b1 = read_flag(h, base)
        print("已切换（切换型命令）。ok=%s  状态: [0x%X]=%r  [0x%X]=%r"
              % (r.get("ok"), FLAG_VA, a1, FLAG_VA + 1, b1))
        return

    if mode == "navy":
        pct = args[1] if len(args) > 1 else "1.0"
        r = ce.execute_command(h, base, "create_navy " + pct)
        print("create_navy %s ->" % pct, r.get("ok"), repr(r.get("message")))
        return

    if mode == "invincible":
        r = ce.execute_command(h, base, "invincible")
        print("invincible（切换型）->", r.get("ok"), repr(r.get("message")))
        return

    if mode == "win":
        if len(args) < 3:
            print("用法: python wartime.py win <敌国id> <战争id> --yes")
            return
        cid, warid = args[1], args[2]
        if "--yes" not in args:
            print("将执行（核弹级，未真正执行——加 --yes 才生效）：")
            print("   surrender %s %s" % (cid, warid))
            print("   含义：令该敌国向战争 %s 投降（= 我方赢得该战争）。" % warid)
            return
        r = ce.execute_command(h, base, "surrender %s %s" % (cid, warid))
        print("surrender %s %s ->" % (cid, warid), r.get("ok"), repr(r.get("message")))
        return

    print("用法: python wartime.py [status|wars|attack_on|attack_off|navy [pct]|invincible|win <cid> <warid> [--yes]|independence]")


if __name__ == "__main__":
    main()
