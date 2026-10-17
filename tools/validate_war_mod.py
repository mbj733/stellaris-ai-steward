# -*- coding: utf-8 -*-
"""Static validation of the installed ai_steward_war mod (no game needed).

Checks: required files, balanced braces, unique event ids, on_action references,
localisation BOM, descriptor fields. Read-only.
"""
import re
import sys
from pathlib import Path

if sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8")

DOC = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris"
MOD = DOC / "mod" / "ai_steward_war"
ENTRY = DOC / "mod" / "ai_steward_war.mod"


def validate():
    problems = []
    required = [
        ENTRY,
        MOD / "descriptor.mod",
        MOD / "common" / "on_actions" / "zz_ai_steward_war.txt",
        MOD / "events" / "ai_steward_war_events.txt",
        MOD / "localisation" / "simp_chinese" / "ai_steward_war_l_simp_chinese.yml",
        MOD / "localisation" / "english" / "ai_steward_war_l_english.yml",
    ]
    for p in required:
        if not p.exists():
            problems.append("missing: %s" % p)
    if problems:
        return problems

    desc = ENTRY.read_text(encoding="utf-8", errors="replace")
    if "supported_version" not in desc:
        problems.append("descriptor: no supported_version")
    if "path=" not in desc:
        problems.append("descriptor: no path=")

    on = (MOD / "common" / "on_actions" / "zz_ai_steward_war.txt").read_text(
        encoding="utf-8", errors="replace")
    ev = (MOD / "events" / "ai_steward_war_events.txt").read_text(
        encoding="utf-8", errors="replace")
    for name, text in (("on_actions", on), ("events", ev)):
        if text.count("{") != text.count("}"):
            problems.append("%s: braces %d/%d" % (name, text.count("{"), text.count("}")))
    if "on_monthly_pulse_country" not in on:
        problems.append("on_actions: on_monthly_pulse_country missing")

    ids = re.findall(r"\bid\s*=\s*(ai_steward_war\.\d+)", ev)
    if len(ids) != len(set(ids)):
        problems.append("events: duplicate ids %s" % ids)
    for ref in re.findall(r"\b(ai_steward_war\.\d+)", on):
        if ref not in ids:
            problems.append("on_actions references missing event %s" % ref)
    for must in ("ai_steward_war.1", "ai_steward_war.2",
                 "ai_steward_war.10", "ai_steward_war.11"):
        if must not in ids:
            problems.append("events: missing %s" % must)

    for p in required[-2:]:
        raw = p.read_bytes()
        if not raw.startswith(b"\xef\xbb\xbf"):
            problems.append("loc missing UTF-8 BOM: %s" % p.name)
    return problems


def main():
    problems = validate()
    if problems:
        print("[FAIL] war mod static validation")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)
    print("[PASS] war mod static validation (files/braces/events/loc)")


if __name__ == "__main__":
    main()
