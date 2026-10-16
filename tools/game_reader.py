# -*- coding: utf-8 -*-
"""实时读取游戏资源状态（内核数据直读，不截图）。

用法：
  python game_reader.py          打印当前资源（优先用缓存地址，失效则自动重找）
  python game_reader.py --find   强制用"最新存档靶值 + 内存扫描"重新定位
"""
import argparse
import json
import re
import struct
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

import memread as mr

CACHE = Path(__file__).resolve().parent / "_res_addr.json"
NAMES = ["energy", "minerals", "food", "physics_research", "society_research",
         "engineering_research", "influence", "unity", "trade", "consumer_goods", "alloys"]
ART_OFF = 0x90
SCALE = 100000.0


def read_at(h, base):
    data = mr.read_mem(h, base, len(NAMES) * 8)
    if not data or len(data) < len(NAMES) * 8:
        return None
    vals = {}
    for i, n in enumerate(NAMES):
        vals[n] = struct.unpack_from("<q", data, i * 8)[0] / SCALE
    art = mr.read_mem(h, base + ART_OFF, 8)
    if art and len(art) == 8:
        vals["minor_artifacts"] = struct.unpack_from("<q", art, 0)[0] / SCALE
    return vals


def valid(vals):
    if not vals or len(vals) < len(NAMES):
        return False
    good = 0
    nonzero = 0
    for n in NAMES:
        v = vals.get(n)
        if v is None or not (0 <= v <= 2e6):
            return False
        if v <= 1e7:
            good += 1
        if v > 0:
            nonzero += 1
    if vals["energy"] == 0 and vals["minerals"] == 0:
        return False
    # 真实经济至少 6 个资源槽非零；垃圾/零块一律拒绝
    return good >= 9 and nonzero >= 6


def _iter_regions(h):
    for base, rsize, prot in mr.regions(h, writable_only=True):
        data = mr.read_mem(h, base, rsize)
        if data:
            yield base, data


def _targets_from_save():
    """从最新存档提取玩家资源块的精确值。"""
    import read_save as rs
    sv = rs.latest_save()
    with zipfile.ZipFile(sv) as z:
        txt, _ = rs.decode(z.read("gamestate"))
    # 首选：玩家国家模块里的库存（country.<player>.modules.standard_economy_module.resources）
    try:
        root = rs.Parser(txt).top()
        gs = root.get("gamestate", root)
        pl = gs.get("player")
        pcid = None
        if isinstance(pl, dict):
            pcid = pl.get("country")
        elif isinstance(pl, list) and pl and isinstance(pl[0], dict):
            pcid = pl[0].get("country")
        c = gs.get("country", {}).get(str(pcid))
        res = c["modules"]["standard_economy_module"]["resources"]
        kv = {}
        for k, v in res.items():
            try:
                kv[k] = float(v)
            except Exception:
                pass
        if kv.get("energy", 0) > 0 and "trade" in kv:
            return sv, kv
    except Exception as e:
        print("玩家库存解析失败，回退旧法:", e)
    # 兜底：旧启发式（可能抓到别的国家/对象，仅供救急）
    best = None
    for m in re.finditer(r"resources\s*=\s*\{", txt):
        j = txt.index("{", m.start())
        depth, k = 0, j
        while k < len(txt):
            c = txt[k]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        block = txt[j + 1:k]
        kv = dict((a, float(b)) for a, b in re.findall(r"(\w+)\s*=\s*([-\d.]+)", block))
        if "trade" in kv and kv.get("energy", 0) > 1000:
            if best is None or kv["energy"] > best["energy"]:
                best = kv
    return sv, best


