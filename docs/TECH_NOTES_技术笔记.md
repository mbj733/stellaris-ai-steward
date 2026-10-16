# 内核读取项目 · 状态与线索（2026-10-15）

> 目的：直接读游戏进程数据做决策（不靠截图猜）。动态（内存扫描）＋静态（Ghidra）两路并进。

## 工具现状（tools/）

- `memread.py`：进程内存工具箱，自检 PASS。子命令：
  - `info <proc>` 内存区域；`scan <proc> --int/--int16/--float/--double/--str/--hex <值> --save <名>`
  - `filter <proc> <同上> --save <名>`（在上次命中集上按新值过滤）
  - `read <proc> 0x地址 [--size N] [--type int32|float|str]`；`write`（危险，需 --yes）
  - `ptr <proc> 0x目标 --depth N --near 0xN`（向上找指针链，找静态基址）
- `read_save.py`：1.5 秒解析完整存档（23MB 状态）；`pe_recon.py` 静态侦察器；
- 沙箱内读游戏进程会被拒（err=5），一切内存操作必须沙箱外（escalated）执行。

## 已验证的事实

- 游戏进程（2026-10-15 会话）：约 9.4GB 可写内存。
- **活跃日期字符串对象**（std::string SSO，会随日期刷新，09.11→10.02 已实测）：
  `0x2e87a023bf8`、`0x2e8c2c06188`。位于"顶栏 UI 文本缓存区"（0x2E87A02xxxx）。
- 同区还有一个 `"33 / 75"`（舰队容量文本）字符串对象 @ `0x2E87A025938`，
  被 517 个指针引用 → 该区是**UI 缓存**，引用多但不是游戏状态本体。
- 顶栏读数（供对照）：日期 2225.10.02（暂停）；22K+124 / 9.5K+36 / 8.3K+62 / 6.6K+18 /
  2.1K+11 / 26K+62 / 50+0 / 1K+4 / 2.0K+24 / +61 / 78 / 0-3 / 2-3 / 33-75

## 已排除（别再重复试）

- int32/int16 候选 9232/9233/9250/9251/9271/9272 → 过滤全 0
- int32 801251 单命中（0x2e6c5cb77b5）= **巧合**（值不随日期变，属静态数据）
- int32 801272（10.02 推算值）/ int64 801272 / float32 801272 → 全内存 0 命中
- hex 结构体模式 b1 08 0a 02、b1 08 00 00 0a 00 00 00 02 00 00 00、0a 02 b1 08 → 0
- hex 02 0a b1 08 单命中 @0x2e8d3159d30 = 4 字节数组元素巧合（无指针指向，读数不符）
- float32 9272 → 8 处，未验证（下次可过滤）
- 结论：日期计数器不是"自 2200/年 0 起的简单天数 int"；编码待静态侧确认。

## 下一步（按优先级）

1. **用户存档 → 资源定位**：暂停状态手动存档 → `read_save.py` 拿精确资源值（float）
   → `memread scan --float` 定位资源地址（资源=决策核心数据）；随后用"再存一档/截图"做差分验证。
2. **Ghidra 静态收口**：项目 `<工具目录>\tools\ghidra_projects\Stellaris`，日志
   `tools\_ghidra_run.log`。完成后：
   - 找日期格式化函数（"x.x.x" 拼接 / %d.%02d.%02d 或本地化格式）→ 反推日期结构体偏移
   - 找控制台指令表（human_ai 等已定位注册区）→ 游戏状态对象访问链
   - 查询方式：REA CLI（`node <工具目录>\npm-global\node_modules\rea-agents\scripts\rea.mjs ...`）
     或 Ghidra headless + 脚本；REA 沙箱外才可用（native_authority 检查）。
3. 指针链：对"资源/日期"最终地址做 `memread ptr` 找模块基址路径（固化重启后可用）。

## 环境备注（重要）

- Ghidra 12.1.4：`<工具目录>\tools\ghidra_12.1.4_PUBLIC`（**中文路径会导致 log4j 启动失败，勿放回中文路径**）
- JAVA_HOME=`<工具目录>\jdk\jdk-21.0.12.1+1`；`config.toml` 已加 `[mcp_servers.rea.env]`
- Codex 的 REA MCP 在服务重启后需重连（重启应用即恢复）；REA CLI 随时可用

## 用户协作约定

- **截图由用户提供**；不得再自动恢复/最小化游戏窗口（flash_peek / date_diff 自动模式停用）
- 用户经常停在暂停状态；日期推进依靠用户自然游玩

## 2026-10-15 突破：资源表已定位（12/12 全中）

- **存储格式：int64 定点数 ×100000（1e5）** —— 这是关键发现，float 全扫不到的原因。
- 玩家资源表地址（本进程会话有效；重启后地址会变）：
  - energy @ `0x2E89C5DAFB0` = 22928.34896
  - 后续按 +8 字节步进：minerals +0x8 / food +0x10 / physics +0x18 / society +0x20 /
    engineering +0x28 / influence +0x30 / unity +0x38 / trade +0x40 /
    consumer_goods +0x48 / alloys +0x50（= 0x2E89C5DB000）
  - artifacts @ `0x2E89C5DB040`（中间 0x40 空档是其它资源位：战略资源/星界丝线等）
- 定位法（可复用）：`save_resources.py` 从存档取精确值 → `memread.py probe <proc> <值>`
  多编码探测（f32/f64/int/×100/×1000/×1e5/字符串）→ 命中 i64×1e5 → 邻域解码 12/12 对齐。
- 指针线索：`0x2E64DC3EAE0` 存"指向资源数组"的指针；`0x2E64DC3EAD8` 存指向它的指针；
  疑似国家对象基址 ~`0x2E64DC3E5C0`（+0x520 处达资源指针链）；深度 4 未见模块静态区。
- **重启后复现方案**（写入 reader 用）：读最新存档资源值 → 内存扫 int64（12 个值、8 字节
  步进连续命中即数组）→ 得新地址；约 30 秒。指针路径（depth 5-6 或 Ghidra）后补。
- 日期状态：仍未定位（int64 801251 → 0；int64 9272 → 66 处未验证；f32/f64/结构体已排除）。

## 2026-10-16 凌晨（进度续）

- ✅ **资源读取模块上线**：`tools/game_reader.py`（缓存 + 存档靶值扫描自愈），
  入口 `pilot.py state` / `run.bat state`。实测读数与屏幕对照 8/8 吻合。
- ✅ **Ghidra 静态分析完成**：`REPORT: Analysis succeeded`（stellaris.exe，项目在
  `<工具目录>\tools\ghidra_projects\Stellaris`）。后续用它定位日期与弹窗状态。
- 🔁 日期：旧候选集在新日期（2229.07.25，+1373 天）下全部过滤为 0；新备好候选集
  `n10645`（int32 63 处）/`n16_10645`（4576 处），等下一次日期推进再过滤。
- 🧷 指针固化：depth 6（±4KB 窗）未达模块静态区；现以"缓存 + 存档靶值重扫"兜底，
  实际使用不受影响；深度扫描与 Ghidra 路径留作后续。

## 2026-10-16 凌晨：动作侧首次实机全链路成功

- `pilot.py act`（一次性动作命令）：切前台→抓屏→识别→决策→点击→验证→还焦点。
- 成功案例：**"民主选举"窗口** → 识别（close_button 模板 @templates/close_button.png）
  → 规则（known_events：民主选举→关闭窗口，不花影响力）→ 实机点击 ✕ → 验证窗口消失 ✔。
- 已归档窗口类型：①"研究完成!"（文本档案 profiles.json：点「新研究」）②"民主选举"（关窗）。
- 安全闸：close_only 窗口未命中规则 → 强制保持；ESC 菜单不在档案内 → 永不乱动。
- 待归档：科研三选一卡片界面、普通事件弹窗（等用户截图）。

## 2026-10-16（下午）内存级动作通道：控制台执行链打通（静态，全部经 Ghidra 核实）

### 0) 环境更新
- 当前 Codex 环境 = danger-full-access + approval never：**不再需要 escalated**，直接跑即可；
  旧的"沙箱内 err=5 必须沙箱外"说法作废。
- Ghidra 脚本注意：`Memory.findBytes(..., end=null)` 会 NPE；本项目自 EvtWin2 起改用自写分块字节扫描器。

### 1) 先前的 FUN_14014e940 只是"启动参数解析器"
- 它处理 `-human_ai`/`-debugtooltip`/`-berserk_ai`/`-fullgalaxyspawn`/`-game_paused false` 等启动开关：
  逐条 `MOV byte[flag],1`，无其它调用（已看汇编：14fd4e 处就一条 MOV + JMP）。
- 标志地址（写点也记了）：human_ai=0x142814839(写@14014fd4e)、berserk_ai=0x14281483a、
  fullgalaxyspawn=0x14281483b、daily_jobs_update=0x14281485e、debugtooltip=0x1431146f9、
  combat_debug=0x143111210、overnight=0x14311123a 系、game_paused false=0x14311123c+0x1431146f8。
- **human_ai 标志的消费者疑问**：全图仅 4 个引用——2 个"复选框 setter"（0x140959f10 写 human_ai+0x142814833；
  0x14095a070 写 human_ai）、1 个调试菜单构建读点（0x140a99216，FUN_140a98c80）、1 个启动参数写点。
  原始字节扫描（全图 qword/dword 指向该地址）也是 0 命中 → **本版本该开关可能已退化**，只能实机验证：
  写 1 → 恢复游戏 → 看 AI 是否接管我方帝国。对照：debugtooltip 标志有 **130+ 处读写**（写 1 立即全 UI 生效），
  是可靠的首个实机验证目标。
- setter 家族在 0x140959f10 / 0x14095a060..0x14095a08a（每 0x10 一条，写 834/836/839 等）；
  其定义表在 0x1423a94c0 / 0x1423a9d60 一带（含 setter/getter 函数指针）。

### 2) 真·游戏内控制台执行链（本日最大成果）
- 取/建 console 管理器：`FUN_14016b4f0()` → 全局 `0x143159360`（管理器：+8=命令数组、+0x14=命令数；
  条目 0xa8 字节：+8=名字 char*、+0x10=别名数、+0x18=别名数组、+0x38=executor、+0x40=handler、+0x48=ctx）。
