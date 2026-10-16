# -*- coding: utf-8 -*-
"""Stellaris 托管决策大脑 v1（常驻守护：观察状态 + 事件卡死自愈 + 决策日志）

规则（当前版本）：
  R1 事件处理（v1.1，2026-10-16 打通内存级选项选择）：
     托管开启时，每 8 秒扫描"待决事件"：
       - 唯一选项事件 → 自动选择（等价点击"确定"），写决策日志；
       - 多选项事件 → 决策器自动选择（人工覆盖 > ai 基础权重 > 首个无触发选项）；
         无法安全决策（未收录 / 选项数不符）时仅记录日志、不自动执行。
     托管关闭 + 离开模式（面板按钮）时也处理事件，但仅限停留超过 45 秒的（给在座的玩家观察窗）；
     两者都不是时绝不动作（不打扰手动玩家）。
  R2 资源心跳：每 10 分钟记录一次 12 项资源（内存直读）；疑似顶到存储上限时标注。
  R3 状态变迁：托管开关 / 暂停状态每次变化都记一条。

日志：autopilot\\logs\\decisions.log
单实例锁：CodexStellarisBrainMutex（由 hai_watch.py 看门狗常驻保障）
"""
import ctypes
import json
import os
import re
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import console_exec as ce  # noqa: E402

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG = LOG_DIR / "decisions.log"
AWAY_FILE = ROOT / "tools" / "_away_mode.flag"   # 存在 = 离开模式开启（面板按钮控制）
STATE_FILE = ROOT / "tools" / "_brain_state.json"  # 大脑跨重启状态（军力基线等）
RES_FILE = ROOT / "tools" / "_brain_res.json"      # 资源块连续性缓存（地址+实读值）
AUDIT_FILE = ROOT / "tools" / "_brain_audit.json"  # 审计读写游标（跨重启零断档）
TPLMAP_FILE = ROOT / "data" / "evt_tpl_map.json"   # 事件名→模板 id 缓存（按名武装用）
STANDING_FILE = ROOT / "data" / "evt_standing.json"  # 按名武装规则持久化（重启后立即恢复覆盖）
SAVES_DIR = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris" / "save games"
GAMELOG = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris" / "logs" / "game.log"
AUDIT_RE = re.compile(
    r"\[(\d+:\d+:\d+)\]\[eventcommands\.cpp:88\]: Event (\S+) added info about event selection\. "
    r"selectedOption (\d+), human (-?\d+), playerEventId (\d+)")

R1_EVENT_INTERVAL = 8   # 秒：R1 待决事件扫描间隔
AWAY_GRACE_EVENT = 15   # 秒：离开模式下，事件停留多久才自动处理（给"其实在座的玩家"留观察窗；
                        # 45s → 15s：高频事件时游戏暂停占比过高，缩短以提升挂机推进效率）
RES_LOG_INTERVAL = 600  # 秒：资源心跳间隔
AWAY_GRACE = 90         # 秒：离开模式下，检测到暂停后等待多久自动继续
AWAY_RESUME_OFF = 6     # 秒：离开模式(托管OFF)下，空闲暂停超此时长且无待决事件 → 自动恢复运行
                        # （15→6：空闲模组约每 40-50 秒暂停一次，缩短阈值把运行占比从 ~40% 提到 ~85%；
                        #  仍高于 R1 单步注入暂停时长，两者互不干扰）
WIN_CLEAN_INTERVAL = 45  # 秒：离开模式下外交/通知窗口自动清理间隔（2026-10-17 新增 R8）
WIN_TARGETS = [
    "incoming_diplomacy_view_action_war_peace",  # 宣战/和平"收件"窗口（实测被宣战后该窗滞留屏幕）
]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    try:
        if LOG.exists() and LOG.stat().st_size > 2_000_000:
            bak = LOG.with_name(LOG.name + ".1")
            try:
                if bak.exists():
                    bak.unlink()
                LOG.rename(bak)
            except Exception:
                pass
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{now()}  {msg}\n")
    except Exception:
        pass


def latest_save_mtime():
    best = 0.0
    try:
        for f in SAVES_DIR.rglob("*.sav"):
            try:
                m = f.stat().st_mtime
                if m > best:
                    best = m
            except OSError:
                pass
    except Exception:
        pass
    return best


def load_state():
    try:
        import json
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return (float(d.get("prev_mil", 0) or 0), int(d.get("last_techs", 0) or 0),
                float(d.get("last_fleet", 0) or 0), int(d.get("fleet_streak", 0) or 0))
    except Exception:
        return 0.0, 0, 0.0, 0


