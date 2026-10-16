# -*- coding: utf-8 -*-
"""解析游戏 events/*.txt → data/event_index.json + data/event_title_index.json。

用途：让决策引擎知道「弹这个窗的事件是哪个、每个选项会造成什么」。
运行前不需要游戏开着；只读游戏安装目录 + 知识库 loc_zh.json。
"""
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

GAME = Path(r"<改成你的游戏安装路径>")
KB = Path(r"<可选：你缓存的游戏数据目录>")   # 生成器第二数据源，可留空不用
OUT = Path(str(Path(__file__).resolve().parent.parent / "data"))

SKIP_KEYS = {
    "trigger", "name", "text", "option", "immediate", "is_triggered_only", "hide_window",
    "random_list", "if", "else_if", "else", "limit", "weight", "modifier", "description",
    "resource", "amount", "icon", "sound", "id", "title", "desc", "picture", "fires",
    "days", "months", "years", "scale", "portrait", "triggered_desc", "show_sound",
}


def strip_quotes(s):
    s = (s or "").strip()
    while s[:1] == '"' and s[-1:] == '"' and len(s) >= 2:
        s = s[1:-1]
    return s.strip()


def find_block(text, start):
    """text[start-1] 应为 '{'。返回 (block_text, end_index)。"""
    depth = 1
    i = start
    n = len(text)
    in_str = False
    while i < n and depth:
        ch = text[i]
        if in_str:
            if ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "#":
                j = text.find("\n", i)
                i = j if j != -1 else n
                continue
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        i += 1
    return text[start:i - 1], i


def value_after(block, key, window=None):
    seg = block if window is None else block[:window]
    m = re.search(rf"(?<![\w.]){key}\s*=\s*", seg)
    if not m:
        return None
    rest = seg[m.end():]
    rs = rest.lstrip()
    if rs.startswith("{"):
        j = seg.index("{", m.end())
        inner, _ = find_block(seg, j + 1)
        m2 = re.search(r"(?<![\w.])text\s*=\s*([\w.:\"]+)", inner)
        return strip_quotes(m2.group(1)) if m2 else None
    m2 = re.match(r"([\w.:\"]+)", rs)
    return strip_quotes(m2.group(1)) if m2 else None


def parse_file(p):
    text = p.read_text(encoding="utf-8", errors="replace")
    events = []
    for m in re.finditer(r"\b(\w+_event)\s*=\s*\{", text):
        typ = m.group(1)
        block, _ = find_block(text, m.end())
        eid = value_after(block, "id")
        if not eid:
            continue
        cut = len(block)
        for kw in ("immediate", "option", "trigger"):
            j = block.find(kw)
            if j != -1:
                cut = min(cut, j)
        title = value_after(block, "title", window=min(cut, 1200))
        desc = value_after(block, "desc", window=min(cut, 1200))
        hide = bool(re.search(r"hide_window\s*=\s*yes", block))
        opts = []
        for om in re.finditer(r"\boption\s*=\s*\{", block):
            ob, _ = find_block(block, om.end())
            name = value_after(ob, "name")
            effects = sorted(set(
                e for e in re.findall(r"([a-z_][a-z0-9_]{3,})\s*=", ob)
                if e not in SKIP_KEYS and not e.startswith("has_")
            ))
            opts.append({"name": name, "effects": effects[:24]})
        events.append({"id": eid, "type": typ, "hide": hide,
                       "title": title, "desc": desc, "options": opts})
    return events


def clean_zh(s):
    if not s:
        return s
    s = re.sub(r"§.", "", s)
    s = re.sub(r"\$[^$]*\$", "", s)
    s = re.sub(r"£[a-z_]+£", "", s)
    s = s.replace("\\n", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip()


def main():
    t0 = time.time()
    events_dir = GAME / "events"
    files = sorted(events_dir.glob("*.txt"))
    print(f"event 文件数：{len(files)}")
    loc = json.loads((KB / "loc_zh.json").read_text(encoding="utf-8"))

    def zh_of(key):
        if not key:
            return None
        for k in (key, key + ":0", key + ":1"):
            if k in loc:
                return clean_zh(loc[k])
        return None

    all_events = {}
    for p in files:
        try:
            for ev in parse_file(p):
                ev["file"] = p.name
                ev["title_zh"] = zh_of(ev.get("title"))
                ev["desc_zh"] = zh_of(ev.get("desc"))
                for opt in ev.get("options", []):
                    opt["name_zh"] = zh_of(opt.get("name"))
                all_events[ev["id"]] = ev
        except Exception as e:
            print("解析失败:", p.name, repr(e))
    print(f"事件总数：{len(all_events)}")

    title_index = {}
    for eid, ev in all_events.items():
        if ev["hide"]:
            continue
        t = ev.get("title_zh")
        if t and len(t) >= 2:
            title_index.setdefault(t, [])
            if len(title_index[t]) < 20:
                title_index[t].append(eid)
    print(f"可匹配标题数：{len(title_index)}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "event_index.json").write_text(
        json.dumps({"events": all_events}, ensure_ascii=False), encoding="utf-8")
    (OUT / "event_title_index.json").write_text(
        json.dumps(title_index, ensure_ascii=False), encoding="utf-8")
    print("输出:", OUT / "event_index.json", (OUT / "event_index.json").stat().st_size // 1024, "KB")
    print("输出:", OUT / "event_title_index.json", (OUT / "event_title_index.json").stat().st_size // 1024, "KB")
    print(f"耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