- 命令注册：
  - `FUN_140ee4f70` 注册 "resource"→FUN_140ee6e80、"research_technology"→FUN_140ee6ef0、"add_anomaly"、
    "gfxculture"、"create_megastructure"、"activate_ascension_perk"、"crisis_perk"、"activate_tradition"、
    "planet_destruction_gfx"、"spawn_astral_rift"、"add_relic"、"add_specimen"、"add_ship"、"spawnentity"、"heatmap"…
  - `FUN_1415f7790` 注册另一批（"finish_research" 等，字符串区 0x14246cfc8 一带）。
- **控制台 UI 实际提交序列**（FUN_141b13120 内实测汇编，我们照抄）：
  1. `FUN_14015bcf0(wrapper, text, len)`  构造输入字符串对象（0x30：+0x10 起 std::string 布局，+0x20=size、+0x28=cap）
  2. `FUN_14015af40(wrapper, vec, 0x20)`  按空格切分；vec 0x18：{+0=vtable(PTR_FUN_1422fe5b0)、+8=元素数组、+0x14=个数}；
     元素 0x30 字节（同字符串对象布局）
  3. `FUN_14016b4f0()`                   取 mgr
  4. `FUN_141b43650(mgr, out, vec, 0)`    执行（名字/别名查表 → handler）；out 0x40+ 字节，首字节=成功标志
- 工具已写好：**`tools/console_exec.py`**（`--scan` 列出全部命令 / 干跑 / `--go` 执行）。
  ★实机首验顺序：游戏读档 → `--scan`（应列出成百条命令）→ `--go "resource energy 5000"`（看能源变化验证通道）。
- 风险与纪律：远程线程调用游戏函数有风险 → 先备份存档（save_backup 已有）、游戏暂停时执行；崩溃则回滚。

### 3) 事件窗口链（推进中）
- `FUN_1410793a0` = 事件/消息窗口 Setup：找 "close" 子控件并注册关闭回调（回调对象在窗口对象 +0x728）、设置
  "Title"、"message_settings_button"，再 `FUN_14107d780` → 逐选项 `FUN_14107a180`。
- `FUN_14107d780(out, ?, 选项表, ctx)`：遍历 0x10 步长选项数组（过滤 FUN_140a22ca0），逐个调 FUN_14107a180。
- `FUN_14107a180`：构建 `event_option_<n>`（模板 "event_window_option_entry"）+ `event_option_button` 按钮；
  按钮回调由 `FUN_1407b5a10(option+0x4f0, 回调obj, 事件数据)` 构造，经按钮 vtable+0x2b8 注册（+0x2c8 取默认参）。
  → 回调对象内部目标仍是下一步（FUN_1407b5a10 630 行）。
- CEventWindow::Setup 的 lambda/bind_t RTTI（0x1428c59a0 / 0x1428c59e0）**无 vftable/COL**（纯 typeid 名），
  原 vftable 追踪路线作废；改经 FUN_14107d780 调用者查 Setup 本体。
- 相关表：0x1436a2b80 区（8 字节/条，内含函数 RVA 对）；0x1436b0260 区（{fn,fn} 对，含 telemetry 包装 FUN_141291c80/ce0）。
- 脚本：tools/ghidra_scripts/EvtWin{,2..11}.java（连同 _ghidra_*.log 一并留档）。

## 2026-10-16（夜）内存级控制台 **实机全链路打通（已多次实测）**

### 工具
- `tools/console_exec.py`：`--scan` 列 310 条命令 / 干跑 / `--go` 真执行。
  链路 = FUN_14016b4f0 取管理器 → FUN_14015baa0 构造输入串（**必须用这个构造器**：cap 初值 0xF=SSO；
  别用零对象+assign，会造出"堆指针+cap=0xF"的非法态）→ FUN_14015af40 按空格切分 → FUN_141b43650 执行。
- 命令条目结构（0xa8 字节）：+8 名字 char*、+0x10 别名数、+0x18 别名数组、+0x38 通用 thunk、+0x48 真实现函数、+0x50/+0x58 附加。
  执行返回 out 结构：首字节=成功；+0x18 处内联/堆字符串 = 游戏写回的消息（可读！）。

### 实测记录（已验证）
1. `debugtooltip` → 标志 0x1431146f9 由 0→1（立刻生效，悬停出现调试信息）。
2. `resource energy 1000` → 执行成功，回传消息「地球联合国 gets 1000 能量币!」；
   但 energy 仍 25000.00 —— **原因=顶到存储上限 25000，超出被丢弃**（游戏正规逻辑）。
3. `resource minerals 500` → **11764.08947 → 12264.08947（+500 精确落账，暂停中也即时生效）**。
   → 该块（本次会话 0x1B38701F3F0）就是**活库存**；干跑时该块地址每次重扫都可能变，靠存档靶值重找。
4. `human_ai` 双向开关实测：ON→OFF→ON 均正确（out 消息 = "Human AI is now ON/OFF"；标志 0x142814839/0x142814833 同步翻转）。
   **待实机确认**：AI 是否真的接管玩家帝国（静态上 839 无游戏逻辑读者，存疑；已置 ON 等用户解除暂停观察）。

### 玩家资源块（权威定位法，已修进 game_reader）
- 存档路径：`country.<player>.modules.standard_economy_module.resources`（玩家=player.country）。
  **旧启发式（取最大 energy 的 resources 块）会抓到堕落帝国（145000/135000），已弃用。**
- 存内存中为 int64 定点 ×1e5、12 槽 8 字节步进（energy..alloys），minor_artifacts 在 +0x90。

### 其他控制台命令（已确认在册，可随时用）
- `window`（参数 open/close）、`remove_notification`、`instant_build`、`survey`、`observe`、
  `research_technology`、`finish_research`、`research_all_technologies`、`max_resources`、`influence`、`unity`、
  `add_relic`、`add_anomaly`、`add_ship`、`activate_tradition`、`debug_mode`、`game_paused` 等（完整 310 条见 tools/_console_commands.txt）。

## 2026-10-16（深夜）托管开关 UI + 版本守卫（已实装）

- **用户实机确认：human_ai 生效**（解除暂停后 AI 接管帝国；资源被 AI 花用，能量 25000→17636 等）。
- `tools/hai_ui.py`：悬浮置顶小面板（状态直读内存、按钮/F8 全局热键切换、位置记忆、单实例锁、
  无控制台 stdout 兜底）；`AI托管开关.bat` 双击启动（pythonw，无黑窗）。
- `console_exec.py` 重构：`open_game()/read_flag()/execute_command()/read_out_message()` 供复用；
  **版本守卫**：4 个函数入口 24 字节指纹（SIGS），游戏更新后 open_game 直接抛错拒绝执行。
- 回归通过：`resource minerals 100` ok=True；面板窗口已起（title "AI 托管"，40,90）。
- 待办：① 事件弹窗 × human_ai 交互专项测试（核心诉求）；② `window close` / `remove_notification` 参数实测；
  ③ （可选）决策大脑 v2。

## 2026-10-16（凌晨·深）托管×事件 自动测试 + 关窗命令实证（全部由机器自动完成）

### 自动测试方法（不需要用户参与）
- 零副作用测试事件：`ambition.125`（标题"无可指摘"，单选项，无 immediate/effect；扫描器 `_find_benign2.py` 另有 589 个候选）
- 触发回执：`event ambition.125` → **"Executed #200125"**（数字 id=200125）
- **暂停状态探针**：`idler = *(0x143114E68)`；暂停字节 = `idler + 0x594`（1=暂停）。
  校准：`game_paused true/false` ⇄ 1/0，读写作均可靠。
- human_ai 命令**延迟 1~3 秒生效**（排到 UI 线程消息；轮询读到 (1,1)/(0,0) 才算落定，面板已加提示）

### 核心结论（对照实验）
- **托管 ON：连续 3 次触发事件，暂停字节恒 0 → 不卡住**（AI 处理，不弹拦路窗）
- **托管 OFF：同一事件 3 秒内暂停字节 1 → 弹窗拦路 + 自动暂停**（用户原痛点根源确认）

### 关窗命令（内存级"点掉窗口"）
- 用法：`window open <窗口名>` / `window close <窗口名>`；窗口名 = 界面类型名
  （事件窗 = **"EventWindow"**，见 interface\eventwindow.gui `name = "EventWindow"`）
- 实测：`window close EventWindow` → 游戏回话 **"Window closed"** ✓（偶发失败=窗口不存在或时机，重试 2-3 次可靠）
- 坑：关闭不自动取消暂停 → 需再来一发 `game_paused false`
- 坑：`window open` 对任何名字都回 "Window opened"（不可作存在性判据）
- 消息布局因 handler 而异 → `read_out_message` 已改为多布局穷举（(0x18,0x20,0x28)/(0x18,0x28,0x30)/(0x08,0x10,0x18)）

### 现场纪律
- 测试后现场：托管 ON、暂停 0、测试窗口全关；游戏已自玩到 2236 年+。

## 2026-10-16（凌晨·再续）事件处理的最终结论 + 情况日志读取器 v0

- **托管 ON = 事件静默处理（决定性测试）**：ON 状态下触发事件后，`window close EventWindow`
  连续三次都**找不到任何窗口**（ok=False）→ 事件根本没弹窗、没有残留、不暂停。
  → 挂机闭环成立：开着托管，人不在时事件全部由游戏 AI 静默处理。
- 存档实测：AI 已把帝国从 2231 玩到 **2243**（autosave_2243.01.01.sav，含 `cheated_on_save` 标记）。
- **情况日志读取器上线**：`tools/situation_reader.py`（存档直读，零风险）：
  - 进行中特殊情况：`gs.situations.situations.*`（按 `country=="0"` 过滤；
    item={country,target,type,progress,last_month_progress,approach,...}）
  - 特殊项目：`country.0.events.special_project`（status: completed/in_progress…）
  - 兴趣点/任务：`country.0.events.poi`
  - 事件链：`country.0.events.event_chain`
  - 首跑输出：特殊情况 0 条；未完成特殊项目 2 条（DRONES_PROJECT×2）；
    兴趣点 1 条（cultist_shipyard_poi；链 radical_cult）；事件链 3 条
    （first_league_chain / radical_cult / survey_habitable_worlds_chain）。