class Brain:
    def __init__(self):
        self.h = None
        self.base = None
        self.last_r1 = 0.0
        self.seen_events = set()
        self.evt_first_seen = {}
        self._gl_off = None
        self.audit_seen = set()
        try:
            import json
            d = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
            self._gl_off = int(d.get("off", 0))
            self.audit_seen = set(d.get("seen", []) or [])
        except Exception:
            self._gl_off = None
        self.last_res = 0.0
        self.prev_hai = None
        self.prev_pause = None
        self.res_base = None
        self.last_addr = None
        self.away_prev = None
        self.away_since = None
        self.away2_since = None
        self.save_mtime = 0.0
        self.last_attempt = 0.0
        self.standing = {}      # 按名武装：name → {tpl, opt, ts}
        try:
            d0 = json.loads(STANDING_FILE.read_text(encoding="utf-8"))
            if isinstance(d0, dict):
                nowt0 = time.time()
                for nm, e in d0.items():
                    if isinstance(e, dict) and e.get("tpl") and (nowt0 - float(e.get("ts") or 0)) < 86400:
                        self.standing[nm] = {"tpl": int(e["tpl"]), "opt": int(e.get("opt") or 0),
                                             "ts": float(e.get("ts") or 0)}
        except Exception:
            pass
        self._last_rw_log = None
        self.last_r6 = 0.0
        self.last_win_clean = 0.0
        self._win_enabled_logged = False
        self.cnt_ladder = 0     # 本进程：天梯成功数
        self.cnt_single = 0     # 本进程：单选项成功数
        self.cnt_fail = 0       # 本进程：失败数
        self.prev_mil, self.last_techs, self.last_fleet, self.fleet_streak = load_state()
        self.prev_own_wars = None
        self.last_r5 = 0.0
        self.last_vals = None
        self.prev_advs = ""
        self.was_connected = False
        self.last_sv = ""
        try:
            import json
            d = json.loads(RES_FILE.read_text(encoding="utf-8"))
            self.last_addr = d.get("base")
            self.last_vals = d.get("vals")
        except Exception:
            pass

    def ensure(self):
        if self.h is not None:
            return True
        try:
            self.h, self.pid, self.base = ce.open_game()
            log(f"[连接] 游戏 pid={self.pid} base=0x{self.base:X}")
            return True
        except Exception:
            return False

    def drop(self):
        self.h = None
        self.base = None

    # ---------- R1: 待决事件处理（内存级注入 + 探测天梯 + 托管改写 v1.2） ----------
    def _away_resume_if_needed(self):
        """离开模式（托管 OFF）下：事件处理完毕后若仍暂停 → 自动恢复运行（不冻结游戏）"""
        try:
            if not AWAY_FILE.exists():
                return
            if ce.read_flag(self.h, self.base, ce.RVA_HUMAN_AI) == 1:
                return  # 托管 ON 属 R4 管辖
            time.sleep(1.2)
            if ce.read_pause(self.h, self.base) == 1:
                r = ce.execute_command(self.h, self.base, "game_paused false")
                log(f"[R1] 离开模式：事件处理后已自动恢复运行（ok={r.get('ok')}）")
        except Exception as ex:
            log(f"[R1] 自动恢复异常：{ex}")

    def _ensure_rw88(self):
        """离开模式：确保 rw88 改写钩子在线。
        校验三级：state(base+ver) → 入口 14 字节是 FF25 跳转 → 跳转目标==state.cave；
        任一级不符即「还原+重装」自愈（覆盖游戏重启 / 被外部还原 / 旧版本残留）。"""
        try:
            import importlib, json as _js
            hr = importlib.import_module("hook_rw88")
            ok = False
            st = None
            try:
                st = _js.loads(hr.STATE.read_text(encoding="utf-8"))
                ok = (int(st.get("base") or 0) == int(self.base or 0)
                      and int(st.get("ver") or 0) == hr.STATE_VER)
            except Exception:
                ok = False
            if ok:
                b = ce.rpm(self.h, self.base + hr.RVA_FN, 14)
                tgt = struct.unpack_from("<Q", b, 6)[0] if (b and len(b) >= 14) else 0
                ok = bool(b and b[:2] == b"\xFF\x25" and tgt == int(st.get("cave") or 0))
            if not ok:
                if time.time() - getattr(self, "_rw_retry", 0.0) < 60:
                    return False          # 失败冷却：自愈最多每分钟一次，避免抖动
                self._rw_retry = time.time()
                try:
                    hr.revert()           # 幂等：还原原始序言（重装前置条件）
                except Exception:
                    pass
                ok2 = False
                try:
                    ok2 = (hr.install(rw=True) == 0)
                except Exception:
                    ok2 = False
                if not ok2:
                    try:                  # 极端兜底：直接写回原序言再装
                        fn = self.base + hr.RVA_FN
                        orig = bytes.fromhex(hr.EXPECT_ORIG)
                        op = ctypes.c_uint32(0)
                        k32 = ce.k32
                        k32.VirtualProtectEx(ctypes.c_void_p(self.h), ctypes.c_void_p(fn), 64, 0x40,
                                             ctypes.byref(op))
                        k32.WriteProcessMemory(ctypes.c_void_p(self.h), ctypes.c_void_p(fn), orig,
                                               len(orig), None)
                        k32.VirtualProtectEx(ctypes.c_void_p(self.h), ctypes.c_void_p(fn), 64,
                                             op.value, ctypes.byref(op))
                        ok2 = (hr.install(rw=True) == 0)
                    except Exception as ex2:
                        ok2 = False
                if not ok2:
                    log("[R1] rw88 钩子重装失败（下轮重试）")
                    return False
                self._last_rules = None   # 重装后武装表为空 → 下轮扫描自动重建
                log("[R1] rw88 改写钩子已安装（或重装）")
            return True
        except Exception as ex:
            log(f"[R1] rw88 钩子保障失败：{ex}")
            return False

    def rule_health(self, hai):
        """R6 健康心跳（每 10 分钟一行日志）：钩子在线性/武装/改写/拦截/待决 + 本进程处理统计。"""
        if time.time() - self.last_r6 < 600:
            return
        self.last_r6 = time.time()
        try:
            import importlib, json as _js
            hr = importlib.import_module("hook_rw88")
            if AWAY_FILE.exists():
                self._ensure_rw88()
            b = ce.rpm(self.h, self.base + hr.RVA_FN, 14)
            hook_ok = bool(b and b[:2] == b"\xFF\x25")
            nsl = rwn = blk = -1
            try:
                stt = _js.loads(hr.STATE.read_text(encoding="utf-8"))
                if int(stt.get("base") or 0) == self.base:
                    raw = ce.rpm(self.h, stt["scratch"], 0x1D0)
                    rwn = struct.unpack_from("<Q", raw, 0x28)[0]
                    blk = struct.unpack_from("<Q", raw, 0x1C4)[0]
                    nsl = sum(1 for k in range(24)
                              if struct.unpack_from("<I", raw, 0x38 + k * 16)[0] == 1)
            except Exception:
                pass
            es = importlib.import_module("evt_select")
            pd = es.pending_events(self.h, self.base)
            npd = len(pd) if pd is not None else -1
            log(f"[R6] 健康：钩子={'在线' if hook_ok else '离线'} 武装{nsl}条 改写{rwn} 拦截{blk} 待决{npd}"
                f" | 本进程 天梯{self.cnt_ladder} 单选项{self.cnt_single} 失败{self.cnt_fail}")
        except Exception as ex:
            log(f"[R6] 健康检查异常：{ex}")

    def _inject_with_pause(self, ev, idx):
        """注入选项（注入要求暂停）。成功由调用方恢复；失败且由我方暂停则立即恢复。"""
        import importlib
        es = importlib.import_module("evt_select")
        was = ce.read_pause(self.h, self.base)
        paused_by_us = False
        ok = False
        try:
            if was != 1:
                ce.execute_command(self.h, self.base, "game_paused true")
                time.sleep(0.5)
                paused_by_us = True
            ok = bool(es.select_option(self.h, self.base, ev, idx))
        except Exception as ex:
            log(f"[R1] 注入异常：{ex}")
        finally:
            if not ok and paused_by_us:
                ce.execute_command(self.h, self.base, "game_paused false")
                time.sleep(0.2)
        return ok

    def _ladder(self, ev):
        """探测天梯：按参谋偏好顺序注入；第一个被游戏接受（触发器合法）的选项即采用。
        被拒项静默跳过（游戏侧校验），无需在 Python 侧复刻触发器求值。"""
        import importlib
        ed = importlib.import_module("evt_decide")
        cands = ed.candidates(ev["name"], ev.get("n_opts"))
        tried = []
        for k, why in cands:
            if self._inject_with_pause(ev, k):
                otext = ed.option_text(ev["name"], k)
                extra = ("（跳过被拒项 %s）" % [t[0] for t in tried]) if tried else ""
                log(f"[R1] 多选项事件决策：{ev['name']} id={ev['iid']} → 选项{k}"
                    f"「{otext[:36]}」依据：{why}{extra}；执行=成功")
                return k
            tried.append((k, why))
        log(f"[R1] 多选项事件决策：{ev['name']} id={ev['iid']} 候选全被拒："
            f"{[(t[0], t[1][:16]) for t in tried]}；执行=失败")
        return None

    def _decide_arm(self, name, n_opts):
        """返回 (option, reason)：首个"无触发器"候选（预期必合法）；无法确定返回 None。"""
        try:
            import importlib
            ed = importlib.import_module("evt_decide")
            for k, why in ed.candidates(name, n_opts):
                if ed.option_has_trigger(name, k) is False:
                    return k, why
        except Exception:
            pass
        return None

    def _tpl_of(self, name, obj):
        """事件名→模板 id：在游戏事件注册表里按事件 def 指针定位。
        模板 id = 命名空间序*100000 + 表内序（与 exec 的查找公式一致）。带磁盘缓存。"""
        try:
            import json as _js
            cache = {}
            if TPLMAP_FILE.exists():
                try:
                    cache = _js.loads(TPLMAP_FILE.read_text(encoding="utf-8"))
                except Exception:
                    cache = {}
            if name in cache:
                return int(cache[name])
            if not obj:
                return None
            reg = struct.unpack("<Q", ce.rpm(self.h, self.base + 0x3152CA8, 8))[0]
            if not reg:
                return None
            ns_cnt = struct.unpack("<i", ce.rpm(self.h, reg + 0x3C, 4))[0]
            ns_arr = struct.unpack("<Q", ce.rpm(self.h, reg + 0x30, 8))[0]
            if not (0 < ns_cnt <= 4096) or not ns_arr:
                return None
            for i in range(ns_cnt):
                ent = ns_arr + i * 0x18
                cnt = struct.unpack("<i", ce.rpm(self.h, ent + 0x14, 4))[0]
                ptr = struct.unpack("<Q", ce.rpm(self.h, ent + 8, 8))[0]
                if not (0 < cnt <= 65536) or not ptr:
                    continue
                for k in range(cnt):
                    cell = struct.unpack("<Q", ce.rpm(self.h, ptr + k * 8, 8))[0]
                    defp = struct.unpack("<Q", ce.rpm(self.h, cell, 8))[0] if cell else 0
                    if defp == obj:
                        tpl = i * 100000 + k
                        cache[name] = tpl
                        try:
                            TPLMAP_FILE.write_text(_js.dumps(cache, ensure_ascii=False), encoding="utf-8")
                        except Exception:
                            pass
                        return tpl
        except Exception as ex:
            log(f"[R1] 模板解析异常：{ex}")
        return None

    def _sync_standing(self, pend):
        """按名预武装：观察到的多选项事件若有"无触发器"首选候选 → 解析模板 id 写武装表。
        家族 1 小时未见即失效；全表变化才重写（hook_rw88.set_slots）。"""
        try:
            import importlib
            hr = importlib.import_module("hook_rw88")
            nowt = time.time()
            changed = False
            for ev in pend:
                name = ev.get("name")
                n = ev.get("n_opts") or 0
                if not name or not ev.get("gate") or n < 2:
                    continue
                ent = self.standing.get(name)
                if ent and nowt - ent.get("ts", 0) < 3600:
                    if ent.get("opt") is not None and ent["opt"] >= n:
                        self.standing.pop(name, None)   # 选项数变化（版本/模组）→ 撤销该家族武装
                        changed = True
                        log(f"[R1] 武装撤销：{name} 选项数变化（现 {n}，原目标选项 {ent['opt']}）")
                        continue
                    ent["ts"] = nowt
                    continue
                dec = self._decide_arm(name, n)
                if not dec:
                    if ent:
                        self.standing.pop(name, None)
                        changed = True
                    continue
                tpl = self._tpl_of(name, ev.get("obj"))
                if not tpl:
                    continue
                self.standing[name] = {"tpl": int(tpl), "opt": int(dec[0]), "ts": nowt}
                log(f"[R1] 已武装(按名)：{name} 模板{tpl} → 选项{dec[0]}「{dec[1][:36]}」")
                changed = True
            for nm in list(self.standing):
                if nowt - self.standing[nm].get("ts", 0) > 3600:
                    self.standing.pop(nm, None)
                    changed = True
            if len(self.standing) > 20:
                ks = sorted(self.standing.items(), key=lambda kv: -kv[1].get("ts", 0))
                self.standing = dict(ks[:20])
                changed = True
            rules = [(1, e["tpl"], e["opt"]) for e in self.standing.values()]
            if changed or rules != getattr(self, "_last_rules", None):
                hr.set_slots(rules)
                self._last_rules = list(rules)
                try:
                    STANDING_FILE.write_text(json.dumps(
                        {nm: {"tpl": e["tpl"], "opt": e["opt"], "ts": e["ts"]}
                         for nm, e in self.standing.items()}, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass
                log(f"[R1] 武装表刷新：{len(rules)} 条按名规则" + ("（重建）" if not changed else ""))
            # 排空改写环形缓冲：自上次扫描起每次改写都出确认日志（不漏报、不被流冲掉）
            try:
                stt = json.loads(hr.STATE.read_text(encoding="utf-8"))
                if int(stt.get("base") or 0) == self.base and int(stt.get("ver") or 0) == hr.STATE_VER:
                    idx = struct.unpack_from("<I", ce.rpm(self.h, stt["scratch"] + 0x1CC, 4), 0)[0]
                    last = getattr(self, "_rw_idx", None)
                    if last is None:
                        last = max(0, idx - 8)   # 首次（含重启后）：回读最近 8 条，审计不断档
                    if last > idx:
                        last = idx
                    miss = idx - last
                    if miss > 8:
                        log(f"[R1] 改写缓冲跳过 {miss - 8} 条（扫描间隔内改写过多）")
                        last = idx - 8
                    if idx > last:
                        buf = ce.rpm(self.h, stt["scratch"] + 0x200, 8 * 16)
                        for j in range(last, idx):
                            k = j & 7
                            ev, pre_, post_, tpl_ = struct.unpack_from("<IIII", buf, k * 16)
                            if pre_ != post_:
                                log(f"[R1] 改写生效：id={ev} 模板{tpl_} 游戏AI原选{pre_} → 已改写为{post_}")
                            else:
                                log(f"[R1] 改写执行（AI 原选即目标 {post_}）：id={ev} 模板{tpl_}")
                    self._rw_idx = idx
            except Exception as ex:
                log(f"[R1] 改写缓冲读取异常：{ex}")
        except Exception as ex:
            log(f"[R1] 按名武装异常：{ex}")

    def _stuck_fallback(self, ev, nowt):
        """托管 ON 下事件滞留 > 90 秒仍未被 AI 应答：短暂暂停兜底注入（极端情况）。"""
        iid = ev["iid"]
        if nowt - self.evt_first_seen.setdefault(iid, nowt) < 90:
            return
        self.evt_first_seen.pop(iid, None)
        was = ce.read_pause(self.h, self.base)
        n = ev.get("n_opts") or 0
        if n == 1:
            ok = self._inject_with_pause(ev, 0)
        else:
            ok = self._ladder(ev) is not None
        if ok:
            self.seen_events.add(iid)
            log(f"[R1] 滞留兜底：{ev['name']} id={iid} 已在托管 ON 下注入处理")
            if was != 1 and AWAY_FILE.exists():
                ce.execute_command(self.h, self.base, "game_paused false")
                log("[R1] 滞留兜底：已恢复运行")

    def rule_events(self, hai):
        away = AWAY_FILE.exists()
        interval = 3 if (hai == 1 and away) else R1_EVENT_INTERVAL  # 托管 ON：3 秒快扫，抢在游戏 AI 应答前武装
        if not (hai == 1 or away) or time.time() - self.last_r1 < interval:
            return
        self.last_r1 = time.time()
        try:
            import importlib
            es = importlib.import_module("evt_select")
            pend = es.pending_events(self.h, self.base)
            if pend is None:
                return
            if away:
                self._ensure_rw88()
                self._sync_standing(pend)
            if len(self.seen_events) > 512:
                self.seen_events.clear()
            if len(self.evt_first_seen) > 512:
                self.evt_first_seen.clear()
            nowt = time.time()
            for ev in pend:
                iid = ev.get("iid")
                if not iid or iid in self.seen_events or not ev.get("gate"):
                    continue
                n = ev.get("n_opts") or 0
                if hai == 1:
                    # 托管 ON：游戏 AI 秒级应答；按名武装已在 _sync_standing 就位；滞留超时兜底
                    self._stuck_fallback(ev, nowt)
                    continue
                # ---- 托管 OFF（离开模式）：15 秒观察窗后，暂停 + 探测天梯 ----
                if nowt - self.evt_first_seen.setdefault(iid, nowt) < AWAY_GRACE_EVENT:
                    continue
                self.evt_first_seen.pop(iid, None)
                self.seen_events.add(iid)
                if n == 1:
                    if self._inject_with_pause(ev, 0):
                        self.cnt_single += 1
                        log(f"[R1] 单选项事件已自动处理：{ev['name']} id={iid}（选项0）")
                        self._away_resume_if_needed()
                    else:
                        self.cnt_fail += 1
                        log(f"[R1] 单选项事件处理失败：{ev['name']} id={iid}（60 秒后重试）")
                        self.seen_events.discard(iid)
                        self.last_r1 = time.time() + 52
                else:
                    if self._ladder(ev) is not None:
                        self.cnt_ladder += 1
                        self._away_resume_if_needed()
                    else:
                        self.cnt_fail += 1
                        self.seen_events.discard(iid)
                        self.last_r1 = time.time() + 52
        except Exception as ex:
            log(f"[R1] 事件扫描异常：{ex}")

    # ---------- 审计：跟进 game.log 的事件应答记录（含游戏 AI 的 human -1 决策） ----------
    def _save_audit(self):
        try:
            import json
            AUDIT_FILE.write_text(json.dumps({
                "off": int(self._gl_off or 0),
                "seen": list(self.audit_seen)[-400:],
            }), encoding="utf-8")
        except Exception:
            pass

    def rule_audit(self, hai):
        try:
            if not GAMELOG.exists():
                return
            size = GAMELOG.stat().st_size
            if self._gl_off is None:
                self._gl_off = size          # 只追增量，不重放历史
                self._save_audit()
                return
            if size < self._gl_off:
                self._gl_off = 0             # 文件被游戏重开/轮转
                self.audit_seen.clear()      # 新会话 id 从低位重用 → 去重键必须重置，否则开局事件漏审计
                self._save_audit()
            if size <= self._gl_off:
                return
            with open(GAMELOG, "rb") as f:
                f.seek(self._gl_off)
                chunk = f.read(65536)
            if not chunk:
                return
            nl = chunk.rfind(b"\n")
            if nl < 0:
                # 未读到完整行：若超缓冲上限则硬吞（防卡死），否则等下轮
                if len(chunk) >= 65536:
                    self._gl_off += len(chunk)
                return
            self._gl_off += nl + 1           # 只推进到最后一个完整行，行尾切断留待下轮
            text = chunk[:nl + 1].decode("utf-8", "replace")
            if len(self.audit_seen) > 1024:
                self.audit_seen.clear()
            away = AWAY_FILE.exists()
            changed = False
            for m in AUDIT_RE.finditer(text):
                ts, name, idx, human, iid = (m.group(1), m.group(2), int(m.group(3)),
                                             int(m.group(4)), int(m.group(5)))
                key = "%s|%d|%d" % (name, iid, idx)
                if key in self.audit_seen:
                    continue
                self.audit_seen.add(key)
                changed = True
                if not (hai == 1 or away):
                    continue  # 纯手动游玩时段不刷审计
                try:
                    import importlib
                    ed = importlib.import_module("evt_decide")
                    otext = ed.option_text(name, idx)
                except Exception:
                    otext = ""
                if human == -1:
                    log(f"[审计] 游戏AI自动决策：{name} id={iid} → 选项{idx}"
                        f"「{otext[:36]}」（{ts}）")
                    try:
                        import importlib
                        ea2 = importlib.import_module("evt_analyze")
                        ra = ea2.analyze(name)
                        if (ra and "error" not in ra and ra.get("conf") == "high"
                                and ra.get("suggest") != idx):
                            sug = ra["suggest"]
                            rsn = ra["options"].get(sug, {})
                            why = "；".join(rsn.get("reasons", [])[:3]) or "无计分键"
                            log(f"[参谋意见] {name}：本参谋建议选项{sug}（{why}），"
                                f"游戏选了{idx}——仅供参考（启发式）")
                    except Exception:
                        pass
                elif human == 1 and iid not in self.seen_events:
                    log(f"[审计] 事件应答（非本系统：手动/其他）：{name} id={iid} → 选项{idx}"
                        f"「{otext[:36]}」（{ts}）")
            if changed:
                self._save_audit()
        except Exception as ex:
            log(f"[审计] 异常：{ex}")

    # ---------- R2: 资源心跳 ----------
    def rule_resources(self):
        if not self.ensure():
            return
        sm = latest_save_mtime()
        new_save = bool(sm) and sm != self.save_mtime
        if new_save:
            self.save_mtime = sm
            self.res_base = None      # 新存档 → 靶值刷新，强制重扫
            time.sleep(3)             # 等自动存档写盘完成再解析
        # 未定位时高频重试（90 秒），已定位后回归 10 分钟心跳
        gap = RES_LOG_INTERVAL if self.res_base else 90
        due = time.time() - self.last_res >= gap
        if not (due or new_save):
            return
        if time.time() - self.last_attempt < 20 and not new_save:
            return
        self.last_attempt = time.time()
        try:
            import importlib
            g = importlib.import_module("game_reader")
            if self.res_base:
                vals = g.read_at(self.h, self.res_base)
                if not g.valid(vals):
                    self.res_base = None
            if not self.res_base and self.last_addr:
                # 连续性快速通道：上次的地址直接验证（跨重启/跨月份极稳）
                v = g.read_at(self.h, self.last_addr)
                if g.valid(v):
                    self.res_base = self.last_addr
            if not self.res_base:
                sv, targets = g._targets_from_save()
                self.last_sv = str(sv).rsplit("\\", 1)[-1]
                targets = targets or {}
                # 靶值可信度门槛：读到全 0 / 退化靶值（多见存档写入中的瞬间）直接跳过本轮
                try:
                    sane = (float(targets.get("energy", 0)) > 100 and
                            (float(targets.get("energy", 0)) + float(targets.get("minerals", 0))) > 100)
                except Exception:
                    sane = False
                if not sane:
                    log("[R2] 存档靶值不可信（疑似写入中/退化），跳过本轮")
                    self.last_res = time.time()
                    return
                prefer = self.last_addr
                self.res_base = g.find_by_scan(self.h, targets)
                if not self.res_base:
                    self.res_base = g.find_by_scan_fuzzy(self.h, targets, prefer=prefer)
                    if self.res_base:
                        log("[R2] 精确扫描未中，容差扫描（±12%）定位成功")
                if self.res_base:
                    self.last_addr = self.res_base
                if not self.res_base and self.last_vals:
                    self.res_base = g.find_by_scan_fuzzy(self.h, self.last_vals, rtol=0.35,
                                                         prefer=self.last_addr)
                    if self.res_base:
                        log("[R2] 存档靶值失配（AI 运行中漂移），以上次实读值恢复定位")
            vals = g.read_at(self.h, self.res_base) if self.res_base else None
            if vals and not g.valid(vals):
                log("[R2] 读数校验不过（疑似误配块），丢弃地址并等待重试")
                self.res_base = None
                vals = None
            if vals:
                self.last_vals = vals
                self.last_addr = self.res_base
                try:
                    import json
                    RES_FILE.write_text(json.dumps({
                        "base": self.res_base, "vals": vals, "ts": time.time(),
                    }), encoding="utf-8")
                except Exception:
                    pass
                tags = []
                e = vals.get("energy")
                mins = vals.get("minerals")
                if e is not None and abs(e - 25000) < 1:
                    tags.append("能量疑似顶上限25000")
                if mins is not None and abs(mins - 25000) < 1:
                    tags.append("矿物疑似顶上限25000")
                infl = vals.get("influence")
                if infl is not None and abs(infl - 1000) < 1:
                    tags.append("影响力顶上限1000")
                head = " ".join(f"{k}={v:.0f}" for k, v in list(vals.items())[:8])
                log(f"[R2] 资源（对标 {self.last_sv or '缓存'}）：{head}"
                    + ("  ⚠ " + "；".join(tags) if tags else ""))
            else:
                log("[R2] 资源块未定位（游戏进度与最近存档不一致），等待下次心跳重试")
            self.last_res = time.time()
        except Exception as ex:
            log(f"[R2] 资源读取异常：{ex}")
            self.last_res = time.time()

    # ---------- R5/R6: 任务与军力态势（独立 10 分钟节奏） ----------
    def rule_tasks(self):
        if time.time() - self.last_r5 < RES_LOG_INTERVAL:
            return
        if not self.ensure():
            return
        try:
            import importlib
            sr = importlib.import_module("situation_reader")
            _sv, gs2 = sr.load()
            d = sr.digest(gs2)
            log("[R5] 任务摘要：" + sr.digest_line(gs2))
            # R9 战争守护：我方战争数变化即报警（新战争 / 战争结束/被附庸）
            ow = int(d.get("own_wars") or 0)
            if self.prev_own_wars is None:
                self.prev_own_wars = ow
            elif ow != self.prev_own_wars:
                if ow > self.prev_own_wars:
                    log(f"[R9] ⚠ 战争警报：我方战争 {self.prev_own_wars} → {ow}（新战争爆发！"
                        f"挂机中由托管 AI 应战；亡国级目标请尽快回来看）")
                else:
                    log(f"[R9] 战争状态：我方战争 {self.prev_own_wars} → {ow}（战争结束——"
                        f"变附属国/割地等条款请检查外交状态）")
                self.prev_own_wars = ow
            mp = d.get("military_power")
            if mp:
                if self.prev_mil and mp < self.prev_mil * 0.8:
                    log(f"⚠ [R6] 军力明显下降：{self.prev_mil:.0f} → {mp:.0f}（可能战损，留意战争）")
                self.prev_mil = mp
                try:
                    import json
                    STATE_FILE.write_text(json.dumps({
                        "prev_mil": self.prev_mil, "last_techs": self.last_techs,
                        "last_fleet": self.last_fleet, "fleet_streak": self.fleet_streak,
                    }), encoding="utf-8")
                except Exception:
                    pass
            # ---- 建议栏：识别可行动状态（有变化才输出，避免刷屏） ----
            advs = []
            if d.get("own_wars"):
                advs.append(f"⚠ 你正卷入 {d['own_wars']} 处战争，留意前线与外交")
            elif d.get("wars"):
                advs.append(f"银河存在战争（{d['wars']} 处），我方暂未参战")
            if d.get("situations"):
                advs.append(f"有 {d['situations']} 个进行中的特殊情况待处理")
            if d.get("projects"):
                advs.append("未完成特殊项目：" + "、".join(str(x) for x in d["projects"][:3]))
            if d.get("starbase_cap") and d.get("starbase_used") >= d.get("starbase_cap"):
                advs.append(f"星基容量已满（{d['starbase_used']:.0f}/{d['starbase_cap']:.0f}），扩张受限")
            techs_now = d.get("techs", 0)
            try:
                paused_now = ce.read_pause(self.h, self.base)
            except Exception:
                paused_now = None
            if (self.last_techs and techs_now and techs_now <= self.last_techs
                    and paused_now == 0):
                advs.append(f"科研疑似停滞（科技数 {techs_now} 未增长），检查研究队列")
            if techs_now:
                self.last_techs = techs_now
            fleet_now = d.get("fleet_size", 0)
            if self.last_fleet and fleet_now and fleet_now < self.last_fleet * 0.98:
                self.fleet_streak += 1
            elif not fleet_now or fleet_now >= (self.last_fleet or 0):
                self.fleet_streak = 0
            if self.fleet_streak >= 2 and paused_now == 0:
                advs.append(f"舰队持续减员（{self.last_fleet:.0f} → {fleet_now:.0f}），检查战损与造船队列")
            if fleet_now:
                self.last_fleet = fleet_now
            if self.last_vals:
                for res, cap in (("energy", 25000), ("minerals", 25000), ("food", 25000), ("influence", 1000)):
                    v = self.last_vals.get(res)
                    if v is not None and v >= cap - 1:
                        advs.append(f"{res} 顶在上限 {cap}，多余收入正在被浪费")
                low_energy = 8000 if d.get("wars") else 5000   # 战时能量警戒线提高（策略库 B3）
                for res, low in (("energy", low_energy), ("minerals", 1500), ("food", 2000)):
                    v = self.last_vals.get(res)
                    if v is not None and v < low:
                        advs.append(f"{res} 储备偏低（{v:.0f} < {low}），留意战争消耗")
            key = "|".join(advs)
            if advs and key != self.prev_advs:
                log("[建议] " + "；".join(advs))
            self.prev_advs = key
            try:
                import json
                STATE_FILE.write_text(json.dumps({
                    "prev_mil": self.prev_mil, "last_techs": self.last_techs,
                    "last_fleet": self.last_fleet, "fleet_streak": self.fleet_streak,
                }), encoding="utf-8")
            except Exception:
                pass
            self.last_r5 = time.time()
        except Exception as ex:
            log(f"[R5] 任务摘要失败：{ex}")
            self.last_r5 = time.time()

    # ---------- R3: 状态变迁 ----------
    def rule_transitions(self, hai, paused):
        if self.prev_hai is not None and hai != self.prev_hai:
            log(f"[R3] 托管开关：{'开' if self.prev_hai == 1 else '关'} → {'开' if hai == 1 else '关'}")
        if self.prev_pause is not None and paused != self.prev_pause:
            log(f"[R3] 暂停状态：{'暂停' if self.prev_pause == 1 else '运行'} → {'暂停' if paused == 1 else '运行'}")
        self.prev_hai = hai
        self.prev_pause = paused

    # ---------- R4: 离开模式（暂停自动恢复） ----------
    def rule_away(self, hai, paused):
        away = AWAY_FILE.exists()
        if self.away_prev is None or away != self.away_prev:
            log(f"[R4] 离开模式：{'开启' if away else '关闭'}")
            self.away_prev = away
        if not away:
            self.away_since = None
            self.away2_since = None
            return
        if hai == 1:
            # 托管 ON：暂停超 AWAY_GRACE 且无事件拦路 → 恢复
            if paused == 1:
                if self.away_since is None:
                    self.away_since = time.time()
                elif time.time() - self.away_since >= AWAY_GRACE:
                    r = ce.execute_command(self.h, self.base, "game_paused false")
                    log(f"[R4] 离开模式：游戏已暂停超过 {AWAY_GRACE} 秒且无事件拦路，已自动继续运行"
                        f"（ok={r.get('ok')}）")
                    self.away_since = None
            else:
                self.away_since = None
            self.away2_since = None
            return
        # 托管 OFF：空闲暂停（无我方动作）超阈值 → 恢复运行，让时间持续流动；
        # 有我方待决事件时交给 R1 处理（其流程自行恢复）；事件滞留超 120 秒也强制恢复（不冻结）
        if paused == 1:
            if self.away2_since is None:
                self.away2_since = time.time()
            held = time.time() - self.away2_since
            if held >= AWAY_RESUME_OFF:
                pend = None
                try:
                    import importlib
                    es = importlib.import_module("evt_select")
                    pend = es.pending_events(self.h, self.base)
                except Exception:
                    pend = []
                if not pend or held >= 120:
                    r = ce.execute_command(self.h, self.base, "game_paused false")
                    log(f"[R4] 离开模式(托管OFF)：暂停 {int(held)} 秒"
                        f"{'（无待决事件）' if not pend else '（事件滞留兜底）'}，"
                        f"已自动继续运行（ok={r.get('ok')}）")
                    self.away2_since = None
        else:
            self.away2_since = None

    # ---------- R8: 离开模式窗口清理（外交收件类弹窗自动关闭） ----------
    def rule_windows(self):
        """离开模式下，周期性关闭"提醒/通知型"外交收件窗口（如宣战窗），
        避免挂机时无人确认的弹窗长期滞留屏幕。
        通道：游戏官方控制台命令 window close <gui name>（no-op 安全，多次实测无副作用）。"""
        if time.time() - self.last_win_clean < WIN_CLEAN_INTERVAL:
            return
        self.last_win_clean = time.time()
        if not AWAY_FILE.exists():
            return
        if not self._win_enabled_logged:
            self._win_enabled_logged = True
            log("[R8] 离开模式：外交窗口自动清理已启用（目标：宣战/和平收件窗）")
        for name in WIN_TARGETS:
            try:
                r = ce.execute_command(self.h, self.base, f"window close {name}")
                if r.get("ok"):
                    log(f"[R8] 已自动关闭窗口「{name}」")
            except Exception as ex:
                log(f"[R8] 窗口清理异常：{ex}")

    def run(self):
        log("=== 决策大脑 v1.3 启动（观察 + 探测天梯 + 按名武装改写[24槽/归属校验] + 决策日志） ===")
        while True:
            try:
                if not self.ensure():
                    if self.was_connected:
                        log("[R7] 检测到游戏进程消失（退出或崩溃）——等待重新开启")
                        self.was_connected = False
                    time.sleep(4)
                    continue
                self.was_connected = True
                hai = ce.read_flag(self.h, self.base, ce.RVA_HUMAN_AI)
                paused = ce.read_pause(self.h, self.base)
                if hai is None or paused is None:
                    self.drop()
                    time.sleep(4)
                    continue
                self.rule_transitions(hai, paused)
                self.rule_events(hai)
                self.rule_audit(hai)
                self.rule_away(hai, paused)
                self.rule_windows()
                self.rule_resources()
                self.rule_tasks()
                self.rule_health(hai)
            except Exception as ex:
                log(f"[ERR] 主循环异常：{ex}")
            time.sleep(2)


def main():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    mtx = k32.CreateMutexW(None, False, "CodexStellarisBrainMutex")
    if not mtx:
        return
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS → 已有实例在跑
        return
    Brain().run()


if __name__ == "__main__":
    main()
