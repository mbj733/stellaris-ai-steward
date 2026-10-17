# -*- coding: utf-8 -*-
"""安装/卸载「AI 托管·战争组件」本地 mod：
战时每月：军用舰队转 aggressive、同星系自动追击敌舰队、空闲舰队增援最近威胁；
可选「进攻模式」（ai_steward_war.10 开启 / .11 关闭）让空闲舰队推进最近敌国星系。
用法: python tools/install_war_mod.py install|remove
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DOC = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris"
MODDIR = DOC / "mod"
MOD = MODDIR / "ai_steward_war"
ENTRY = "mod/ai_steward_war.mod"

DESC = (
    'name="AI Steward: War Component"\n'
    'version="0.3.0"\n'
    "tags={\n"
    '\t"Gameplay"\n'
    "}\n"
    'supported_version="4.5.*"\n'
    'path="' + MOD.as_posix() + '"\n'
)

ON_ACTIONS = """on_monthly_pulse_country = {
\tevents = { ai_steward_war.1 ai_steward_war.2 }
}
"""

EVENT = """namespace = ai_steward_war

# 月度：战时全部军用舰队转 aggressive；和平期清掉进攻模式开关
country_event = {
\tid = ai_steward_war.1
\thide_window = yes
\tis_triggered_only = yes

\ttrigger = {
\t\tis_ai = no
\t}

\timmediate = {
\t\tif = {
\t\t\tlimit = { is_at_war = yes }
\t\t\tevery_owned_fleet = {
\t\t\t\tlimit = {
\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t}
\t\t\t\tset_fleet_stance = aggressive
\t\t\t}
\t\t}
\t\telse = {
\t\t\tremove_country_flag = ai_steward_war_offensive
\t\t}
\t}
}

# 月度：同星系自动追击敌舰队；空闲舰队增援最近威胁（或进攻模式下推进最近敌国）
country_event = {
\tid = ai_steward_war.2
\thide_window = yes
\tis_triggered_only = yes

\ttrigger = {
\t\tis_ai = no
\t\tis_at_war = yes
\t}

\timmediate = {
\t\t# 1) 已与敌舰队同星系：直接自动追击并攻击
\t\tevery_owned_fleet = {
\t\t\tlimit = {
\t\t\t\tis_ship_class = shipclass_military
\t\t\t\tNOT = { is_in_combat = yes }
\t\t\t}
\t\t\tif = {
\t\t\t\tlimit = {
\t\t\t\t\tsolar_system = {
\t\t\t\t\t\tany_fleet_in_system = {
\t\t\t\t\t\t\towner = { is_hostile = root }
\t\t\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tsolar_system = {
\t\t\t\t\trandom_fleet_in_system = {
\t\t\t\t\t\tlimit = {
\t\t\t\t\t\t\towner = { is_hostile = root }
\t\t\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t\t\t}
\t\t\t\t\t\tsave_event_target_as = ai_steward_enemy_fleet
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tauto_follow_fleet = {
\t\t\t\t\ttarget = event_target:ai_steward_enemy_fleet
\t\t\t\t\tattack_fleet = yes
\t\t\t\t}
\t\t\t}
\t\t}

\t\t# 2) 空闲舰队：进攻模式→最近敌国星系；否则→最近的本土受威胁星系
\t\tif = {
\t\t\tlimit = { has_country_flag = ai_steward_war_offensive }
\t\t\tevery_owned_fleet = {
\t\t\t\tlimit = {
\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t\tis_fleet_idle = yes
\t\t\t\t}
\t\t\t\tclosest_system = {
\t\t\t\t\tlimit = {
\t\t\t\t\t\towner = { is_hostile = root }
\t\t\t\t\t}
\t\t\t\t\tsave_event_target_as = ai_steward_target_system
\t\t\t\t\tprev = {
\t\t\t\t\t\tqueue_actions = {
\t\t\t\t\t\t\tmove_to = event_target:ai_steward_target_system
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t\telse = {
\t\t\tevery_owned_fleet = {
\t\t\t\tlimit = {
\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t\tis_fleet_idle = yes
\t\t\t\t}
\t\t\t\tclosest_system = {
\t\t\t\t\tlimit = {
\t\t\t\t\t\towner = { is_same_value = root }
\t\t\t\t\t\tany_fleet_in_system = {
\t\t\t\t\t\t\towner = { is_hostile = root }
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t\tsave_event_target_as = ai_steward_target_system
\t\t\t\t\tprev = {
\t\t\t\t\t\tqueue_actions = {
\t\t\t\t\t\t\tmove_to = event_target:ai_steward_target_system
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
}

# 开启进攻模式（空闲舰队主动推进最近敌国星系）
country_event = {
\tid = ai_steward_war.10
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tset_country_flag = ai_steward_war_offensive
\t}
}

# 关闭进攻模式（回到纯防御：只在敌舰队进入本土时增援）
country_event = {
\tid = ai_steward_war.11
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tremove_country_flag = ai_steward_war_offensive
\t}
}
"""

LOC_ZH = 'l_simp_chinese:\n ai_steward_war_name:0 "AI 托管·战争组件"\n'
LOC_EN = 'l_english:\n ai_steward_war_name:0 "AI Steward: War Component"\n'


def update_dlc(add=True):
    dlc = DOC / "dlc_load.json"
    raw = dlc.read_text(encoding="utf-8")
    cfg = json.loads(raw)
    mods = cfg.setdefault("enabled_mods", [])
    if add and ENTRY not in mods:
        mods.append(ENTRY)
    if not add:
        cfg["enabled_mods"] = [m for m in mods if m != ENTRY]
    bak = DOC / ("dlc_load.json.bak-war-" + time.strftime("%Y%m%d%H%M%S"))
    bak.write_text(raw, encoding="utf-8")
    dlc.write_text(json.dumps(cfg, separators=(",", ":")), encoding="utf-8")
    return dlc.read_text(encoding="utf-8")


def install():
    (MOD / "common" / "on_actions").mkdir(parents=True, exist_ok=True)
    (MOD / "events").mkdir(parents=True, exist_ok=True)
    (MOD / "localisation" / "simp_chinese").mkdir(parents=True, exist_ok=True)
    (MOD / "localisation" / "english").mkdir(parents=True, exist_ok=True)
    (MOD / "descriptor.mod").write_text(DESC, encoding="utf-8")
    (MODDIR / "ai_steward_war.mod").write_text(DESC, encoding="utf-8")
    (MOD / "common" / "on_actions" / "zz_ai_steward_war.txt").write_text(ON_ACTIONS, encoding="utf-8")
    (MOD / "events" / "ai_steward_war_events.txt").write_text(EVENT, encoding="utf-8")
    (MOD / "localisation" / "simp_chinese" / "ai_steward_war_l_simp_chinese.yml").write_text(
        LOC_ZH, encoding="utf-8-sig")
    (MOD / "localisation" / "english" / "ai_steward_war_l_english.yml").write_text(
        LOC_EN, encoding="utf-8-sig")
    print("mod files written:", MOD)
    print("dlc_load now:", update_dlc(True))


def remove():
    import shutil
    if MOD.exists():
        shutil.rmtree(MOD)
    p = MODDIR / "ai_steward_war.mod"
    if p.exists():
        p.unlink()
    print("mod removed")
    print("dlc_load now:", update_dlc(False))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "install"
    if mode == "install":
        install()
    elif mode == "remove":
        remove()
    else:
        print("用法: python _install_war_mod.py install|remove")
