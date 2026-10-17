# v0.9.0 — 2026-10-18

## 核心

- 事件自动处理（合法最优解 + 探测天梯 + 武装改写）
- 游戏内悬浮面板 / F8 托管 / F9 战争模式
- 运行时内存操作，不改游戏文件；游戏退出即还原
- 审计与自愈：决策日志、健康心跳、钩子/面板/进程自动恢复

## 战争组件（可选）

- 战时 aggressive、同星系自动追击、首都集中回防
- 弱舰队 `< weak_fleet_power` 不参与自动追击/推进
- 经济政策：军事/民用/平衡（动态阈值）
- 附属国：conserve 保存舰队、改约/独立就绪判断
- 探索接管 `.28`（`survey-all`，作弊级）
- 结构救济 `.27`（工厂世界加 `building_factory_3`，作弊级）

## 验证

- 实机验收：v0.6–v0.8 事件/姿态/经济/conserve 通过
- 当前 v0.9.0 新增 `.28` 探索接管，需重启加载
- 仅限单机；不修改游戏安装目录；不提供游戏本体

## 快速开始

1. 安装 Python 3.10+
2. 双击 `install.bat`
3. 启动游戏，面板自动出现
4. 可选：安装战争组件 `python tools\install_war_mod.py install`

完整说明见 `README.md` / `README_EN.md` / `docs/WAR_COMPONENT.md` / `docs/STRATEGY_AUDIT.md`。
