# -*- coding: utf-8 -*-
"""Stellaris · AI 托管开关（游戏内风格悬浮面板 v2）

- 无边框、置顶、微透明，样式贴近游戏 UI（深蓝底 + 金色描边），可随意拖动
- 状态直读游戏内存："托管开关" + "游戏 运行中/暂停中"
- 点按钮 / 按 F8（全局热键）切换；切换有 1~3 秒生效延迟（游戏自身机制）
- 配合 hai_watch.py 看门狗：游戏一启动面板自动出现，游戏退出后面板自动退出

用法：
    python hai_ui.py            打开面板
    python hai_ui.py --selftest 只检测一次状态
"""
import json
import os
import sys
import time
import tkinter as tk
from pathlib import Path

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import console_exec as ce  # noqa: E402

POS_FILE = Path(__file__).resolve().parent / "_hai_ui_pos.json"
AWAY_FILE = Path(__file__).resolve().parent / "_away_mode.flag"
WAR_FILE = Path(__file__).resolve().parent / "_war_offensive.flag"
CLOSED_FLAG = Path(__file__).resolve().parent / "_hai_ui_closed.flag"

GOLD = "#c9a75f"
BG = "#0d1622"
BG2 = "#182640"
FG = "#e9e2d0"
FG_ON = "#7be08a"
FG_OFF = "#9aa4b2"
FG_ERR = "#e06c75"
FG_DIM = "#8b8468"

LANG_FILE = Path(__file__).resolve().parent / "_hai_ui_lang.json"

TEXTS = {
    "zh": {
        "win_title": "AI 托管",
        "app_title": "AI 托管 · STELLARIS",
        "checking": "检查中…",
        "btn": "切换　开 / 关",
        "away_on": "离开模式：开 ●",
        "away_off": "离开模式：关",
        "war_on": "战争模式：进攻 ●（F9）",
        "war_off": "战争模式：防御（F9）",
        "war_need_mod": "战争组件未安装（tools\\install_war_mod.py）",
        "war_need_restart": "战争组件未加载（需重启游戏）",
        "war_on_msg": "战争模式：进攻",
        "war_off_msg": "战争模式：防御",
        "war_fail": "战争切换失败: ",
        "hotkey": "F8 全局热键",
        "hotkey_na": "F8 热键不可用（用按钮）",
        "waiting": "等待游戏…",
        "wait_run": "等待游戏运行…",
        "state_on": "托管：开启中 ●",
        "state_off": "托管：已关闭",
        "pause_on": "游戏：暂停中（托管不推进）",
        "pause_run": "游戏：运行中",
        "pause_unk": "游戏：状态未知",
        "logpfx": "日志: ",
        "eng": "引擎: 武装%d · 改写%d · 拦截%d · 待决%s",
        "eng_nohook": "引擎: 钩子未装（游戏重启后自动重装）",
        "eng_dash": "引擎: —",
        "sent": "已发送切换",
        "fail": "失败",
        "takes": "（1~3 秒生效）",
        "lang_btn": "EN",
    },
    "en": {
        "win_title": "AI Steward",
        "app_title": "AI STEWARD · STELLARIS",
        "checking": "Checking...",
        "btn": "Toggle  ON / OFF",
        "away_on": "Away mode: ON ●",
        "away_off": "Away mode: OFF",
        "war_on": "War mode: ATTACK ● (F9)",
        "war_off": "War mode: DEFEND (F9)",
        "war_need_mod": "War component not installed (tools\\install_war_mod.py)",
        "war_need_restart": "War component not loaded (restart the game)",
        "war_on_msg": "War mode: attack",
        "war_off_msg": "War mode: defend",
        "war_fail": "War toggle failed: ",
        "hotkey": "F8 global hotkey",
        "hotkey_na": "F8 unavailable (use button)",
        "waiting": "Waiting for game...",
        "wait_run": "Waiting for game...",
        "state_on": "Autopilot: ON ●",
        "state_off": "Autopilot: OFF",
        "pause_on": "Game: paused (autopilot idle)",
        "pause_run": "Game: running",
        "pause_unk": "Game: unknown state",
        "logpfx": "Log: ",
        "eng": "Engine: armed %d · rewrites %d · blocked %d · pending %s",
        "eng_nohook": "Engine: hook not installed (auto-reinstalls)",
        "eng_dash": "Engine: —",
        "sent": "toggle sent",
        "fail": "failed",
        "takes": " (1-3 s)",
        "lang_btn": "中",
    },
}


def game_running():
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            n = (p.info["name"] or "").lower()
            if n in ("stellaris.exe", "stellaris"):
                return True
    except Exception:
        return True  # 无法判断时不触发自动退出
    return False