def find_by_scan(h, targets):
    """在内存里找 8 字节步进的资源数组（≥6 个连续槽命中已知靶值）。"""
    tvals = {round(v * SCALE): name for name, v in targets.items() if name in NAMES}
    if len(tvals) < 6:
        return None
    found = []
    for base, data in _iter_regions(h):
        n = len(data) // 8
        if n < 20:
            continue
        arr = np.frombuffer(data[:n * 8], dtype=np.int64)
        for tv in tvals:
            for idx in np.where(arr == tv)[0][:200]:
                found.append((base + int(idx) * 8, tv))
    # 找 8 字节步进的连续命中
    addrs = sorted(a for a, _ in found)
    hitset = {}
    for a, tv in found:
        hitset.setdefault(a, tv)
    best = None
    for a in addrs:
        cnt = 0
        for i in range(11):
            if a + i * 8 in hitset:
                cnt += 1
        if best is None or cnt > best[1]:
            best = (a, cnt)
    if best and best[1] >= 6:
        return best[0]
    return None


def find_by_scan_fuzzy(h, targets, rtol=0.12, prefer=None):
    """容差版扫描：以 energy 为锚点，11 槽中 ≥8 槽落在 ±rtol（下限 ±0.5 单位）内即命中。
    用于游戏高速运行时（存档靶值与实时值存在少量月度漂移）的兜底定位。
    prefer：上次已知地址——多候选时选离它最近的（同一堆块地址极稳定，抗"误配到别国"）。"""
    tvals = []
    for n in NAMES:
        try:
            tvals.append(round(float(targets.get(n, 0)) * SCALE))
        except Exception:
            tvals.append(0)
    if sum(1 for t in tvals if t) < 6:
        return None
    anchor = tvals[0]
    if not anchor:
        return None
    tols = [max(50000, int(abs(t) * rtol)) for t in tvals]
    cands = []
    for base, data in _iter_regions(h):
        n = len(data) // 8
        if n < 20:
            continue
        arr = np.frombuffer(data[: n * 8], dtype=np.int64)
        idxs = np.where(np.abs(arr - anchor) <= tols[0])[0]
        if len(idxs) == 0 or len(idxs) > 5000:
            continue
        for idx in idxs[:2000]:
            if idx + 11 > n:
                continue
            ok = 0
            for k in range(11):
                t = tvals[k]
                if t == 0:
                    continue
                if abs(int(arr[idx + k]) - t) <= tols[k]:
                    ok += 1
            if ok >= 8:
                cands.append(base + int(idx) * 8)
                if len(cands) >= 50:
                    break
        if len(cands) >= 50:
            break
    if not cands:
        return None
    if prefer:
        return min(cands, key=lambda a: abs(a - prefer))
    return cands[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proc", nargs="?", default="stellaris")
    ap.add_argument("--find", action="store_true")
    a = ap.parse_args()
    h, pid = mr.open_proc(a.proc)
    vals = None
    base = None
    if not a.find and CACHE.exists():
        try:
            c = json.loads(CACHE.read_text(encoding="utf-8"))
            base = c.get("base")
            vals = read_at(h, base) if base else None
            if not valid(vals):
                print("缓存地址失效，重新定位...")
                vals = None
        except Exception:
            vals = None
    if vals is None:
        sv, targets = _targets_from_save()
        print("存档靶值来自:", sv)
        if not targets:
            print("存档里没解析到资源块，无法定位")
            return
        t0 = time.time()
        base = find_by_scan(h, targets)
        print(f"内存扫描完成（{time.time()-t0:.1f}s）")
        if base is None:
            print("没找到资源数组：游戏状态可能和存档不一致（请保存后重试）")
            return
        vals = read_at(h, base)
        if not valid(vals):
            print("找到的地址校验不通过")
            return
        CACHE.write_text(json.dumps({"base": base, "ts": time.time()}), encoding="utf-8")
    print(f"资源地址: 0x{base:X}")
    print("-" * 34)
    for n in NAMES + ["minor_artifacts"]:
        if n in vals:
            print(f"{n:>20}: {vals[n]:>15.5f}")


if __name__ == "__main__":
    main()
