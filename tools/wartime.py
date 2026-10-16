# -*- coding: utf-8 -*-
"""战时应急开关：attackallfleets —— 让己方全部舰队进入全面交战模式。

用法（游戏运行时）：
  python wartime.py status   查看开关字节当前值（只读，零风险）
  python wartime.py on       切换为全面交战模式（⚠ 见下方风险说明）
  python wartime.py off      关闭（再切一次即可）

风险说明（知情后再用）：
  - 官方描述为「Makes all fleets target all other fleets」；反编译确认它是全局开关，
    会放松「目标合法性判定」；无法静态 100% 排除波及盟友/宗主/中立的可能。
  - 建议在「舰队周围没有盟友/宗主舰队」的时机开启；任何时刻可再执行一次关闭。
  - 该命令是「切换型」：若当前已是 ON，执行 on 反而会关掉——请以 status 输出为准。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import console_exec as ce  # noqa: E402

FLAG_VA = 0x1428147E0  # attackallfleets 开关字节区（handler 读 0x7E0、写 0x7E1）


def read_flag(h, base):
    b = ce.rpm(h, base + (FLAG_VA - 0x140000000), 2)
    return (b[0], b[1]) if b and len(b) == 2 else (None, None)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    h, pid, base = ce.open_game()
    a, b = read_flag(h, base)
    if mode == "status":
        print("attackallfleets 状态字节: [0x%X]=%r  [0x%X]=%r（1=ON / 0=OFF）"
              % (FLAG_VA, a, FLAG_VA + 1, b))
        return
    if mode in ("on", "off"):
        if mode == "on":
            print("⚠ 提醒：该模式可能波及盟友/宗主/中立舰队——确认周围没有友方舰队再继续。")
        r = ce.execute_command(h, base, "attackallfleets")
        a1, b1 = read_flag(h, base)
        print("已切换（切换型命令）。状态: [0x%X]=%r→%r  [0x%X]=%r→%r  ok=%s"
              % (FLAG_VA, a, a1, FLAG_VA + 1, b, b1, r.get("ok")))
        print("如需回到另一状态，再执行一次即可。")
        return
    print("用法: python wartime.py [status|on|off]")


if __name__ == "__main__":
    main()