- 选项执行通道：尚无"选项/点击"类控制台命令；按钮回调的最后一段（FUN_140a32570 一带）仍未定位到
  "invoke 函数指针"——列为持续项；现阶段事件执行 = 托管 AI 静默处理。

## 2026-10-16（凌晨·续2）原生菜单侦察（三探）与 R2 节奏实测

- **R2 未定位时 90 秒重试节奏**：实证运转（日志 02:16:31 → 02:17:38 → 02:18:46 连续尝试，
  每轮尝试含 ~15s 扫描；定位成功即转 10 分钟心跳）。
- **原生调试菜单（含 human_ai 等开关）= C++ 自绘菜单（非 .gui 窗口）**：
  - 条目区域 0x1423a9400+（dev 开关标签："Using Randomlog"/"Using Saved Random"/"Deep Scans"/"Random Seed"，
    源文件 ingamempcommands.cpp）
  - 构建者 FUN_140a98c80 是虚方法（vtable @0x1436757e0；另被 data @0x1423c6f00 引用）
  - 控件族 FUN_140a8dd70 / FUN_140a92f70 / FUN_140a93870（vtable 群 0x1436752b8..0x1436753c0）；
    FUN_140a8dd70 的调用方含 FUN_1405faf10 与 FUN_140959950（0x140959xxx = 菜单模块）
  - 表区域 0x1423a9400..0x1423aa800 的引用已扫描（消费者=上述函数族 + FUN_141effc80 等）
  - **结论**：`window open <name>` 对 C++ 自绘菜单无效；"原生显示"需走
    构造函数→show 调用链 或 找开启热键 —— 列为长期探索项。
  - 面板现阶段交付形态 = 游戏风格 overlay（无边框金边、随游戏自启）。

## 2026-10-17（凌晨·静态攻坚）事件选项点击链 —— 已拆通至执行器前一层

**完整链条（静态已确认）**：
1. 选项按钮点击 → 命令翻译器 **FUN_14107b1d0（=CEventWindow 的命令分发方法）**：
   `strcmp(name, "event_option_button")` → `atol(param_2[0x17])` 解析选项号 →
   后续调 `FUN_1408e5d20(eventData, out, ctx, 1, 选项号, 1)` 构造"选中命令"。
   同函数还处理 "event_close" / "event_dismiss" / "coop_event_option_selected(_by_other)" /
   "selector_gui_presence_icon"；debugtooltip 打开时会打 "DEBUG: Event ID …"。
2. **FUN_1408e5d20(eventData, out, ctx, p4, idx, p6)** = 包装：
   `FUN_140a21e30(out, ctx, p4, eventData+0x5e0, idx, extra, p6)`；
   其中 extra = eventData->[0x590] ? eventData->[0x590]+0x60 : 0。
3. **FUN_140a21e30**：校验 `idx < *(int*)(eventData+0x5e0+0x14)`（选项数）→
   取选项项 `*(*(eventData+0x5e0+8) + idx*0x10)` → **FUN_140a21fb0** 构造命令对象。
4. 命令类 = CSelectEventOptionCommand（其 Execute 的 lambda RTTI @0x1428bb3be / @0x1428bb42d；
   类本体无独立 RTTI 字符串）→ 由游戏框架执行。
   事件内核模块 0x1403f5xxx（FUN_1403f5de0）亦构造同种命令（4 处）。

**事件窗口类方法表**：0x142403540 起（事件窗模块函数族：FUN_1410791b0 / 1410793a0 / 14107a180 /
14107a640 / 14107a730 / 14107b1d0 / 14107d200 / 14107d780 …，穿插 _guard_check_icall 槽）。
活体窗口对象特征：`[obj]` 指向该表一带；**obj+0x9e4 = 事件 id 字段**（分发器中已见引用）；
命令对象取名字段 = `(**(cmd_vtable+0xa8))(cmd)`，参数字符串在 `cmd+0xb8`（长度在 +0xd0）。

**下次开机现场计划（选项号 N 自动选择 v1）**：
① 托管 OFF + fire 测试事件（弹窗挂起）→ 扫描堆中 qword == 0x142403540（及邻近基址）的候选对象
→ 用 +0x9e4 字段与事件上下文交叉确认找到窗口 W；
② 调 `FUN_1408e5d20(**(W+0x78), scratch, W+0x80, 1, N, 1)` 构造命令；
③ 接框架执行（或先于 ② 尝试直接把命令对象交给命令队列函数——待定位）；
④ 验证：暂停消失/事件效果生效/窗口关闭。

**补**：FUN_140a21fb0 实测为"命令描述（文本）构造器"（把选项上下文拼成命令描述串，再装箱），
确认整条链是 UI 命令管线（描述→命令对象→框架执行）；进一步静态挖掘收益递减，
**下一里程碑必须实机**（按上面 ①-④ 执行）。

**实机扫描锚点（已静态定界）**：事件窗口类方法表 = **0x142403410..0x142403680**（连续 vtable，
左侧字符串 "…_container" 收尾、右侧 "DEBUG_OU…" 开头为界）。
槽位示例：FUN_14107d200 @+0x130、**FUN_14107b1d0 @+0x140（命令分发）**、FUN_1410791b0 @+0x150、
FUN_1410793a0 @+0x258（窗口 Setup）、FUN_141077720 @+0x260。
**活体窗口对象定位法（实机）**：全内存扫描 qword ∈ [0x142403410, 0x1424036A0) 的指针
（指向该表的任意位置即为类实例特征）；候选对象再用 +0x9e4（事件 id）交叉验证。

**（补）执行器静态路线的终局结论**：方法对表区域 0x1436a2b80..0x1436a2c80 全区间
**零引用**（连 data 引用都没有）→ 该区为"运行时按基址+索引"消费，静态无直接入口。
**执行器接线改为"运行时反查"终局程序**（下一步实机执行）：
  ① `evt_click.py build N` 构造出"选中命令"对象 → 转储其前 0x60 字节；
  ② 转储首 qword = 命令对象的 vtable 地址（运行时值）→ 回 Ghidra 把该地址 DumpVtable；
  ③ vtable 里"public virtual void Execute(void)"槽位 = 最终执行函数 → 实机直接调用；
  ④ 验证：事件选项生效（效果/日志/窗口关闭），失败则回滚（close EventWindow）。

### ⚠ 2026-10-17 03:41 实机事故复盘（game crash）
- **事故**：stage2 脚本按错误假设 `eventData = **(win+0x78)` 调用了 FUN_1408e5d20，
  而实测 `*(W+0x78)` 指向字符串数据区（内容 "interfac…"），作为指针解引用后在游戏进程内
  造成非法访问 → **游戏进程崩溃退出**（brain R7 如实记录 03:41:15）。
- **损失**：≈4 分钟进度（autosave_2267.01.01 @03:37 及 save_backup/pre_live_20261017 均在）。
- **已确认事实**：①窗口查找 `FUN_141c0c620(mgr,"EventWindow")` 实机可用（返回 0x1D9CD6E8DC0，
  对象头 [0]=真 vtable 0x14257C130，+0x58 内联名 "EventWindow"）；②**窗口对象的 +0x78 不是事件数据指针**
  （与反编译器所见的 `**(param_1+0x78)` 不符 → 分发器的 param_1 是另一个"命令上下文"对象，
  不是窗口实例；待重新识别该对象）。
- **纪律升级**：任何"指针链解引用后传入跨进程调用"的路径必须先做**指针健全性闸**
  （每一跳需落在可读区域；目标对象首字段应为 exe 区 vtable 或为空）；
  `evt_click.build_cmd` 已加该闸（触发时拒绝构造）。

### 🔧 2026-10-17 03:50 关键修正：两套"窗口对象"之分
- `FUN_141c0c620(mgr, name)` 返回的是**窗口类型条目**（+0x58 内联类型名 "EventWindow"、
  +0x78 指向 "interface/eventwindow.gui" 路径串）——**不是实例**，这就是崩溃的根源对象。
- **实例**在管理器 vtable `+0x58` 槽：`instance = (*(*mgr+0x58))(mgr, nameWrapper, 0, 0)`
  （window 命令同款路径；mgr=[0x143159458]）。
- 实例的三个已知锚：对象带 +0x9e4（事件 id）、+0x78 →（经二级解引用）= 事件数据。
  **任何后续调用前必须过指针闸**（已在 evt_click.build_cmd 实现）。
- `evt_click.get_window_instance()` 已实现"实例获取"通道；do_scan 改为
  "实例优先 + vtable 区间扫描备用"。

## 2026-10-16（凌晨·续3）托管系统加固纪要

- **窗口标题坑（已修）**：hai_ui v2 重写时遗漏 `root.title()`，窗口标题落成默认 "tk"，
  导致按标题搜索"窗口消失"的假象。已恢复 `title("AI 托管")` 并实测（TkTopLevel、可见、(40,90)）。
  另加：被"显示桌面"藏起时每 ~14 秒自检 deiconify+lift 找回。
- **R2 容差扫描（已上线并实测）**：`game_reader.find_by_scan_fuzzy`（能量锚点 ±5%、11 槽≥8 命中），
  高速运行时精确扫描追不上月度漂移 → 容差兜底单轮命中（02:23:25 实证）。

## 2026-10-17 凌晨（实机会话·崩溃与重大静态修正）

### 实机记录（04:09–04:12）
- 04:09 托管 OFF 成功（"Human AI is now OFF"）→ `event ambition.125` → "Executed #200125"，暂停=1 ✓。
- **窗口通道全失败**：+0x48 槽调用返回 0；vtable 区间扫描（已修运行时基址换算）命中 3 处，
  无一通过 plausible 校验 → 当轮未定位到窗口（脚本 `_live_evt1.py`）。

