# Stellaris AI Steward · 群星 AI 托管

> **EN**: A single-player Stellaris stewardship tool — auto-resolve events with a best-legal-choice
> engine, one-tap AI autopilot, a floating in-game panel, and a full audit trail.
> All operations are **runtime memory reads/writes on the running game process only**;
> no game file is ever modified, and everything reverts when the game exits.
>
> **中文**：单机《群星》辅助值守工具——事件自动按"合法最优解"处理、一键托管、游戏内悬浮面板、全程审计。
> 所有操作均为对**运行中游戏进程的临时内存读写**，不修改任何游戏文件，游戏退出即全部还原。

---

## ✨ 功能 / Features

- **事件全自动**：单选项直接处理；多选项按"参谋偏好"逐个探测，取游戏接受的第一个（= 合法且最优）；
- **一键托管**：面板按钮 / `F8` 全局热键，切换游戏自带的 `human_ai` 托管（帝国由游戏 AI 自动发展）；
- **决策改写**：已学习的多选项事件家族自动"武装"——游戏内任何来源的选择（AI 托管、游戏自发结算）
  都会被替换为参谋决策；归属校验保证**绝不触碰其他帝国**；
- **悬浮面板**：随游戏自动出现，实时显示 `武装 / 改写 / 归属拦截 / 待决` 状态；可拖动，可关闭；
- **审计与自愈**：每 10 分钟健康心跳；钩子 / 面板 / 进程全部自动恢复；一切决策双侧留痕。

## ⚙️ 安装 / Install

**要求**：Windows + Python 3.10+ + **Stellaris 4.5.2**

1. 安装 [Python](https://www.python.org/downloads/)（务必勾选 *Add Python to PATH*）；
2. 双击 **`install.bat`**：自动创建虚拟环境、安装依赖、可选开机自启、冒烟自检；
3. 正常启动游戏 → 面板自动出现，值守开始。**不需要**把任何文件放进游戏目录。

> **版本说明**：本工具针对 Stellaris **4.5.2 (Cygnus)** 的内存布局制作，内置版本指纹校验——
> 游戏版本不符时会**拒绝运行**（防止改错地址导致游戏崩溃）。适配新版本属于逆向工作，
> 可参考 `docs/技术笔记` 与 `tools/ghidra_scripts`（高级用户）。

## 🎛 使用 / Usage

| 控件 | 作用 |
|---|---|
| 「切换 开 / 关」/ `F8` | **托管**：开 = 游戏 AI 替你发展帝国（决策受本工具把关）；关 = 帝国操作留给你 |
| 「离开模式」 | 人不在时打开：事件全自动应答 + 时间防冻结 |
| 引擎状态行 | 实时读数：`武装 N 条 · 改写 M 次 · 归属拦截 B · 待决 K` |

**速查**：上班挂机 = 两个开关都开；回来自己玩 = 两个都关；查账 = 看面板状态行或跑一下 `/tools/digest.py`。

## 🔧 工具 / Tools

```
python tools\selftest_all.py      # 全系统自检（16 项）
python tools\digest.py            # 回归摘要：这段时间发生了什么
python tools\soak_report.py --since "YYYY-MM-DD HH:MM"   # 时段质量报告
python tools\hook_rw88.py read    # 内存钩子状态（武装表 / 改写数 / 归属拦截）
```

日志：`logs\decisions.log`（`[R1]` 事件处理 · `[R6]` 健康心跳 · `[审计]` 决策流水）。

## 📦 可选增强（推荐）

`data/` 默认不含任何游戏数据（**版权考虑**，仓库里不携带任何游戏文件/文本）。
想获得更聪明的决策（事件权重、选项名字、修正符参数），可自行从**本机游戏安装**生成：
见 `data/README.md`（脚本顶部填你的游戏路径即可）。

## ⚠️ 免责声明 / Disclaimer

1. **仅限单人游戏使用**；请勿在联机对局中使用（联机使用后果自负）。
2. 本工具**不修改任何游戏文件**：所有操作均为对运行中进程的临时内存读写，游戏重启即完全还原。
3. 本工具不含任何游戏文件、美术资源或本地化文本，**不提供游戏本体下载**；
   Stellaris® 及相关内容版权归 Paradox Interactive 所有。本项目为社区个人作品，
   **与 Paradox Interactive 无任何关联，亦未获其背书**。
4. 使用前请**备份存档**；因使用本工具造成的任何存档或游戏问题，由使用者自行承担。
5. 本项目仅供**个人单机自动化与研究学习**用途。

> 1. Single-player use only — do not use in multiplayer.
> 2. Modifies nothing on disk: runtime memory only, fully reverted when the game exits.
> 3. Contains no game files, art, or localization text. Not affiliated with or endorsed by Paradox Interactive.
> 4. Back up your saves; use at your own risk.
> 5. For personal single-player automation and educational/research purposes only.

## 📁 仓库结构 / Layout

```
├── install.bat / uninstall.bat        # 双击安装 / 卸载
├── start_panel.bat / start_watchdog.bat        # 手动启动
├── tools/                             # 运行核心：值守大脑 / 悬浮面板 / 内存钩子 / 决策引擎 / 自检工具
│   └── ghidra_scripts/                # Ghidra 逆向脚本（用于版本适配，可选）
├── docs/                              # 操作手册 + 技术笔记（逆向分析记录）
└── data/                              # 可选增强数据（默认空）
```

## 🗺 路线 / Roadmap

- [ ] 适配后续游戏版本（需重新定位函数地址）
- [ ] 面板多语言（中/英）
- [ ] 更多决策维度（科技选择托管等）

## License

MIT（见 `LICENSE`）。本仓库不含任何 Paradox Interactive 版权内容。
