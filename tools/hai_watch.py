# -*- coding: utf-8 -*-
"""看门狗：Stellaris 一启动就自动拉起"AI 托管"面板。

- 每 4 秒检查一次 stellaris.exe
- 游戏从"未运行"变为"运行"时（或看门狗启动时游戏已在运行）拉起面板
- 你自己关掉面板后，本局游戏内不会再弹（下次启动游戏才会再拉起）

用法：pythonw hai_watch.py   （已注册到开机启动项，随登录常驻）
"""
import ctypes
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")

try:
    import psutil
except ImportError:
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
PYW = ROOT / ".venv" / "Scripts" / "pythonw.exe"
UI = ROOT / "tools" / "hai_ui.py"
BRAIN = ROOT / "tools" / "brain.py"
LOG = ROOT / "tools" / "_watch.log"
CLOSED_FLAG = ROOT / "tools" / "_hai_ui_closed.flag"   # 用户主动关面板 → 本局不再补拉；异常消失则自动补拉


def log(msg):
    try:
        if LOG.exists() and LOG.stat().st_size > 1_000_000:
            bak = LOG.with_name(LOG.name + ".1")
            try:
                if bak.exists():
                    bak.unlink()
                LOG.rename(bak)
            except Exception:
                pass
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


def game_running():
    for p in psutil.process_iter(["name"]):
        n = (p.info["name"] or "").lower()
        if n in ("stellaris.exe", "stellaris"):
            return True
    return False


def panel_running():
    for p in psutil.process_iter(["name", "cmdline"]):
        nm = (p.info["name"] or "").lower()
        if "python" not in nm:
            continue  # 只认 python 解释器进程，避免把"命令行里提到脚本名"的 shell 误判
        try:
            cl = p.info["cmdline"] or []
        except Exception:
            continue
        if any("hai_ui.py" in str(x) for x in cl):
            return True
    return False


def brain_running():
    for p in psutil.process_iter(["name", "cmdline"]):
        nm = (p.info["name"] or "").lower()
        if "python" not in nm:
            continue
        try:
            cl = p.info["cmdline"] or []
        except Exception:
            continue
        if any("brain.py" in str(x) for x in cl):
            return True
    return False


def main():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    mtx = k32.CreateMutexW(None, False, "CodexStellarisWatchMutex")
    if not mtx or ctypes.get_last_error() == 183:  # 已有看门狗在跑 → 直接退出
        return
    log(f"watchdog start, pyw exists={PYW.exists()}, ui exists={UI.exists()}")
    launched = False   # 本局游戏是否已经拉起过面板
    dbg = 0
    while True:
        try:
            cur = game_running()
            pan = panel_running()
            if dbg < 5:
                log(f"loop: game={cur} panel={pan} launched={launched}")
                dbg += 1
            if not brain_running():
                try:
                    subprocess.Popen([str(PYW), str(BRAIN)], cwd=str(ROOT))
                    log("brain launched")
                except Exception:
                    log("brain launch failed:\n" + traceback.format_exc())
            if not cur:
                launched = False           # 游戏关了 → 下次启动再拉起
                try:
                    if CLOSED_FLAG.exists():
                        CLOSED_FLAG.unlink()
                except Exception:
                    pass
            else:
                if pan:
                    launched = True        # 面板已在（无论谁拉起的）
                elif not launched:
                    try:
                        subprocess.Popen([str(PYW), str(UI)], cwd=str(ROOT))
                        log("panel launched")
                    except Exception:
                        log("launch failed:\n" + traceback.format_exc())
                    launched = True        # 本局只自动拉起一次；你手动关掉就不再弹
                elif not CLOSED_FLAG.exists():
                    try:                   # 面板中途消失且非"用户主动关闭" → 崩溃自动补拉
                        subprocess.Popen([str(PYW), str(UI)], cwd=str(ROOT))
                        log("panel relaunch (previous instance vanished unexpectedly)")
                    except Exception:
                        log("relaunch failed:\n" + traceback.format_exc())
        except Exception:
            log("loop error:\n" + traceback.format_exc())
        time.sleep(4)


if __name__ == "__main__":
    main()