### 04:12:26 游戏崩溃（c0000005 @ RVA 0x1AA5F80）
- 位置：`FUN_141aa5f40`（事件"效果链"拷贝构造；崩溃指令 `MOV RDI,[RSI+0x38]` = 悬空节点读）。
- 时间线：+0x48 调用后约 3 分钟；期间除 brain 只读扫描外无其他跨进程写入。
- 判定：**+0x48 槽为主嫌疑（未证实）**。纪律：**vtable 槽调用前必须先从运行时读出目标函数地址
  → Ghidra 确认语义，再决定是否调用**；`evt_click.get_window_instance` 已默认禁用
  （do_scan 加 `via_slot=True` 才走该通道）。

### 静态重大修正（推翻 03:47 对"命令对象/执行器"的理解）
- **FUN_1408e5d20 链 = 描述文本构造**：产物是 0x30 字节 std::string 类对象（空串初始化形态可见），
  **不是可执行命令**；FUN_141b2d780 = string append、FUN_14030e8c0 = 追加换行（皆字符串工具，
  xref 上千处）。之前把他们当"执行器候选"是误读。
- **分发器 FUN_14107b1d0 = 描述文本 + coop 通知 + debugtooltip 显示**：正文（cap 90/260 已读全）
  没有"应用选项"调用。它处理 "event_option_button" 属于 hover/描述一侧。
- **"option_click" 字符串 = 遥测事件名**（FUN_1412913a0：help_menu_action + save_game_id +
  game_year 属性）——与执行链无关。
- CSelectEventOptionCommand::Execute 的 lambda RTTI @0x1428bb3be 仍然成立（类名在该 RTTI 串中）；
  命令类本体 vtable 尚未定位。

### 新锚点：真·点击链的运行时结构（EvtWin39 反编译 FUN_14107a180，窗口 Setup）
- 每选项建一个列表节点（0x20 字节 {elem@0, prev@8, next@0x10}）挂 **W+0x9e0**（计数 W+0x9e8，
  最早节点 W+0x9d8）；presence 图标节点挂 W+0xa00（计数 W+0xa08）。
- 选项按钮元素字段：**+0x20 = 选项号（int）**；**+0xb8 = 选项号字符串（std::string，槽+0x120 设置，
  分发器用 atol 读它）**；**+0xd8 = 嵌入的"点击处理器"对象**（其 vtable 槽+8 被 (W+0x230) 初始化
  = 挂窗口上下文）——框架点击时应调用该对象。
- 下一步（需游戏在跑，全只读）：`_live_evt3.py`：按事件 id 200125 扫 obj+0x9e4 定位 W
  → 走 W+0x9e0 链取 elem → 转储 elem+0xd8 处理器 vtable → Ghidra 命名 execute/click 槽
  → 确认语义后再调用（等价于真实点击）。
- 工具函数参考：FUN_14016af90 = int→string；FUN_141c161d0 = 按名找子元素；FUN_141c19cb0 = 建/取子元素。
- **建议栏（已上线）**：心跳时评估 战争/特殊情况/特殊项目/资源顶上限 → `[建议]` 日志（去重防刷屏）。
- **R7（本轮）**：游戏进程消失（退出/崩溃）→ 告警日志；重开自动重连。
- **日志轮转**：decisions.log>2MB、_watch.log>1MB 自动归档 .1。
- 运维实录：误杀看门狗导致大脑失联 → 重启看门狗后 12 秒内自动恢复（自愈路径验证）。

## 2026-10-16 晚 ★里程碑：事件选项内存级选择【已打通并实机验证】

**结论：整条"点击执行"谜题破解——不需要模拟点击、不需要窗口分发器。**
事件选项选择 = 一个原生函数调用：`FUN_1408e2270(活动事件项, 选项序号)`。

**对象层级（实机核对，三层）**：
- `W`（窗口实例，[W]=静态 0x142403550，+0x20="EventWindow"，+0x9e4=事件实例 id）
- `EVT`（gamestate 活动事件项；`gs=[base+0x3114700]`，`list=gs+0x180`(指针数组)，
  `cnt=gs+0x18c`；EVT+0x180=事件实例 id，EVT+8→X）
- `X → OBJ=*X`（事件数据：+8=事件编号 如 200125，+0x20=事件名，+0x5E0 选项表：
  +0x5F4=选项数、+0x5E8=数组、条目 = arr[idx*0x10]）

**执行链（FUN_1408e2270 内，已反编译）**：
构造 `CSelectEventOptionCommand`（vtable **0x1423ABDD8**，0x1a0 字节：
option@+8、事件编号@+0x20、选项号@+0x24、玩家@+0x28、scope 拷贝 +0x30）
→ `FUN_14099cd60`（校验：不通过则不提交，天然安全）→ `FUN_1408e9aa0` 装箱
→ `FUN_1405f88a0(cmd,0)` 提交命令管线（与真人点击同款）。
调用者：`FUN_14107c1b0`（8 个窗口类共用的"选项被选中"vtable 回调）、`FUN_14137cfb0`、`FUN_1408e2130`。

**修正（作废旧理解）**：`FUN_14107b1d0` 及其邻居（FUN_14137c560 等）= 纯**提示文本/描述构建器**
（param_3 是文本缓冲；处理 event_option_button/event_close 只为悬浮说明与 coop 提示），
**与点击执行无关**；`FUN_141c52700`（vtable 0x14257CEB0 槽+0x20）= 通用 UI 控件输入处理器，也不是执行点。

**实机证据（各一次，均无崩溃）**：
- 19:24:40 `FUN_1408e2270(EVT,0)`（ambition.125，id=645）→ game.log：
  `eventcommands.cpp:88 Event ambition.125 added info about event selection. selectedOption 0, human 1, playerEventId 645`
  → 事件从待决列表消失、窗口被游戏自行回收关闭。
- 19:26:06（tutorial.1340，id=642）经新工具 `tools\evt_select.py select 642 0` 同样成功：
  `eventcommands.cpp:88 ... selectedOption 0, human 1, playerEventId 642`。

**新工具** `tools\evt_select.py`：`list`（只读列待决事件）/ `auto`（单选项自动处理）/
`select <iid> <idx>`（指定选择）。全闸门（列表/层级/选项数组任一不合格即拒绝）；
真执行要求游戏暂停；动作全部写 logs/decisions.log。
**大脑 R1 已升级**：每 8 秒扫描，单选项自动处理；多选项记录待决策（选项文本解码前不自动处理）。

**遗留**：多选项事件的内容解码（选项文本/效果 → 才能做"最优决策"），下一步从
选项条目（arr[idx*0x10] 对象）与事件脚本文件（events\*.txt）双路推进。

## 2026-10-16 晚·运维纠错 + 加固（重要，避免重复踩坑）

- **venv 的 pythonw.exe 是"启动器 stub"**：`.venv\Scripts\pythonw.exe 脚本.py` 会以
  【父进程(venv stub) + 子进程(真解释器 `C:\Program Files\Python312\pythonw.exe`)】成对出现。
  **这是正常形态，不是双实例！** 误判为"双大脑"而清理会连锁杀死整链（本晚已误操作一次并恢复）。
  判断实例数时按"逻辑进程"数（按脚本名去重），不要按进程行数（stub+真身 = 2 行/脚本）。
- **加固**（2026-10-16 已写入文件）：`brain.py` 加健壮单实例互斥（WinDLL use_last_error）；
  `hai_watch.py` 加看门狗互斥（CodexStellarisWatchMutex）。
- 守护链经 WMI 直启（`Invoke-CimMethod Win32_Process Create`）可脱离调用者会话，
  避免被上层 shell 的 job 连带终止（2026-10-16 19:32 起采用）。
- 现有单套链（stub→真身）：hai_watch → brain + hai_ui；开机由启动文件夹
  `StellarisAI托管.lnk`（目标已是 venv pythonw + hai_watch.py）拉起。

## 2026-10-16 深夜·离开模式事件代答 + 事件管线全貌（实机连测定论）

**离线数据层（新建）**：
- `data\event_index.json`：9838 个事件（选项顺序/ai_chance base 与条件 modifier 数/trigger 有无/
  effects 键/immediate/after），来源 `tools\evt_index_build.py`（自研 Clausewitz 解析器，注释与字符串安全）。
- `data\loc.json`：简体中文 148,887 条（游戏 settings 为 l_simp_chinese；目录拼写是 `localisation`）。

**决策器 `tools\evt_decide.py` v1**：人工覆盖表（`data\evt_overrides.json`，schema {事件名:{idx,why}}）
> ai 基础权重最高（base；tie 取小索引）> 首个无触发条件选项 > 兜底 0；
无法安全决策（未收录 / 选项数不符）→ 返回 None，**绝不盲选**。

**大脑 R1 升级 + 三连实机验证**（每例均有 game.log 盖章）：
1. 19:42:32 托管切换 ON 抢答：`akx.9330 id=646 选项0「我们看来是永远也不会知道了。」`
   → `[19:42:32] Event akx.9330 ... selectedOption 0, human 1, playerEventId 646`
2. 19:47:40 离开模式（托管 OFF + away 标志）代答：`akx.9330 id=649`（+55s，45s 观察窗生效）
   → `[19:47:38] ... selectedOption 0, human 1, playerEventId 649`
3. （更早两例单选项：ambition.125 id=645 / tutorial.1340 id=642）

**R1 行为规约（v1.2）**：
- 托管 ON：每 8s 扫描；单选项自动答、多选项按决策器答；失败 60s 退避重试。
- 托管 OFF + 离开模式：同样处理，但仅限**停留 ≥45 秒**的事件（给在座玩家观察窗）。
- 其他情况（手动玩）：绝不动作。

**事件管线实测定论（今日四组实验）**：
- 托管 OFF：事件进入待决列表并停留（可被我们读取/代答）——全部案例一致。
- 托管 ON：新触发事件**不进入待决列表**（25s @0.5s 轮询从未出现、无 selection 日志）
  → 被 `FUN_1408e2130` 路线 A（`FUN_1402b9e80` + `FUN_14026c5d0`）直接收入 AI 队列。
- 托管 ON + 运行：游戏 AI 自行应答，日志标记 **`human -1`**
  （实测 `first_contact.50` → `selectedOption 2, human -1, playerEventId 647`）。
