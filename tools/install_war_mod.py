# -*- coding: utf-8 -*-
"""安装/卸载「AI 托管·战争组件」本地 mod：
战时每月：军用舰队转 aggressive、同星系自动追击敌舰队、空闲舰队增援最近威胁；
可选「进攻模式」（ai_steward_war.10 开启 / .11 关闭）让空闲舰队推进最近敌国星系。
用法: python tools/install_war_mod.py install|remove
"""
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DOC = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris"
MODDIR = DOC / "mod"
MOD = MODDIR / "ai_steward_war"
ENTRY = "mod/ai_steward_war.mod"
LAUNCHER_DB = DOC / "launcher-v2.sqlite"

DESC = (
    'name="AI Steward: War Component"\n'
    'version="0.8.1"\n'
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
\t\t\t\t\tNOT = { has_fleet_flag = dimensional_fleet }
\t\t\t\t}
\t\t\t\tif = {
\t\t\t\t\tlimit = {
\t\t\t\t\t\tfleet_power < 5000
\t\t\t\t\t\tNOT = { is_in_combat = yes }
\t\t\t\t\t}
\t\t\t\t\tset_fleet_flag = ai_steward_weak
\t\t\t\t}
\t\t\t\telse = {
\t\t\t\t\tif = {
\t\t\t\t\t\tlimit = { has_fleet_flag = ai_steward_weak }
\t\t\t\t\t\tremove_fleet_flag = ai_steward_weak
\t\t\t\t\t}
\t\t\t\t\tset_fleet_stance = aggressive
\t\t\t\t}
\t\t\t}
\t\t}
\t\telse = {
\t\t\tremove_country_flag = ai_steward_war_offensive
\t\t\tevery_owned_fleet = {
\t\t\t\tlimit = {
\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t\thas_fleet_flag = ai_steward_weak
\t\t\t\t}
\t\t\t\tremove_fleet_flag = ai_steward_weak
\t\t\t\tset_fleet_stance = aggressive
\t\t\t}
\t\t}
\t\t# 经济政策：由战略引擎设置 flag；每月重申，覆盖游戏 AI 的回退
\t\tif = {
\t\t\tlimit = {
\t\t\t\thas_country_flag = ai_steward_econ_civilian
\t\t\t}
\t\t\tset_policy = {
\t\t\t\tpolicy = economic_policy
\t\t\t\toption = economic_policy_civilian
\t\t\t\tcooldown = no
\t\t\t}
\t\t}
\t\tif = {
\t\t\tlimit = {
\t\t\t\thas_country_flag = ai_steward_econ_military
\t\t\t}
\t\t\tset_policy = {
\t\t\t\tpolicy = economic_policy
\t\t\t\toption = economic_policy_military
\t\t\t\tcooldown = no
\t\t\t}
\t\t}
\t\tif = {
\t\t\tlimit = {
\t\t\t\thas_country_flag = ai_steward_econ_balanced
\t\t\t}
\t\t\tset_policy = {
\t\t\t\tpolicy = economic_policy
\t\t\t\toption = economic_policy_balanced
\t\t\t\tcooldown = no
\t\t\t}
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
\t\t# 1) 同星系接敌：扫描星系；有敌方军用舰队时，命令该星系内我方军用舰队追击
\t\tevery_system = {
\t\t\tlimit = {
\t\t\t\tOR = {
\t\t\t\t\tNOT = { root = { has_country_flag = ai_steward_conserve } }
\t\t\t\t\tAND = {
\t\t\t\t\t\texists = space_owner
\t\t\t\t\t\tspace_owner = { is_same_value = root }
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tany_fleet_in_system = {
\t\t\t\t\texists = owner
\t\t\t\t\towner = { is_hostile = root }
\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t}
\t\t\t}
\t\t\trandom_fleet_in_system = {
\t\t\t\tlimit = {
\t\t\t\t\texists = owner
\t\t\t\t\towner = { is_hostile = root }
\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t}
\t\t\t\tsave_event_target_as = ai_steward_enemy_fleet
\t\t\t}
\t\t\tevery_fleet_in_system = {
\t\t\t\tlimit = {
\t\t\t\t\texists = owner
\t\t\t\t\towner = { is_same_value = root }
\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t\tNOT = { is_in_combat = yes }
\t\t\t\t\tfleet_power >= 5000
\t\t\t\t}
\t\t\t\tauto_follow_fleet = {
\t\t\t\t\ttarget = event_target:ai_steward_enemy_fleet
\t\t\t\t\tattack_fleet = yes
\t\t\t\t}
\t\t\t}
\t\t}

\t\t# 2) 空闲舰队：进攻模式→最近敌国星系；否则→最近的本土受威胁星系
\t\tif = {
\t\t\tlimit = {
\t\t\t\thas_country_flag = ai_steward_war_offensive
\t\t\t\tNOT = { has_country_flag = ai_steward_conserve }
\t\t\t}
\t\t\tevery_owned_fleet = {
\t\t\t\tlimit = {
\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t\tis_fleet_idle = yes
\t\t\t\t\tfleet_power >= 5000
\t\t\t\t}
\t\t\t\tclosest_system = {
\t\t\t\t\tlimit = {
\t\t\t\t\t\texists = space_owner
\t\t\t\t\t\tspace_owner = { is_hostile = root }
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
\t\t\t# 首都受威胁：所有强舰队集中回防首都
\t\t\tif = {
\t\t\t\tlimit = {
\t\t\t\t\tcapital_scope = {
\t\t\t\t\t\tsolar_system = {
\t\t\t\t\t\t\tany_fleet_in_system = {
\t\t\t\t\t\t\t\texists = owner
\t\t\t\t\t\t\t\towner = { is_hostile = root }
\t\t\t\t\t\t\t}
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tcapital_scope = {
\t\t\t\t\tsolar_system = {
\t\t\t\t\t\tsave_event_target_as = ai_steward_capital
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tevery_owned_fleet = {
\t\t\t\t\tlimit = {
\t\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t\t\tis_fleet_idle = yes
\t\t\t\t\t\tfleet_power >= 5000
\t\t\t\t\t}
\t\t\t\t\tqueue_actions = {
\t\t\t\t\t\tmove_to = event_target:ai_steward_capital
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\telse = {
\t\t\tevery_owned_fleet = {
\t\t\t\tlimit = {
\t\t\t\t\tis_ship_class = shipclass_military
\t\t\t\t\tis_fleet_idle = yes
\t\t\t\t\tfleet_power >= 5000
\t\t\t\t}
\t\t\t\tclosest_system = {
\t\t\t\t\tlimit = {
\t\t\t\t\t\texists = space_owner
\t\t\t\t\t\tspace_owner = { is_same_value = root }
\t\t\t\t\t\tany_fleet_in_system = {
\t\t\t\t\t\t\texists = owner
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

# 经济政策：军事经济（由战略引擎在消费品安全余量充足时触发）
country_event = {
\tid = ai_steward_war.20
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tset_country_flag = ai_steward_econ_military
\t\tremove_country_flag = ai_steward_econ_civilian
\t\tremove_country_flag = ai_steward_econ_balanced
\t\tif = {
\t\t\tlimit = {
\t\t\t\tcan_set_policy = { policy = economic_policy option = economic_policy_military }
\t\t\t}
\t\t\tset_policy = {
\t\t\t\tpolicy = economic_policy
\t\t\t\toption = economic_policy_military
\t\t\t\tcooldown = no
\t\t\t}
\t\t}
\t}
}

# 经济政策：民用经济（消费品为负、合金仍有安全余量时触发）
country_event = {
\tid = ai_steward_war.21
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tset_country_flag = ai_steward_econ_civilian
\t\tremove_country_flag = ai_steward_econ_military
\t\tremove_country_flag = ai_steward_econ_balanced
\t\tif = {
\t\t\tlimit = {
\t\t\t\tcan_set_policy = { policy = economic_policy option = economic_policy_civilian }
\t\t\t}
\t\t\tset_policy = {
\t\t\t\tpolicy = economic_policy
\t\t\t\toption = economic_policy_civilian
\t\t\t\tcooldown = no
\t\t\t}
\t\t}
\t}
}

# 经济政策：平衡经济（默认/和平期）
country_event = {
\tid = ai_steward_war.22
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tset_country_flag = ai_steward_econ_balanced
\t\tremove_country_flag = ai_steward_econ_military
\t\tremove_country_flag = ai_steward_econ_civilian
\t\tif = {
\t\t\tlimit = {
\t\t\t\tcan_set_policy = { policy = economic_policy option = economic_policy_balanced }
\t\t\t}
\t\t\tset_policy = {
\t\t\t\tpolicy = economic_policy
\t\t\t\toption = economic_policy_balanced
\t\t\t\tcooldown = no
\t\t\t}
\t\t}
\t}
}

# 保存舰队：宗主战争里只在自家星系自动接敌，避免当炮灰（等独立窗口）
country_event = {
\tid = ai_steward_war.23
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tset_country_flag = ai_steward_conserve
\t}
}

country_event = {
\tid = ai_steward_war.24
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tremove_country_flag = ai_steward_conserve
\t}
}

# 强制改善附属协议（战略引擎在实力达到阈值后触发）：
# 允许带贡赋扩张、只参加宗主防御战、恢复独立投票权
country_event = {
\tid = ai_steward_war.25
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tevery_agreement = {
\t\t\tlimit = {
\t\t\t\tagreement_preset = preset_vassal_oppressive_ai
\t\t\t}
\t\t\tset_rule_can_subject_expand = can_expand_with_tithe
\t\t\tset_rule_join_overlord_wars = defensive
\t\t\tset_rule_can_subject_vote = yes
\t\t\tset_rule_can_subject_do_diplomacy = yes
\t\t}
\t}
}

# 消费品缺口：把人口最多的非首都殖民地设为工厂世界（AI 会按定位补工厂区）
country_event = {
\tid = ai_steward_war.26
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tordered_owned_colony = {
\t\t\tlimit = {
\t\t\t\tis_capital = no
\t\t\t\tNOT = { has_designation = col_factory }
\t\t\t}
\t\t\tposition = 0
\t\t\torder_by = trigger:planet_size
\t\t\tset_colony_type = col_factory
\t\t}
\t}
}

# 结构性救济（作弊级）：给工厂世界加工业区，快速补消费品岗位
country_event = {
\tid = ai_steward_war.27
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tordered_owned_colony = {
\t\t\tlimit = { has_designation = col_factory }
\t\t\tposition = 0
\t\t\tadd_building = building_factory_3
\t\t}
\t}
}

# 诊断：把全部军用舰队移动回首都星系（仅手动触发，用于验证移动链路）
country_event = {
\tid = ai_steward_war.99
\thide_window = yes
\tis_triggered_only = yes

\timmediate = {
\t\tcapital_scope = {
\t\t\tsolar_system = {
\t\t\t\tsave_event_target_as = ai_steward_home_system
\t\t\t}
\t\t}
\t\tevery_owned_fleet = {
\t\t\tlimit = {
\t\t\t\tis_ship_class = shipclass_military
\t\t\t}
\t\t\tqueue_actions = {
\t\t\t\tmove_to = event_target:ai_steward_home_system
\t\t\t}
\t\t}
\t}
}
"""

# 把策略配置里的弱舰队阈值写入 mod（默认 5000；改配置后重装+重启生效）
_DYN = Path(__file__).resolve().parent.parent / "policy" / "strategy_dynamic.json"
try:
    _WEAK = int(float(json.loads(_DYN.read_text(encoding="utf-8")).get("weak_fleet_power", 5000)))
except Exception:
    _WEAK = 5000
EVENT = EVENT.replace("fleet_power < 5000", "fleet_power < %d" % _WEAK)
EVENT = EVENT.replace("fleet_power >= 5000", "fleet_power >= %d" % _WEAK)

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


def update_launcher_db(add=True, mod_dir=MOD):
    """Keep the Paradox Launcher playset in sync (otherwise it can rewrite dlc_load)."""
    if not LAUNCHER_DB.exists():
        print("launcher db not found - skip playset sync")
        return
    bak = LAUNCHER_DB.with_name(LAUNCHER_DB.name + ".bak-war-" + time.strftime("%Y%m%d%H%M%S"))
    bak.write_bytes(LAUNCHER_DB.read_bytes())
    con = sqlite3.connect(str(LAUNCHER_DB))
    try:
        ps = con.execute("SELECT id FROM playsets WHERE isActive=1 AND isRemoved=0 "
                         "ORDER BY updatedOn DESC LIMIT 1").fetchone()
        if not ps:
            print("launcher: no active playset - skip")
            return
        psid = ps[0]
        row = con.execute("SELECT id FROM mods WHERE gameRegistryId=? LIMIT 1",
                          (ENTRY,)).fetchone()
        if add:
            if row:
                mid = row[0]
                con.execute(
                    "UPDATE mods SET displayName=?, version=?, dirPath=?, "
                    "status='ready_to_play', timeUpdated=? WHERE id=?",
                    ("AI Steward: War Component", "0.8.1", str(mod_dir),
                     int(time.time()), mid))
            else:
                mid = str(uuid.uuid4())
                con.execute(
                    "INSERT INTO mods (id, gameRegistryId, displayName, version, tags, "
                    "requiredVersion, dirPath, status, source, timeUpdated, "
                    "isMetadataApplied, metadataStatus, keepLatest) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (mid, ENTRY, "AI Steward: War Component", "0.8.1",
                     '["Gameplay"]', "4.5.*", str(mod_dir),
                     "ready_to_play", "local", int(time.time()), 0, "not_applied", 1))
            exists = con.execute("SELECT 1 FROM playsets_mods WHERE playsetId=? AND modId=?",
                                 (psid, mid)).fetchone()
            if not exists:
                pos = con.execute("SELECT COALESCE(MAX(position),-1)+1 FROM playsets_mods "
                                  "WHERE playsetId=?", (psid,)).fetchone()[0]
                con.execute("INSERT INTO playsets_mods (playsetId, modId, enabled, position) "
                            "VALUES (?,?,?,?)", (psid, mid, 1, pos))
            con.execute("UPDATE playsets SET updatedOn=?, hasNotApprovedChanges=0 WHERE id=?",
                        (int(time.time() * 1000), psid))
        else:
            if row:
                mid = row[0]
                con.execute("DELETE FROM playsets_mods WHERE modId=?", (mid,))
                con.execute("DELETE FROM mods WHERE id=?", (mid,))
                con.execute("UPDATE playsets SET updatedOn=?, hasNotApprovedChanges=0 WHERE id=?",
                            (int(time.time() * 1000), psid))
        con.commit()
        print("launcher playset synced:", "add" if add else "remove", psid)
    finally:
        con.close()


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
    update_launcher_db(True)


def remove():
    import shutil
    if MOD.exists():
        shutil.rmtree(MOD)
    p = MODDIR / "ai_steward_war.mod"
    if p.exists():
        p.unlink()
    print("mod removed")
    print("dlc_load now:", update_dlc(False))
    update_launcher_db(False)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "install"
    if mode == "install":
        install()
    elif mode == "remove":
        remove()
    else:
        print("用法: python _install_war_mod.py install|remove")
