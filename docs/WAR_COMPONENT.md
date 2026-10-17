# 战争组件（AI Steward · War Component）

## 它做什么

一个由托管工具自动安装的**本地 mod**（只写入 `Documents\Paradox Interactive\Stellaris\mod`，
不改游戏本体）。战争期间，游戏自己的脚本引擎会每月执行：

1. **姿态**：把玩家全部机动军用舰队设为 `aggressive`（自动接敌）。
2. **同星系接敌**：舰队所在星系出现敌方**军用**舰队时，自动 `auto_follow_fleet`
   追击并攻击（`attack_fleet = yes`）。
3. **本土增援**：空闲（`is_fleet_idle`）的军用舰队自动前往**最近的、有我方领土且出现敌舰队**的星系。
4. **可选进攻**：打开进攻模式后，空闲舰队改为前往**最近的敌国星系**。

**v0.4 强弱分级**：`fleet_power < 5000` 的舰队转为 `evasive` 并打 `ai_steward_weak` 标记，
不参与自动追击/增援/进攻；`>= 5000` 的舰队才执行上述动作。避免弱舰队被单独送死。

**v0.5/0.6 首都集中回防 + 经济政策 + 附属国保存模式**：
- 首都星系出现敌舰队时，所有 `fleet_power >= 5000` 的空闲舰队集中回防首都，
  不再各自跑最近的受威胁星系（避免被各个击破）；
- 经济政策事件 `.20/.21/.22`（军事/民用/平衡）由 `strategy_engine.py` 根据
  消费品/合金月净收入触发；事件 1 每月重申一次，覆盖游戏 AI 的回退；
- `v0.5.1` 排除 `dimensional_fleet` 等特殊舰队，避免 `set_fleet_stance` 警告；
- `v0.6.0` 新增 `ai_steward_conserve`（事件 `.23/.24`）：当玩家是附属国、
  忠诚 < -50 且军力 < 宗主 50% 时，只在自家星系自动接敌，不在宗主战争里当炮灰。

只对玩家国家生效（`is_ai = no`）；AI 国家的行为不受影响。

## 开关

- 默认：**防御模式**（第 1–3 条始终生效）。
- 进攻模式：面板上的「战争模式」按钮 / `F9` 热键 / 命令行：
  ```
  python tools\war_mode.py on
  python tools\war_mode.py off
  ```
  本质是控制台事件 `ai_steward_war.10` / `.11`，设置/清除国家 flag `ai_steward_war_offensive`。

## 安装 / 卸载

```
python tools\install_war_mod.py install
python tools\install_war_mod.py remove
```

安装后**必须重启游戏**（mod 只在启动时加载）。`dlc_load.json` 会被自动加入/移除
`mod/ai_steward_war.mod`，原文件留有带时间戳的备份。
安装器还会把 mod 写入 Paradox 启动器的 active playset（`launcher-v2.sqlite`，
enabled=1 / position=1），防止下次启动时启动器用 playset 覆盖 `dlc_load.json`。

## 验证

```
python tools\war_mode.py status    # 存档：我方战争数、舰队姿态、移动状态、进攻开关
python tools\war_mode.py verify    # 检查 mod 挂载 + error.log 脚本错误 + 战时 aggressive 比例
python tools\check_war_mod.py      # 只看机动军用舰队（排除恒星基地）
```

也可以直接双击项目根目录的 `check_war.bat`（重启游戏后运行）。

诊断事件（手动触发，会真的移动舰队）：
```
event ai_steward_war.99    # 全部军用舰队回到首都星系（验证移动链路）
```

`error.log` 路径：`Documents\Paradox Interactive\Stellaris\logs\error.log`。

## 边界（如实说明）

- 这是**战役层**自动化：接敌、增援、推进；不做精确集火/走位/技能微操。
- 进攻模式会把舰队送向最近敌国星系，可能撞上优势敌军；默认关闭，建议在我方军力明显占优时开。
- 需要游戏重启才加载；mod 脚本错误会在 `error.log` 里逐条报告。
- 与 `auto_pause_when_idle` 等本地 mod 共存；不改动游戏安装目录。

## 验证记录（2026-10-17）

- 用独立 `-userdir` + `-mod` 启动第二个《群星》实例（不碰正在玩的存档）做脚本加载测试。
- 初版把 `move_to` 当普通 effect 用，游戏报：
  `move_to effect ... accepts only yes or no as values`（events 文件 line 85/103）。
- 已改为舰队动作队列语法 `queue_actions = { move_to = event_target:... }`；
  第二实例 `error.log` 无任何 `ai_steward_war` 错误。
- **真实存档第一次重启（17:03-17:04）**：mod 成功加载，6/6 机动军用舰队 stance 变为
  `aggressive`（事件 1 生效）。但事件 2 的 `closest_system` 防御分支每星系报
  `Invalid context switch [owner] from ... [galactic_object]`（line 101，600 条）——
  `owner` 不能从 galactic_object 直接切；已改为 `space_owner`（vanilla an4_events 同款用法）。
- 同一次运行还发现：同星系追击分支在 fleet trigger 里用 `solar_system = { ... }` 报
  `Invalid context switch [solar_system] from ... [fleet]`（line 49）。已改为**星系级扫描**：
  `every_system` → 有敌方军用舰队 → `every_fleet_in_system`（我方军用舰队）→ `auto_follow_fleet`。
  这样不再需要 fleet→system 的 trigger 作用域切换。
- 同时给 `space_owner` 和 fleet `owner` 加了 `exists` 守卫（无主星系/无主太空生物没有 owner，
  直接切会报错）。
- 仍需**再重启一次**加载这两处修复（`space_owner` + `every_system`），然后由
  `war_mode.py verify` 确认防御/追击/移动分支。