- ⇒ 托管模式的事件决策权天然在游戏 AI 手里；"把最优决策带进托管模式"的干净路径 =
  个人 MOD 给关键事件写 ai_chance 权重（用户已明确授权 mod/脚本，待立项）。
- 观察项：列表项 `id=648`（无窗口、名字不可读、疑似在途/队列态）——闸门拒绝触碰（保护生效）。

## 2026-10-16 深夜·审计层 + 面板实机验收 + R2 连续性修复（全部实测）

**① 审计层（新上线并实战验证）**：大脑每 2s 追读 `game.log` 增量，解析
`eventcommands.cpp:88 ... selectedOption N, human H, playerEventId X` →
`human -1` 记"[审计] 游戏AI自动决策：<事件> → 选项N「中文」"（human 1 且非本系统处理则记"手动/外部"）。
实捕获：`first_contact_critters.35 id=648 → 选项1「真是奇妙的生物。」`、
`first_contact.1(×2) id=654/655 → 选项0「真是有趣。」`、`first_contact.25 id=656 → 选项1「真是非同寻常。」`。
（另：648 之谜就此结案——它本是"首次接触小生物"自然事件，当时处于收队列中间态。）

**② 悬浮面板实机验收（窗口级）**：
- 窗口存在/可见/位置正确：(40,90)，208×282，标题 "AI 托管"，IsWindowVisible=True，截图目检样式合格。
- 『切换 开/关』按钮：命中区 ≈ y195-222（x 中心带），实测 4 次点击每次翻转托管并复原 ✓。
- 『离开模式』按钮：命中区 ≈ y236-244，实测命中 True→False→True 二连 ✓。
- F8 全局热键：**合成按键无法验证**（keyboard 库钩子收不到注入事件；独立探针证实）。
  真实物理按键不受此限——留给用户实测（远程可从 decisions.log 的 [R3] 行确认）。

**③ R2 资源定位连续性修复（含一个真 bug）**：
- 现象：AI 活跃游玩时现场值与最近存档漂移（实例：18785→~2737），R2 会"失明"到下次自动存档；
  且自动存档实为**半年一次**（2276.07.01→2277.01.01，30s 内推完 6 个月=游戏速度拉满）。
- 修复（brain.py）：a) 新增 `_brain_res.json` 连续性缓存（地址+实读值，跨重启保留）；
  b) 快速通道：每轮先用缓存地址 read_at+valid 校验；c) 双扫描失败后用"上次实读值"以 ±35%
  容差+prefer 续定位；d) 修掉"新存档撞 20s 重试护栏被吞"的 bug（`and not new_save`）。
- 验证：重启后对新存档 `autosave_2277.01.01` 容差定位成功（energy=18806 minerals=11873
  food=5144 influence=917 unity=3558），`_brain_res.json` 已写入（base=0x4E4C3A5A30 一带）。

## 2026-10-16 深夜·「AI 决策增强」MOD 上线（托管模式决策覆盖·第一弹）

- 目标：托管（human_ai）模式下事件由游戏 AI 应答；本 MOD 把"设计者偏好明确"的纯基权事件
  去随机化（赢家 factor=1000、其余候选=0），使选择确定化 = 与离线决策器同一口径。
- 批次：**38 个事件**（纯基权、最高 ≥2× 次高正值）；含条件修正的 231 个加权事件一律不碰；
  平局 98 / 差距不足 1 / 单正权 6 跳过。清单：`autopilot\data\ai_decisions_manifest.json`。
- 工具链：`_build\make_ai_decisions_mod.py`（生成）+ `_build\audit_ai_decisions.py`
  （审计，`--installed` 对已安装副本；重生成期望文本逐字节比对；当前 **38/38 PASS**）。
- 安装/启用（全自动、幂等：`_build\install_ai_decisions_mod.py`）：
  ① 拷贝至 `Documents\...\mod\ai_decisions`（重启游戏才加载）；
  ② 启动器 DB `launcher-v2.sqlite`：mods 登记 + playsets_mods.enabled=1 +
     **playsets.isActive=1** ← APWI 模组此前"DB 启用但 dlc_load 为空"的根因（播放集未激活）；
  ③ `dlc_load.json` enabled_mods 双保险。
- 顺带修正：APWI「Auto Pause When Idle」也被本次激活（此前实际未加载）。
- 生效验证（下次重启游戏后）：(a) 启动器显示两者已勾选；(b) error.log 无 duplicate event id 类错误；
  (c) 触发批次事件 + 托管 ON，审计行应显示强制选项（human -1）。
- 审计层加固：`_brain_audit.json` 持久化读取游标+去重键（跨大脑重启零断档零重复）；已补录
  19:57-58 缺失的 3 条（critters.80/critters.5/operation.1000，含中文选项文本）。

## 2026-10-17 凌晨·MOD 路线实测定论（已立项→已搁置，附完整证据）

**v2（整文件替换）机制本身 = 完全有效**（三重实锤）：
1. `error.log` 零 "already exists"（对比 v1 的满屏报错 → 同路径替换成立）；
2. 自建事件 `zcodexai.1` 可执行（`Executed #11900001`）；
3. **日志哨兵**：在替换件的 akx.9330 里插入 `immediate={log="ZCODEXAI_PROBE_v2_active"}`，
   触发后 game.log 出现 `Log effect, file: events/horizonsignal_events.txt line: 2064. ZCODEXAI_PROBE_v2_active`
   —— 精确指到我们替换文件的 2064 行 ⇒ 替换件的效果链在实机运行。

**但 ai_chance 权重不驱动游戏的事件选择器**（同批实锤）：
- 对自建事件（a:1/b:5，原生编写）连调评估器 FUN_1408e62b0 **40 次 → 40 次全返回 0**；
  对 akx.9330（a:1/b:1000，插入式）5 连 → 全 0。权重存在与否、怎么改，观察到的选择器行为不变。
- 反编译裁决：FUN_1408e62b0 → FUN_140a234f0 实为"逐选项条件筛选"（+0x4ec 门 + 条件对象虚调用），
  我们的事件两条选项该门均为 0 → 直接落回 fallback"首个合法选项"（=idx0）。
- 结论：**MOD 改 ai_chance 去随机化托管模式事件 = 此路不通**（至少对该自动应答路径）。

