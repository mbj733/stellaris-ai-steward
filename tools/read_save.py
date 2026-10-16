# -*- coding: utf-8 -*-
"""读 Stellaris 存档（引擎数据快照）并打印玩家帝国概况。

存档 = zip( meta + gamestate )，gamestate 是 Paradox 脚本格式的完整游戏状态。
本工具只读文件，不碰游戏进程、不改任何东西 —— 「内核级读取」的零风险通道。
"""
import glob
import os
import re
import sys
import time
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
sys.setrecursionlimit(200000)

SAVES = os.path.join(os.path.expanduser("~"), "Documents",
                 "Paradox Interactive", "Stellaris", "save games")

_TOK = re.compile(r'[^\s{}=#"]+')


def latest_save():
    files = glob.glob(os.path.join(SAVES, "**", "*.sav"), recursive=True)
    files.sort(key=os.path.getmtime)
    return files[-1] if files else None


def decode(data):
    for enc in ("utf-8-sig", "gb18030", "cp1252"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8/replace"


def _add(obj, key, val):
    if key not in obj:
        obj[key] = val
    else:
        old = obj[key]
        if isinstance(old, list):
            old.append(val)
        else:
            obj[key] = [old, val]


class Parser:
    """宽容版 Clausewitz 脚本解析器（key=value / 块 / 数组 / 重复键）。"""

    def __init__(self, text):
        self.t = text
        self.i = 0
        self.n = len(text)

    def top(self):
        """顶层：连续的 key = value 直到文件结束。"""
        obj = {}
        while True:
            self.skip()
            if self.i >= self.n:
                break
            m = _TOK.match(self.t, self.i)
            if not m:
                self.i += 1
                continue
            key = m.group(0)
            self.i += len(key)
            self.skip()
            if self.i < self.n and self.t[self.i] == "=":
                self.i += 1
                _add(obj, key, self.value())
            else:
                self.i += 1
        return obj

    def skip(self):
        t, n = self.t, self.n
        while self.i < n:
            c = t[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif c == "#":
                j = t.find("\n", self.i)
                self.i = n if j < 0 else j + 1
            else:
                break

    def value(self):
        self.skip()
        c = self.t[self.i]
        if c == "{":
            return self.block()
        if c == '"':
            j = self.t.find('"', self.i + 1)
            s = self.t[self.i + 1:j]
            self.i = j + 1
            return s
        m = _TOK.match(self.t, self.i)
        tok = m.group(0)
        self.i += len(tok)
        return tok

    def block(self):
        assert self.t[self.i] == "{"
        self.i += 1
        obj = {}
        arr = []
        while True:
            self.skip()
            if self.i >= self.n:
                break
            if self.t[self.i] == "}":
                self.i += 1
                break
            if self.t[self.i] == '"':
                j = self.t.find('"', self.i + 1)
                key = self.t[self.i + 1:j]
                self.i = j + 1
                self.skip()
                if self.i < self.n and self.t[self.i] == "=":
                    self.i += 1
                    _add(obj, key, self.value())
                    continue
                arr.append(key)
                continue
            m = _TOK.match(self.t, self.i)
            if m:
                tok = m.group(0)
                k = self.i + len(tok)
                while k < self.n and self.t[k] in " \t":
                    k += 1
                if k < self.n and self.t[k] == "=":
                    self.i = k + 1
                    _add(obj, tok, self.value())
                    continue
            arr.append(self.value())
        if obj and not arr:
            return obj
        if arr and not obj:
            return arr
        if obj and arr:
            obj["__items__"] = arr
        return obj


def main():
    sv = latest_save()
    if not sv:
        print("没有找到存档")
        return
    print("存档:", sv)
    with zipfile.ZipFile(sv) as z:
        names = z.namelist()
        meta_txt, enc1 = decode(z.read("meta"))
        gs_txt, enc2 = decode(z.read("gamestate"))
    print(f"zip 内容: {names}  编码: meta={enc1} gamestate={enc2}")
    print(f"gamestate 文本 {len(gs_txt)/1e6:.1f} MB")
    m_f = re.search(r"meta_fleets=(\d+)", meta_txt)
    m_p = re.search(r"meta_planets=(\d+)", meta_txt)
    print(f"meta 交叉验证值：fleets={m_f.group(1) if m_f else '?'}  planets={m_p.group(1) if m_p else '?'}")

    t0 = time.time()
    root = Parser(gs_txt).top()
    dt = time.time() - t0
    gs = root.get("gamestate", root) if isinstance(root, dict) else {}
    print(f"解析完成（{dt:.1f}s）")
    if not gs:
        print("解析结果为空，文件开头 300 字符：", repr(gs_txt[:300]))

    top = list(gs.keys())
    print(f"顶层段（{len(top)}）:", ", ".join(top[:40]))
    print("日期:", gs.get("date"))

    player = gs.get("player")
    pcid = None
    if isinstance(player, dict):
        pcid = player.get("country")
    elif isinstance(player, list) and player and isinstance(player[0], dict):
        pcid = player[0].get("country")
    print("player 段:", str(player)[:300])
    print("玩家国家 id:", pcid)

    countries = gs.get("country") or {}
    if isinstance(countries, dict):
        print("国家总数:", len(countries))
        c = None
        for k in (str(pcid), pcid, "0"):
            if k in countries:
                c = countries[k]
                break
        if isinstance(c, dict):
            print("帝国名:", c.get("name"))
            print("国家块字段数:", len(c), "| 字段样例:", ", ".join(sorted(str(k) for k in c.keys())[:70]))
            techish = [str(k) for k in c if "tech" in str(k).lower() or "research" in str(k).lower()]
            print("疑似科技/研究字段:", techish[:20])
            ts = c.get("tech_status") or c.get("technology")
            if isinstance(ts, dict):
                techs = [k for k in ts if str(k).startswith("tech_")]
                print("科技条目数:", len(techs), "样例:", techs[:8])
            for key in ("resources", "budget", "authority", "civics", "ethos", "flags"):
                if key in c:
                    print(f"{key}:", str(c[key])[:260])
        else:
            print("没找到玩家国家块；国家键样例:", list(countries.keys())[:10])

    for sect in ("fleet", "planet", "pop", "ship"):
        v = gs.get(sect)
        if isinstance(v, dict):
            owned = 0
            for _, blk in v.items():
                s = str(blk)
                if pcid is not None and re.search(rf"\b(owner|controller|country)\s*=\s*{re.escape(str(pcid))}\b", s):
                    owned += 1
            print(f"{sect} 段: 共 {len(v)} 个，玩家持有约 {owned} 个")


if __name__ == "__main__":
    main()