class App:
    def __init__(self):
        self.h = None
        self.base = None
        self.pending = False
        self.pending_war = False
        self.last_err = ""
        self.gone_since = None
        self.drag = (0, 0)
        self.last_toggle = 0.0
        self.lang = "zh"
        try:
            _d = json.loads(LANG_FILE.read_text(encoding="utf-8"))
            if _d.get("lang") in ("zh", "en"):
                self.lang = _d["lang"]
        except Exception:
            pass
        try:            # 面板已在运行 → 清掉"用户关闭"标记（下次异常消失可自动补拉）
            if CLOSED_FLAG.exists():
                CLOSED_FLAG.unlink()
        except Exception:
            pass

        self.root = tk.Tk()
        self.root.title(self.t("win_title"))
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 0.95)
        except Exception:
            pass
        self.root.configure(bg=GOLD)  # 1px 金边
        self.root.geometry(self._load_pos())

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=1, pady=1)

        bar = tk.Frame(wrap, bg=BG)
        bar.pack(fill="x", padx=8, pady=(6, 0))
        self.title_lbl = tk.Label(bar, text=self.t("app_title"), font=("Microsoft YaHei UI", 8, "bold"),
                                  fg=GOLD, bg=BG)
        self.title_lbl.pack(side="left")
        self.lang_lbl = tk.Label(bar, text=self.t("lang_btn"),
                                 font=("Microsoft YaHei UI", 8, "bold"), fg=FG_DIM, bg=BG, cursor="hand2")
        self.lang_lbl.pack(side="right", padx=(0, 8))
        self.lang_lbl.bind("<Button-1>", lambda e: self.switch_lang())
        close = tk.Label(bar, text="✕", font=("Microsoft YaHei UI", 9, "bold"),
                         fg=FG_DIM, bg=BG, cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self.on_close())
        for w in (bar, self.title_lbl):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        self.state_lbl = tk.Label(wrap, text=self.t("checking"), font=("Microsoft YaHei UI", 15, "bold"),
                                  fg=FG_OFF, bg=BG)
        self.state_lbl.pack(padx=16, pady=(4, 2))
        self.state_lbl.bind("<Button-1>", self._drag_start)
        self.state_lbl.bind("<B1-Motion>", self._drag_move)

        self.sub_lbl = tk.Label(wrap, text="", font=("Microsoft YaHei UI", 9), fg=FG_DIM, bg=BG)
        self.sub_lbl.pack(padx=16, pady=(0, 4))

        self.btn = tk.Button(
            wrap, text=self.t("btn"), command=self.request_toggle,
            font=("Microsoft YaHei UI", 10), bg=BG2, fg=FG,
            activebackground="#22375c", activeforeground="#ffffff",
            relief="flat", padx=10, pady=6, bd=0,
            highlightthickness=1, highlightbackground=GOLD, highlightcolor=GOLD)
        self.btn.pack(padx=14, pady=(2, 4), fill="x")

        self.away_btn = tk.Button(
            wrap, text=self.t("away_off"), command=self.toggle_away,
            font=("Microsoft YaHei UI", 9), bg=BG, fg=FG_DIM,
            activebackground="#1d2c46", activeforeground=FG,
            relief="flat", bd=0, padx=8, pady=3,
            highlightthickness=1, highlightbackground="#3a4757", highlightcolor="#3a4757")
        self.away_btn.pack(padx=14, pady=(0, 2), fill="x")

        self.war_btn = tk.Button(
            wrap, text=self.t("war_off"), command=self.toggle_war,
            font=("Microsoft YaHei UI", 9), bg=BG, fg=FG_DIM,
            activebackground="#1d2c46", activeforeground=FG,
            relief="flat", bd=0, padx=8, pady=3,
            highlightthickness=1, highlightbackground="#3a4757", highlightcolor="#3a4757")
        self.war_btn.pack(padx=14, pady=(0, 2), fill="x")

        self.info_lbl = tk.Label(wrap, text=self.t("hotkey"), font=("Microsoft YaHei UI", 8),
                                 fg="#6d7686", bg=BG)
        self.info_lbl.pack(padx=16, pady=(0, 8))

        self.adv_lbl = tk.Label(wrap, text="", font=("Microsoft YaHei UI", 8),
                                fg="#5f6b7d", bg=BG, wraplength=170, justify="left")
        self.adv_lbl.pack(padx=16, pady=(0, 8))
        self._log_t = 0.0
        self.eng_lbl = tk.Label(wrap, text=self.t("eng_dash"), font=("Microsoft YaHei UI", 8),
                                fg="#7f8ea3", bg=BG, wraplength=170, justify="left")
        self.eng_lbl.pack(padx=16, pady=(0, 8))
        self._eng_t = 0.0

        try:
            import keyboard
            keyboard.add_hotkey("f8", self._hotkey)
            keyboard.add_hotkey("f9", self._war_hotkey)
            self.kb = True
        except Exception:
            self.kb = False
            self.info_lbl.config(text=self.t("hotkey_na"))

        self.apply_lang()
        self.tick()
        self.root.mainloop()

    # ---------- 拖动 / 位置 ----------
    def _drag_start(self, e):
        self.drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self.drag[0]}+{e.y_root - self.drag[1]}")

    # ---------- 语言 ----------
    def t(self, key):
        return TEXTS.get(self.lang, TEXTS["zh"]).get(key, key)

    def switch_lang(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        try:
            LANG_FILE.write_text(json.dumps({"lang": self.lang}), encoding="utf-8")
        except Exception:
            pass
        self.apply_lang()

    def apply_lang(self):
        try:
            self.root.title(self.t("win_title"))
            self.title_lbl.config(text=self.t("app_title"))
            self.lang_lbl.config(text=self.t("lang_btn"))
            self.btn.config(text=self.t("btn"))
            self.info_lbl.config(text=self.t("hotkey") if getattr(self, "kb", False) else self.t("hotkey_na"))
            self.away_btn.config(text=(self.t("away_on") if AWAY_FILE.exists() else self.t("away_off")))
            self.war_btn.config(text=(self.t("war_on") if WAR_FILE.exists() else self.t("war_off")),
                                fg=(FG_ON if WAR_FILE.exists() else FG_DIM))
            self.eng_lbl.config(text=self.t("eng_dash"))
            self.state_lbl.config(text=self.t("checking"))
        except Exception:
            pass

    def _load_pos(self):
        try:
            d = json.loads(POS_FILE.read_text(encoding="utf-8"))
            x = max(0, min(int(d["x"]), self.root.winfo_screenwidth() - 260))
            y = max(0, min(int(d["y"]), self.root.winfo_screenheight() - 260))
            return f"+{x}+{y}"
        except Exception:
            return "+40+90"

    def on_close(self):
        self._close(by_user=True)

    def _close(self, by_user=True):
        try:
            POS_FILE.write_text(json.dumps({
                "x": self.root.winfo_x(), "y": self.root.winfo_y(),
            }), encoding="utf-8")
        except Exception:
            pass
        try:
            if by_user:
                CLOSED_FLAG.touch()
            elif CLOSED_FLAG.exists():
                CLOSED_FLAG.unlink()
        except Exception:
            pass
        self.root.destroy()

    # ---------- 开关 ----------
    def _hotkey(self):
        if time.time() - self.last_toggle < 2.5:
            return
        self.pending = True

    def _war_hotkey(self):
        self.pending_war = True

    def request_toggle(self):
        if time.time() - self.last_toggle < 2.5:
            return
        self.pending = True

    def toggle_away(self):
        try:
            if AWAY_FILE.exists():
                AWAY_FILE.unlink()
            else:
                AWAY_FILE.touch()
        except Exception:
            pass

    def toggle_war(self):
        """切换战争组件的进攻模式（需已安装 ai_steward_war 并重启游戏）。"""
        try:
            import war_mode
            if not war_mode.mod_enabled():
                self.info_lbl.config(text=self.t("war_need_mod"))
                return
        except Exception:
            pass
        if self.h is None:
            self._ensure_open()
        if self.h is None:
            return
        want_on = not WAR_FILE.exists()
        ev = "ai_steward_war.10" if want_on else "ai_steward_war.11"
        try:
            r = ce.execute_command(self.h, self.base, "event " + ev)
            msg = str(r.get("message") or "").lower()
            bad = any(w in msg for w in ("not found", "invalid", "unknown", "no event"))
            if r.get("ok") and not bad:
                if want_on:
                    WAR_FILE.touch()
                elif WAR_FILE.exists():
                    WAR_FILE.unlink()
                self.info_lbl.config(text=self.t("war_on_msg") if want_on else self.t("war_off_msg"))
            else:
                self.info_lbl.config(text=self.t("war_need_restart"))
        except Exception as e:
            self.info_lbl.config(text=(self.t("war_fail") + str(e))[:60])
        try:
            self.war_btn.config(text=(self.t("war_on") if WAR_FILE.exists() else self.t("war_off")),
                                fg=(FG_ON if WAR_FILE.exists() else FG_DIM))
        except Exception:
            pass

    def _ensure_open(self):
        if self.h is not None:
            return True
        try:
            self.h, self.pid, self.base = ce.open_game()
            self.last_err = ""
            return True
        except Exception as e:
            self.last_err = str(e)
            return False

    def _drop(self):
        self.h = None
        self.base = None

    # ---------- 主循环 ----------
    def tick(self):
        try:
            self._tick_inner()
        finally:
            self._n = getattr(self, "_n", 0) + 1
            if self._n % 16 == 0:
                # 被"显示桌面 / 最小化"藏起来时自动找回（overrideredirect 窗口的保险）
                try:
                    if not self.root.winfo_viewable():
                        self.root.deiconify()
                        self.root.lift()
                        self.root.attributes("-topmost", True)
                except Exception:
                    pass
            self.root.after(900, self.tick)

    def _tick_inner(self):
        away = AWAY_FILE.exists()
        self.away_btn.config(
            text=(self.t("away_on") if away else self.t("away_off")),
            fg=(FG_ON if away else FG_DIM))
        # 决策日志最新一条 → 面板显示（每 5 秒刷新）
        if time.time() - self._log_t > 5:
            self._log_t = time.time()
            try:
                lp = ROOT / "logs" / "decisions.log"
                if lp.exists():
                    tail = lp.read_bytes()[-3000:].decode("utf-8", "replace")
                    lines = [ln for ln in tail.splitlines() if ln.strip()]
                    if lines:
                        line = lines[-1]
                        parts = line.split("  ", 1)
                        if len(parts) > 1:
                            line = parts[1]
                        self.adv_lbl.config(text=self.t("logpfx") + line[:58])
            except Exception:
                pass
        if not self._ensure_open():
            if game_running():
                self.gone_since = None
                txt = self.last_err or self.t("waiting")
                self.state_lbl.config(text=txt[:22], fg=FG_ERR)
            else:
                if self.gone_since is None:
                    self.gone_since = time.time()
                elif time.time() - self.gone_since > 45:
                    self._close(by_user=False)  # 游戏关闭 → 面板自动退出（下次由看门狗拉起）
                    return
                self.state_lbl.config(text=self.t("wait_run"), fg="#5c6472")
                self.sub_lbl.config(text="")
            return

        flag = ce.read_flag(self.h, self.base, ce.RVA_HUMAN_AI)
        if flag is None:
            self._drop()
            return

        # 引擎状态：武装/改写/归属拦截/待决事件（每 5 秒刷新）
        if time.time() - self._eng_t > 5:
            self._eng_t = time.time()
            try:
                import struct as _st
                stt = json.loads((Path(__file__).resolve().parent / "_hook_state_rw88.json")
                                 .read_text(encoding="utf-8"))
                if int(stt.get("base") or 0) == self.base:
                    raw = ce.rpm(self.h, stt["scratch"], 0x1D0)
                    rwn = _st.unpack_from("<Q", raw, 0x28)[0]
                    blk = _st.unpack_from("<Q", raw, 0x1C4)[0]
                    nsl = 0
                    for k in range(24):
                        s = _st.unpack_from("<IIII", raw, 0x38 + k * 16)
                        if s[0] == 1:
                            nsl += 1
                    import evt_select as _es
                    pd = _es.pending_events(self.h, self.base)
                    npd = str(len(pd)) if pd is not None else "?"
                    self.eng_lbl.config(text=self.t("eng") % (nsl, rwn, blk, npd))
                else:
                    self.eng_lbl.config(text=self.t("eng_nohook"))
            except Exception:
                pass

        if self.pending:
            self.pending = False
            self.last_toggle = time.time()
            r = ce.execute_command(self.h, self.base, "human_ai")
            msg = r.get("message") or (self.t("sent") if r["ok"] else self.t("fail"))
            self.info_lbl.config(text=f"{msg}{self.t('takes')}")
            flag = ce.read_flag(self.h, self.base, ce.RVA_HUMAN_AI)
            if flag is None:
                self._drop()
                return

        if self.pending_war:
            self.pending_war = False
            self.toggle_war()

        if flag == 1:
            self.state_lbl.config(text=self.t("state_on"), fg=FG_ON)
        else:
            self.state_lbl.config(text=self.t("state_off"), fg=FG_OFF)

        pv = ce.read_pause(self.h, self.base)
        if pv == 1:
            self.sub_lbl.config(text=self.t("pause_on"), fg="#e0a458")
        elif pv == 0:
            self.sub_lbl.config(text=self.t("pause_run"), fg=FG_DIM)
        else:
            self.sub_lbl.config(text=self.t("pause_unk"), fg=FG_DIM)


def selftest():
    try:
        h, pid, base = ce.open_game()
        print(f"selftest: pid={pid} human_ai={ce.read_flag(h, base, ce.RVA_HUMAN_AI)} "
              f"pause={ce.read_pause(h, base)}")
        ce.k32.CloseHandle(ce.ctypes.c_void_p(h))
    except Exception as e:
        print("selftest:", e)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        import ctypes
        _k = ctypes.WinDLL("kernel32", use_last_error=True)
        _k.CreateMutexW.restype = ctypes.c_void_p
        _mtx = _k.CreateMutexW(None, False, "CodexStellarisHaiUiMutex")
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            sys.exit(0)
        App()