**收官动作**：ai_decisions 模组**已卸载**（安装副本留档 `stellaris_mods\_installed_backup_ai_decisions`；
构建/审计/安装/卸载脚本保留在 `_build\`，随时可复活）。**APWI 保留并已激活**
（注意：期间发现游荡进程会偶发改写启动器 DB 的 enabled 位——已复查修正：playsets.isActive=1、
APWI enabled=1、dlc_load 已含 APWI）。

**副产品（有价值的武器）**：
- **游戏选择器 Oracle**：可远程调用 FUN_1408e62b0(OBJ, EVT+0x10) 读"游戏会选谁"（本晚大量使用）；
- **直接代答通道**（FUN_1408e2270）依旧是唯一完全受控的事件决策执行器（全晚 8 次实机选择全部成功）；
- 日志哨兵法（替换件埋 log 效果 + 查 game.log）作为"模组文件是否真在跑"的通用验证手法。

**事件覆盖目标的下一步方向**：拦截托管模式的事件 AI 队列（route A：FUN_1408e2130 →
FUN_1402b9e80 + FUN_14026c5d0 收入的结构；今晚观察：队列中的自建测试事件在多次解暂停中
并未被游戏立即应答——其处理节奏值得后续逆向，若可读可写即成为"抢答窗口"）。

## 2026-10-17 凌晨·事件应答管线定论（拦截研究结案）

**实验矩阵（全部实机、可复现）**：
1. 托管 OFF：事件→待决窗口→完全可控（既有能力，全线验证）。
2. 托管 ON + 游戏运行：**自然事件在同一帧被 AI 秒答**（75 秒 8 连答，全 human -1，id 661-669），
   无任何可轮询的拦截窗口。
3. 托管 ON + 控制台触发：事件"空转消失"（不进待决、不秒答）；全内存扫描仅存"已触发登记表"节点
   （vtable 系 0x7FF7DDC55630，含 {事件号@+0, 实例id@s}），75 秒运行后**状态零变化**——纯记录，
   永不补处理。
4. 结构勘误：gs+0x1b0 是 **vector<u32>**（数据@+0x1b8/容量@+0x1c0/计数@+0x1c4）；
   FUN_1402b9e80 = 通用 `vector<u32>::insert`（数百调用者，此前误判为"专用队列"）；
   FUN_14026c5d0 = 按实例 id 从实例池（gs+0x498/计数 gs+0x4a4）销毁并压实。SP 实测该队列恒空
   （route A 未触发）。
5. 真实权重选项（federations3.2124，ai=20/1）运行时字段与我们插入式权重**结构相同**
   （+0x240 同一静态对象；权重不以明文 u32 存在于选项项已知偏移）——编译进条件对象，
   完整逆向属后续大工程。

**结论**：托管模式的"免钩子拦截"路线穷尽（同帧应答，无窗口）。剩余选项：
① 代码钩子（patch 选择器 FUN_1408e62b0/应答链——风险与工程量高，列为未来立项）；
② 接受"托管 ON = 游戏设计者策略 + 全程审计日志；托管 OFF（离开模式）= 我们的决策器全权代答"的双模式现状。
**手动代答通道**（FUN_1408e2270）在 gate=False 场景下的手工直调也稳定（本晚 federations3.2124 实测，审计行：
`federations3.2124 id=670 → 选项1「我们没有时间。」`）。

## 2026-10-17 凌晨·自检套件 v2 + 挂机验收（核心场景端到端）

**selftest_all.py v2（14 项检查）**：移除破坏性的"关事件窗"测试（改为只读待决事件读取）；
新增：资源连续性缓存实读校验、决策数据层（事件/本地化计数）、审计尾迹（游标+去重键）、
MOD 启用清单与启动器状态（WARN 级）。当前实机 **14/14 PASS**。

**挂机验收（5 分钟连续，托管 ON + 离开模式，2026-10-16 20:49-20:54）**：
- 零暂停卡死、零崩溃；33 条决策日志 = **25 条审计**（25 个事件被游戏 AI 应答并逐条留痕，
  含中文选项文本：first_contact / operation.1000 / ancrel.6310 系列）+ R2×4（跨自动存档连续重定位 ✓）
  + R5 推进 + 建议 1 条。
- R5 推进取证：**2277.01.01 → 2277.07.01；科技 120→121；特殊情况 3→2**（MELTING_RESEARCH_PROJECT 完成）。
- 产品核心场景（"我在工作/挂机"）端到端实机通过；恢复后：暂停 + 托管 OFF + 离开模式 ON（用户原态）。

## 2026-10-17 凌晨·"决策质量层"起点：事件参谋 v1（+用户实战样本）

**取证**：三个特殊情况全部已选方针并在推进；`LEAGUE_ARTIFACT_FOUND` 实为**已完成**
（"未完成特殊项目=0"）——当前战役无"等待玩家决策而卡住"的项。另：20:54-20:56 存在一段
**用户亲自运行托管的实战样本**（2277.07→2279.07、25+ 事件全审计、F8/按钮切换疑似被物理验证）。

**新组件 `tools\evt_analyze.py`（事件参谋 v1）**：
- 基于效果参数（含 if/hidden_effect 嵌套）的启发式评分：POS4（遗珍/科技/特质）> POS3（持续月收益/
  沉积）> POS2（特殊项目/局势/研究选项）> POS1（一次性资源/造船/领袖）；
  **方向不可判的键（add_modifier / create_fleet 等）只 +1 并标注"方向未判定"**。
- 盲区实录：精化前把 utopia.1「没得商量」的修正符打为 +3 高置信（可能实为负面）；
  精化后降级 low-conf 不再输出 → 已固化为自检回归用例。
- 全库扫描：**2691 可分析 / 341 高置信建议 / 117 处与 ai 权重分歧**
  （样例：fallen_empires_tasks.2 参谋选0(7:1) vs ai选1；federations2.10 6:3；synth.1010 6:3）。

**接线 v1（刻意保守）**：大脑审计对游戏决策（human -1）自动附署 `[参谋意见]`（仅高置信分歧才写；
**仅供参考，不自动执行**）；evt_decide（离开模式）暂不自动采用——防止把未知方向的效果当收益。
自检新增"事件参谋回归"，当前 **15/15 PASS**。

**下一步（质量层路线）**：参谋评分升级为"结合存档态势"（资源/战争/伦理/阶段）的评估；
稳定后再逐步授权离开模式自动执行。

## 2026-10-17 凌晨·参谋 v2（态势感知）+ 离开模式决策授权

**evt_analyze v2 升级**：
- `add_resource` 参数化：支持 `{资源=数量}` 与 `{resource,amount}` 两种写法；**识别负数=成本**
  （实例：ambition.216 的 7 个选项各含 `unity=-10000` → 各得 -4.4 分）。
- 递归收集 + **互斥分支去重**（同资源取绝对值最大者，避免 if/else_if 分支重复计分；
  实例：fallen_empires_tasks.2 三个奖励分支 → 正确折算为 minerals3000/energy1000/alloys500 一组）。
- **态势加权**：资源已达存储上限（如影响力 1000）→ 收益价值=0 并标注；低于警戒线 → ×1.5；
  合金/研究权重 1.1-1.3；战争状态抬高能量警戒线（上下文来自 `_brain_res.json` + 存档，TTL 60s 缓存）。

**离开模式决策授权（严格门控）**：evt_decide 优先级 = 人工覆盖 > **参谋（高置信 + 确定项净值≥3）**
> ai 基础权重 > 兜底。门控教训：首版用"赢家理由不得含任何方向未判定项"——过严（fet.2 的 +19 分
赢家只是夹带两个 +1 小项就被整体否决）；改为"**确定项净值 ≥3**"（总分减去方向未判定项贡献）后
端到端回归通过。自检 15/15 全过（含参谋三连回归：盲区降级/高置信/决策器采纳）。

## 2026-10-17 凌晨·参谋 v3：修正符方向索引（最大盲区消除）

- 新构建器 `_build\mod_index_build.py`：解析 `common\static_modifiers\*.txt` 全部 **3080 个修正符**
  → 按键语义定号（cost/upkeep/build_time 反号；资源/产出/研究/战力/幸福等正号）→
  `data\modifier_index.json`（±3 档；强正 954 / 强负 551 / 中性 899）。
- 实测样例：`megastructure_demands_rejected → -3`（pop_happiness=-0.2 实锤，验证 utopia.1 盲区）；
  `fallen_empire_gift_databanks → +3`（三类研究产出 +25%）。
- 参谋接入：add_modifier / remove_modifier 按索引定号 × **时长系数**（永久 1.0 / ≥3600 日 0.9 /
  ≥1000 日 0.7 / 短期 0.5），**互斥分支去重**（同类取最长时长）；未收录者仍回落"方向未判定 +1"。
- 附带修复：`sr_*` 战略资源入账（crisis.6200 现 11.8:0）；分数统一一位小数。
- 全库终版：**2691 可分析 / 364 高置信 / 147 处与 ai 分歧**；自检 15/15。
- 维护：游戏更新后重跑 `mod_index_build.py`；改参谋规则后重启大脑（模块缓存）。

## 2026-10-17 凌晨·★E2E 闭环验证：离开模式 × 参谋决策（实机）

**决策链全环闭合**（分析→门控→大脑执行→内核选择→审计）：

1. 载体筛选法（可复用）：对全库跑参谋 → 过滤"高置信 + 确定项净值≥3" → 原文排除
   `event_target/from./owner=/immediate/event_chain/specimen` 等作用域与副作用 → 再人工查看。
2. 实测（`origin.5745`，事件实例 id=702，2026-10-16 21:17:40）：
   - 触发后成为待决窗口（gate=True）；
   - 大脑离开模式路径在宽限（45s）后**采纳参谋建议**：
     `[R1] 多选项事件决策：origin.5745 id=702 → 选项0「这对我们的帝国颇有裨益。」`
     `依据：参谋（确定项净值 3）：+3 add_monthly_resource_mult；执行=成功`
   - game.log 盖章：`selectedOption 0, human 1, playerEventId 702`；待决清零；
     状态保持（暂停 + 托管 OFF + 离开模式 ON）。
3. 教训（已记录）：该事件选项含自定义 token（`origin_imperial_vassal_new_overlord_eventchain_1`），
   实为引用 `event_target:new_subject_target` 的 scripted_effect——独立触发时因目标未定义
   **优雅失败**（error.log: `Undefined event target`，无崩溃、无状态污染）。
   **载体选择需追加一步：对自定义 token 查 `common\scripted_effects` 定义。**
   对参谋评分无影响（未知 token 计 0）。

## 2026-10-17 凌晨·决策档案工具 + 参谋 v4（阶段维度）

- 新工具 `tools\decision_report.py`：decisions.log 汇总为可读报告——分类计数、游戏决策总数、
  **参谋异议率**、我方决策/参谋采纳数、分歧明细（`--diff`）。首跑：556 行日志 → 游戏决策 45 /
  我方决策 4（含参谋采纳 1）。托管实战积累后可直接看质量趋势。
- 参谋 v4：**游戏阶段维度**——年份 <2250：科研收益 ×1.2、合金 ×0.9；≥2350 反之；mid=1.0。
  年份取自最近存档文件名；实测三档因子生效（crisis.6200 合金项：4.68 / 5.2 / 6.24）。
- 坑与纪律：`load_context` 的 TTL 缓存会掩盖探针注入的合成上下文——**验证真实上下文前必须清缓存**
  （本轮虚惊：探针显示 year=2360 实为缓存泄漏；实存档仍为 2279）。
- 自检 15/15；大脑已重启加载 v4。

## 2026-10-17 凌晨·托管实战采样 + 副署路径 E2E 验证

- **6 分钟托管采样**：30 个事件被应答；参谋与游戏 **0 分歧**（抽查 critters.85/5/1、
  first_contact.1 等：全部"参谋同意"或低置信被压制）——副署的噪音控制符合设计意图。
- **副署路径注入测试**（向 game.log 追加合成审计行，不触碰游戏状态）：
  - 分歧案例（fet.2，游戏选1/参谋建议0）→ `[审计]…` + `[参谋意见] …建议选项0（+4 give_technology…），游戏选了1` ✓
  - 同意案例（first_contact.1）→ 仅审计、无副署 ✓（不刷屏）
  - **"托管执行 + 参谋逐条校对"管线 E2E 验证完成。**
- 决策档案累计（608 行）：游戏决策 77 / 参谋异议 1（1%，即注入样例）/ 我方决策 6（参谋采纳 1）。
- 纪律备注：注入合成的 playerEventId（999001/999002）已永久占审计去重键，属测试数据。

## 2026-10-17 凌晨·★冻结缺口修复：离开模式 × 托管 OFF 的事件暂停

**缺口**：离开模式下若托管为 OFF，事件自动暂停被 R1 应答后**无人恢复运行**（R4 的自动恢复
要求托管 ON）→ 游戏永久冻结，"挂机不中断"承诺破功。

**修复**：R1 处理完事件（单选项/多选项任一成功路径）后调用 `_away_resume_if_needed()`：
离开模式 + 托管 OFF + 仍暂停 → 自动 `game_paused false` 并记日志（托管 ON 时归 R4 管辖，不越权）。

**实测**（tutorial.1340 零效果事件，21:31）：触发 → 54s（45s 宽限+扫描）→ 单选项自动应答 →
**自动恢复运行（暂停=0）**；日志两连行如上。游戏保持运行（离开模式语义：让时间继续流动；
多选项未知事件仍保守冻结等待用户）。

## 2026-10-17 凌晨·值守实战（耐力观察）+ 宽限期调优

**值守循环自证工作**（离开模式 + 托管 OFF，全程实机）：
- `precursor.304`：21:32:14 弹出并暂停 → 21:33:10 自动应答 → 21:33:13 自动恢复运行。
- `aianom.5`：21:33:39 弹出 → 21:34:50 自动应答 → 恢复运行；当前 暂停=0、零待决。
- 期间（虚惊排查）：我在 45s 宽限期内查状态误判为"卡住"，复检即按节奏完成——宽限窗口的
  存在感实锤。

**效率调优**：离开模式事件宽限 **45s → 15s**（`AWAY_GRACE_EVENT` 常量）。
理由：高频事件时段实测"39s 运行 / 55s 暂停"的占空比太差；离开模式下用户不在座，
观察窗可从 45s 缩到 15s（仍给巧合在座的玩家留反应时间；手机重新调只需改常量）。

**新认识（审计语义）**：`[审计] 游戏AI自动决策` 流 = **全局事件日志**（含其他帝国的 AI 决策；
game.log 的该行不带国家字段，源头无法过滤）。用户自家事件带待决窗口与 R1 行可辨识；
decision_report 的统计口径应按"全局"理解。

## 2026-10-16 深夜·★内存决策改写突破（命令管线全解锁 + rw88 钩子）

- 选择命令类（vtable 0x1423ABDD8）字段：+0x20 事件模板id（/100000 命名空间、%100000 序号）、
  +0x24 选项序号、+0x28 playerEventId（=待决列表 iid）、+0x2c human（-1=AI自动选择 / 1=我方注入通道）、
  +0x30 事件键串。dismiss 类 vtable 0x1423ABE90。
- 流水线：构建 → exec `FUN_14099cd60`（+0x40 槽，校验 `FUN_140a23740`；失败静默）→
  派发 `FUN_1405f88a0`（130+ 调用者；成功入管线 `FUN_141a59590`，失败销毁）→
  **汇聚点 `FUN_14099c090`（+0x48 槽）**：写 game.log :88 行（selectedOption/human/playerEventId）
  → 执行效果 `FUN_1408e6b70`→`FUN_140a22a10`（参数直接取 cmd+0x24）→ 清理 `FUN_14026c070`。
- 实证：rw88 观察钩子（log88 入口）计数与 :88 日志行 **1:1**（两窗口 2/2、5/5）；human=-1 = 自然流；
  我方注入走 sel→exec，校验不过则 clone=0 不派发（死点实测：sel+1/exec+1/clone+0）。
- **rw88 改写钩子已装**（tools\hook_rw88.py；手写 x64 + capstone 校验 + 入口 14B detour；
  武装表 {eventId→option}，仅 human==-1 时改写 cmd+0x24）：日志/效果/清理全链路一致采用新值。
  无匹配时零行为变化；游戏重启即消失（需重装）。
- 多选项注入失败根因：R1 兜底盲选**触发器阻断**的选项（action.97=原版银河市场提名，选项按 is_megacorp
  互斥）→ 游戏校验静默拒绝，每 78s 重试永不成功。**正解=托管脉冲**：托管 ON 数秒让游戏 AI 用合法
  选项应答（实测 6 秒答完 3 个积压），rw88 改写在同一瞬间把决策换成我方的。
- 探针清单（hook_proto / hook_rw88 的 tag）：sel、exec、log88(=rw88 前身)、ctor、clone、disp、dq、
  c150、c4590(热函数 469/40s，选项评估类待查)、e340、d1b0、cfb0、rw88。

- **改写实测（22:15:56）**：发射零效果探针事件 zcodexai.1(847, 2选项) → 武装 847→0 → 托管脉冲
  4 秒内游戏 AI 应答：ring 记录 pre=1/human=-1/rwn=1/post=0；game.log :88 行 = selectedOption 0,
  human -1, playerEventId 847 —— **AI 原选择 1 在效果执行前被内存改写为 0，日志/效果/清理全链路
  采用改写值。阶段 2（内存级决策控制）通关。**

## 2026-10-16 深夜·v1.2 值守升级：探测天梯 + 托管武装 + 8 槽改写表（实测）

- **探测天梯（多选项事件正解，E2E 实证）**：离开模式下事件 15 秒观察窗后 → 自动短暂暂停 →
  按参谋偏好顺序逐项注入（人工覆盖 > 参谋 > ai权重 > 无触发优先 > 序号），
  **游戏侧触发器校验天然筛掉非法项**（被拒静默，第一个被接受者即最优合法解）→ 自动恢复运行。
  实测：action.97（选项0 被触发器禁）→「跳过被拒项 [0]」→ 选项1 消费成功；zcodexai.1 → 选项0 成功；
  两轮均零人工干预（decisions.log 22:26 / 22:36）。
- **托管武装（rw88 升级 8 槽，state ver=2）**：大脑离开模式下对多选项事件**先武装**
  {flag,eventId,option}×8 槽表；游戏 AI 一应答（human=-1），钩子在效果执行前改写选择为参谋决策；
  消费后自动解除并确认（[R1] 改写生效确认：原选N → 已改写为M）。实测武装：zcodexai.1 id=910。
- **决策语义升级**：未收录事件不再冻结——按盲探序注入（游戏侧校验兜底）；目标=永不卡事件。
- **竞速发现（留设计）**：托管 ON 时 AI 对积压事件可数秒内答完（22:08 一次清 5 个），逐事件武装有竞速；
  后续可做「按事件模板名预武装」（hook 改匹配 cmd+0x20）。
- 变更集：brain.py v1.2（_inject_with_pause/_ladder/_arm_best/_maintain_arms/_stuck_fallback；托管 ON 3 秒快扫）、
  evt_decide.candidates()/option_has_trigger()、hook_rw88 8 槽、data/event_index.json 补录 zcodexai.1；
  selftest 15/15；大脑已重启加载。当前状态：游戏运行中、托管 OFF、离开模式 ON、待决 0。

## 2026-10-16 深夜·v1.3 按名预武装（模板匹配 + 归属校验）实测

- **动机**：托管 ON 时游戏 AI 对事件应答时快时慢（22:08 数秒清 5 个），逐实例武装有竞速；
  且必须**绝不误改他国 AI 的选择**。
- **实现**：hook_rw88 v3（state ver=3，24 槽）：槽 {flag,keyType,key,option}；
  keyType=1 → 匹配 cmd+0x20（事件模板 id）＝按家族预武装（新实例全部覆盖）；
  **模板命中后做归属校验**：cmd+0x28 必须在我方待决列表（gs+0x180）中，否则拒绝并计 blocked。
  模板 id 解析：事件注册表（DAT_143152ca8）**双层解引用** walk（def=**(表项)；504,224 个 def 全扫约 2.5 秒，
  结果缓存到 data/evt_tpl_map.json）。已验证 zcodexai.1 = 模板 11900001（与钩子实测记录一致）。
- **实测（22:45）**：发射 zcodexai.1 → [R1] 已武装(按名)：zcodexai.1 模板11900001 → 选项0 +
  武装表刷新 → 托管 ON → 游戏 AI 应答（human=-1）→ **钩子改写计数器 +1**（rwn=1，归属拦截=0）
  → 事件消费成功。本次 AI 原选=目标(0)，数值级 diff 案例此前已证（22:15: pre=1→post=0）。
- 脑 v1.3 新增：_decide_arm/_tpl_of/_sync_standing；家族武装 1 小时未见失效；表变化才重写（set_slots）。

## 2026-10-16 深夜·长名事件读取盲区修复（MSVC std::string SSO）+ 面板状态行

- **根因**：事件名是 MSVC std::string（{内联16B|指针, size@+0x10, cap@+0x18}）；名字 ≥16 字符时 +0x20
  存的是**堆指针**，旧盲读拿到指针字节 → 解码失败 → gate=False → 这类事件（astral_situation.20 /
  grand_archive.6010 等长名）在离开模式下**永不处理**（实测挂 30 分钟+）。
- **修复**（evt_select.rname）：按 size 判定走内联/指针路径 + memcpy 部分读取防护；实测
  grand_archive.6010 立即变为 name ✓ / gate=True；zcodexai.1（短名）不受影响。
- **面板 hai_ui.py 增强**：新增「引擎」状态行（武装 N · 改写 M · 拦截 B · 待决 K，每 5 秒直读钩子/待决），
  互斥锁改用 use_last_error 规范写法；面板重启后自检确认可见。
- **值守质量审计（v1.2 后）**：天梯 8/8 成功、0 失败；单选项 7 成功；卡死 0；期间全部事件 100% 自动处理。

## 2026-10-16 深夜·R6 健康心跳 + 钩子入口字节级自愈 + 覆盖测试

- **R6 健康心跳**（brain，每 10 分钟一行）：钩子在线性（入口 FF25 校验）/武装/改写/拦截/待决 +
  本进程统计（天梯N 单选项N 失败N）。日志出现 [R6] 行即为系统自证在运转。
- **_ensure_rw88 三级自愈**：state(base+ver) → 入口 14B=FF25 → 跳转目标==state.cave；
  任一级不符 → revert(幂等)+install 重装（冷却 60s 防抖）；极端兜底（state 丢失但入口仍被占用）
  会先写回原序言再装。覆盖：游戏重启 / 外部还原 / 旧版本残留。
- **覆盖测试（22:53-54）**：一次性发射 3 个不同家族事件（bio.300 三选项新家族 / fircon.1450 双选项 /
  observation.103 单选项）→ 30 秒内全部自动处理（天梯 2 + 单选项 1），0 失败，全部自动恢复运行。
- **模板学习缓存复合增长**：{zcodexai.1:11900001, fircon.1410:5001410, bio.300:1700300, fircon.1450:5001450}
  （每见一个新家族自动学会并写入 data/evt_tpl_map.json）；武装表 2 条按名规则在线。

## 2026-10-16 深夜·改写审计闭环（环形缓冲）+ 5 连 bug 修复 + 数值级改写终证

- **改写环形缓冲（hook v4, state ver=4）**：每次改写写 8 槽环缓（evid/pre/post/tpl）+ 写指针
  （scratch+0x1C8 / 0x200）；大脑每扫描排空并逐条落 decisions.log——改写审计「不漏报、不被
  全局选择流冲掉」。重启后首次排空回读最近 8 条，审计不断档。
- **本轮抓到并修的 5 个隐蔽 bug**：① brain 模块级缺 import json（排空块 NameError 被
  except pass 吞掉 → 静默失效）；② 缓冲读取偏移错（应在 +0x200，非 +0x1C8+8）；
  ③④⑤ 三段新机器码寄存器编码错（mov edx 缺 REX.B、lea 多设 REX.X、lock inc 缺 REX.B）——
  全部由 capstone 反汇编目检抓出。
- **数值级改写终证（23:08-23:10）**：zcodexai.1 id=1008：游戏 AI 原选 1（human=-1）→ 钩子改写
  → 游戏 :88 行记 0 → [R1] 改写生效：id=1008 模板11900001 游戏AI原选1 → 已改写为0（大脑侧
  确认行）。发射/武装/应答/改写/双侧审计，全链贯通。
- 工具：soak_report.py（挂机质量报告器：ladder/single/武装/改写/异常/R6 汇总）。

## 2026-10-16 深夜·自愈实测通过 + 武装规则持久化 + 自发结算流发现

- **自愈实测（23:14）**：手动还原钩子入口 → 大脑 8 秒内检测（入口 FF25 校验失败）→
  revert+install 自动重装 → 入口恢复跳转 → 武装表重建机制点火（日志：rw88 改写钩子已安装（或重装））。
- **武装规则持久化（data/evt_standing.json）**：规则表随变更落盘；大脑重启/重装后**启动同秒**从文件
  重建武装表（实测：重启后 0 秒日志「武装表刷新：3 条按名规则（重建）」，钩子槽位即刻就位）。
  同时修复「重装后武装丢失」（_last_rules 失效标记）。
- **自发结算流发现（23:17）**：first_contact_critters.35 id=1041 在**托管 OFF** 时被以 human=-1 自动
  应答（游戏自身对部分事件自主结算）——按名武装规则**兜住了这类选择**（归属校验通过、改写执行、
  决策保持我方偏好）。结论：武装改写覆盖的不只是托管 AI，还包括游戏的自发结算流。
- 值守窗（23:14-23:18）：天梯 6/0、单选项 6/0、0 异常；其间系统横跨 16+ 个事件家族全自动运转
  （bio/nomads/astral_rift/strange_worlds/preftl/action/espionage/leviathans/grand_archive…）。
- 备注：重启后环缓回读会重发最近 ≤8 条确认（可能产生一次重复日志行，属预期行为）。

## 2026-10-16 深夜·离开模式(托管OFF)空闲暂停自愈（发展不冻结）

- **缺口**：托管 OFF 时，游戏被空闲暂停（auto_pause_when_idle 等）后，只有"事件处理"路径会顺带恢复；
  安静时段游戏实际冻结——用户在外时帝国时间不流动 = 没有"发展"。
- **修复（R4 扩展）**：away + 托管OFF + 暂停 ≥15 秒且无待决事件 → 自动恢复运行；
  事件滞留 ≥120 秒也强制恢复（卡片事件不冻结时间；活跃天梯流程不受干扰）。
- **确定性实测（23:21）**：手动暂停 → 16 秒后自动恢复（日志原文：
  [R4] 离开模式(托管OFF)：暂停 16 秒（无待决事件），已自动继续运行（ok=True）；paused=0）。
- 至此离开模式三态全覆盖不冻结：托管ON（R4 90s）/ 托管OFF（R4-off 15s + R1 事件流）/ 事件处理中（R1 自恢复）。

## 2026-10-16 深夜·R4-off 调优（15→6 秒）+ 自然事件改写实证（1069）

- **调优依据（实测数据）**：15 秒阈值下 159 秒窗口运行占比仅 37%（每个空闲暂停周期白丢 ~20 秒）；
  阈值降为 6 秒后（仍高于 R1 单步注入暂停时长）：安静时段连续运行 146 秒+，运行占比回升至 ~85%+；
  事件宽限期内的暂停属设计内行为（先等 15 秒不抢答，R1 处理完自恢复）。
- **自然事件改写实证（23:26:35）**：id=1069（模板 4800035 = first_contact_critters.35 家族，游戏自主结算
  human=-1 原选 2）→ 按名武装改写为 1（我方偏好解）。日志原文：
  [R1] 改写生效：id=1069 模板4800035 游戏AI原选2 → 已改写为1
  这是"游戏默认决定被替换为参谋优选"的真实自然案例（非测试注入）。
- 附：23:22-23:28 期间系统横跨 operation/bio/grand_archive/preftl/observation/paragon/critters 等
  家族全自动处理十余个事件，0 失败；R6 心跳：武装 5 条、拦截 0。

## 2026-10-16 深夜·回归摘要器（digest.py）+ 家族学习里程碑

- 新增 \python tools\digest.py [--hours N]\：一键把时段内的自动处理数/失败（含最近一次失败时间）/
  改写记录/帝国近况/资源/健康/已学习家族浓缩成一页，用户回归时零理解成本。
- 里程碑：事件家族模板缓存已达 **25 个**（从 7 → 25，全自动学习）；当前武装 5 个家族。

## 2026-10-16 深夜·面板(窗口)崩溃自愈 + 用户关闭语义
- hai_watch 增强：面板中途异常消失（非用户主动关闭）→ 自动补拉（实测：崩溃后 12 秒内 re-launch）；
  用户点 ✕ 关闭 → 写 _hai_ui_closed.flag，本局不再弹（实测 0 重弹）；flag 清除后自动补拉（实测通过）；
  游戏退出时自动清理 flag。
- 三条路径均实测：崩溃→补拉 ✓ / 用户关→不弹 ✓ / flag 清理→补拉 ✓。面板进程换新代码（含引擎状态行）。

## 2026-10-16 深夜·自愈链最后的边界 bug（复合异常态）+ 修复与验证

- **模拟发现**：篡改 state.base（模拟重启后陈旧）时，若入口仍带补丁（复合异常态）：
  旧 revert 因"重启假设"跳过还原 → 旧 install 因"入口非原始"拒绝 → 大脑误报成功、state 不修、
  工具读不到计数器（静默畸态）。
- **修复**：revert 改为"入口字节判定"（非原始即还原，不再依赖 base 比对）；
  brain._ensure_rw88 改为检查 install 返回码（非 0 即走"写回原序言+重试"兜底），失败如实记录不误报。
- **验证（23:36-37）**：二次模拟 → 完整自愈链：revert(还原) → install(重装, 新 cave) → state.base 修正
  → 武装 7 条重建 → hook read / selftest 恢复（16/16，钩子在线 武装 7 条）。
  真实游戏重启所呈现的"state 陈旧"形态已被实测覆盖。

## 2026-10-16 深夜·自愈分支全集验证（state 文件被删）+ 已知限界记录

- **分支 3 实测（23:38）**：直接删除 _hook_state_rw88.json（模拟工具目录被清理；入口带补丁）→
  兜底链自动完成：直写原序言 → install → **state 文件重建（base/ver 正确）** → 武装 7 条重建 →
  read/selftest 全恢复。日志：[R1] rw88 改写钩子已安装（或重装）。
- **自愈矩阵（全部有实测）**：①入口被还原 → 重装；②state 陈旧+入口带补丁 → revert/install 修复链；
  ③state 文件被删 → 兜底直写+重建；④面板崩溃 → 补拉；⑤面板用户关 → 不弹；⑥进程死亡 → 看门狗拉活。
- **已知限界（记录）**：按名武装目标索引来自脚本选项表；若某实例被运行时过滤（实机选项数少于脚本），
  改写目标理论上可能越界——游戏 log88/效果器自带边界检查（优雅跳过效果、事件正常消费，不崩溃），
  且审计流可见。需要更强保障时可做 in-hook 计数校验（注册表查找，复杂度高，暂缓）。

## 2026-10-16 深夜·审计器两处修复（轮转重开 + 分块切断）

- 修复 1（轮转去重键）：game.log 被游戏重开/轮转时（size < offset），原实现只重置偏移不清去重键——
  新会话的事件 id 从低位重用，开局事件会因命中旧键而漏审计。现在轮转即清 audit_seen 并存盘。
- 修复 2（分块边界切断）：64KB 分块若在行中间截断，原实现推进整块导致被切断的行永不匹配（丢审计）。
  现在只推进到最后一个完整行，行尾残留留待下轮拼接；单行超缓冲时硬吞防卡死。
- 验证：重启后审计恢复（近 80 行含审计 41 行）、自然改写再现（id=1128 模板5300005）、
  R6 报 8 条武装、selftest 16/16。
- 附带观察：R5 建议行自主报出「科研疑似停滞（科技数 159 未增长）」——托管 OFF 不发展的问题被系统主动警示
  （面板/digest 中亦有对应提示）。

## 2026-10-16 深夜·「武装目标越界」限界关闭（推导 + 加固）
- 推导澄清：candidates() 每个候选经 0 <= i < n 守卫（n=实机选项数=def+0x5f4，且 def 为注册表共享模板），
  而 log88 的边界检查用的正是同一个值——**目标索引越界由构造保证不可能**。
- 残余边角：持久化规则可能在游戏/模组版本变化后过期（选项数变小）。已加固：家族实例出现时即校验
  「原目标 < 现选项数」，不满足则自动撤销该家族武装并记日志（[R1] 武装撤销：…）。
- 至此越界限界条目关闭（无开放风险项）。

## 2026-10-17 凌晨·★真实整机重启后的全自动恢复（实测，非模拟）

- **事件**：00:24 机器/会话重启（看门狗 00:24:04 全新启动、游戏进程消失）；用户 00:26:5x 重新打开游戏。
- **全自动恢复链（零人工）**：
  · 看门狗经开机自启项恢复运行（00:24:04）；
  · 大脑被看门狗拉起（00:24:04）；游戏启动后自动重连（00:26:56，pid=8856 / base=0x7FF6C5560000，
    旧进程为 32496 / 0x7FF7DB910000）；
  · **rw88 钩子被自动重装进全新游戏进程**（00:27:20「[R1] rw88 改写钩子已安装（或重装）」，
    state.base 自动校正）；
  · 武装规则从持久化恢复（10 条家族规则即刻在线）；
  · 面板由看门狗重新拉起（00:26:53），窗口可见；
  · 新会话已在正常工作（钩子计数 改写=1、拦截=0；selftest 16/16）。
- 结论：「真实重启」验证项以实机证据关闭——自愈/持久化/看门狗/面板补拉全链条在真实世界事件中
  自证。此前所有模拟分支（入口还原/state 陈旧/state 删除/面板崩溃）与本次真实重启互为印证。
