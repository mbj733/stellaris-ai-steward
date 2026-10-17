# Stellaris AI Steward

> **English** · [🇨🇳 简体中文](README.md)

> 🌐 **Landing page**: <https://mbj733.github.io/stellaris-ai-steward/>

[![Release](https://img.shields.io/github/v/release/mbj733/stellaris-ai-steward)](https://github.com/mbj733/stellaris-ai-steward/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/mbj733/stellaris-ai-steward/total)](https://github.com/mbj733/stellaris-ai-steward/releases)
[![Stars](https://img.shields.io/github/stars/mbj733/stellaris-ai-steward)](https://github.com/mbj733/stellaris-ai-steward)

![AI Steward panel](docs/screenshots/hero_zh.png)

A single-player Stellaris stewardship tool — auto-resolve events with a best-legal-choice engine,
one-tap AI autopilot, a floating in-game panel (with a 中/EN language toggle), and a full audit trail.
All operations are **runtime memory reads/writes on the running game process only**;
no game file is ever modified, and everything reverts when the game exits.

---

## ⬇️ Download

- **Latest release**: <https://github.com/mbj733/stellaris-ai-steward/releases/latest>
- Download `stellaris-ai-steward-vX.Y.Z.zip`, unzip, and run `install.bat`
- Windows + Python 3.10+; nothing needs to be copied into the game folder

## ✨ Features

- **Automatic event resolution** — single-option events are handled instantly; multi-option events are
  probed in preference order and the *first choice accepted by the game* is taken (i.e., the best legal choice);
- **One-tap autopilot** — panel button / `F8` global hotkey toggles the game's built-in `human_ai`
  autopilot (your empire develops automatically under AI control);
- **Decision rewriting** — learned multi-option event families are "armed" per family; any selection
  from any source (AI autopilot, the game's own auto-resolution) is replaced with the steward's choice
  at execution time. An ownership guard ensures **other empires are never touched**;
- **Floating panel** — appears automatically with the game; shows live `armed / rewrites / blocked / pending`
  counters; draggable, closable, and toggleable between Chinese and English;
- **Audit & self-healing** — 10-minute health heartbeats; hooks, panel and processes all recover
  automatically; every decision is logged on both the game side and the tool side.

## ⚙️ Install

**Requirements**: Windows + Python 3.10+ + **Stellaris 4.5.2**

1. Install [Python](https://www.python.org/downloads/) (check *Add Python to PATH*);
2. Double-click **`install.bat`** — it creates a venv, installs dependencies, optionally adds a
   startup entry, and runs a smoke self-test;
3. Launch the game normally — the panel appears by itself. **Nothing needs to be copied into the
   game folder.**

> **Version note**: built against Stellaris **4.5.2 (Cygnus)** memory layout, with a version
> fingerprint guard — the tool **refuses to run** on a different game build (to avoid corrupting
> memory). Porting to a new version is a reverse-engineering task; see `docs/` and
> `tools/ghidra_scripts/` (advanced users).

## 🎛 Usage

| Control | What it does |
|---|---|
| 「Toggle ON / OFF」/ `F8` | **Autopilot**: ON = the game AI develops your empire (decisions policed by this tool); OFF = you keep full manual control |
| 「Away mode」 | Turn on when you step away: events get resolved automatically and the game clock never freezes |
| Engine line | Live counters: `armed N · rewrites M · blocked B · pending K` |

**Quick guide**: idling at work = turn both switches ON; playing yourself = turn both OFF;
checking = look at the engine line or run `python tools\digest.py`.

## 🔧 Tools

```
python tools\selftest_all.py      # full system self-test (16 checks)
python tools\digest.py            # digest: what happened while you were away
python tools\soak_report.py --since "YYYY-MM-DD HH:MM"   # period quality report
python tools\hook_rw88.py read    # memory hook status (armed / rewrites / blocked)
python tools\war_audit.py         # war staff: side power / exhaustion / local balance
python tools\strategy_audit.py    # research / traditions / policies / economy audit
python tools\war_mode.py audit    # war staff (read-only)
python tools\war_mode.py auto     # apply the staff recommendation (no auto-push if enemy collapsed)
python tools\strategy_engine.py status   # economic mode / consumer goods / alloys net
python tools\strategy_engine.py apply    # switch military/civilian/balanced economy
python tools\strategy_engine.py on|off   # allow/deny brain auto-apply
python tools\strategy_engine.py research physics   # research audit (dry-run)
python tools\strategy_engine.py research physics --yes  # oracle mode: grant the top tech (cheat)
```

Logs: `logs\decisions.log` (`[R1]` event handling · `[R6]` health heartbeat · `[审计]` decision stream).

> ⭐ If this saves you time, a **Star** is the most direct way to help; please open an Issue for install/compatibility problems.

## 📦 Optional enhancement (recommended)

`data/` ships empty on purpose (**copyright** — the repository carries no game data).
For smarter decisions (event weights, option names, modifier parameters), generate the indexes
yourself from your own game installation — see `data/README.md`.

## ⚔ Optional: War Component

The core tool writes nothing to disk. The war component is an **optional** local mod
(installed under `Documents\Paradox Interactive\Stellaris\mod`, never into the game folder,
removable with one command):

```bat
:: install, then restart the game once
python tools\install_war_mod.py install
:: wars / fleet stances / attack flag
python tools\war_mode.py status
:: attack mode: idle fleets push to the nearest enemy system
python tools\war_mode.py on
:: defend mode (default)
python tools\war_mode.py off
:: uninstall
python tools\install_war_mod.py remove
```

The panel also has a "War mode" button (`F9`). **Defend mode is automatic** (local auto-engage +
idle fleets reinforce the nearest threatened owned system); attack mode is manual. See
`docs/WAR_COMPONENT.md` for details and limits.

## ⚠️ Disclaimer

1. **Single-player use only** — do not use in multiplayer sessions.
2. The core tool modifies nothing on disk: runtime memory only, fully reverted when the game exits.
   The optional war component writes a local mod under your Documents folder (removable), never
   into the game installation.
3. Contains no game files, art, or localization text; **does not provide the game itself**.
   Stellaris® and related content are the property of Paradox Interactive.
   This is a community project, **not affiliated with or endorsed by Paradox Interactive**.
4. Back up your saves; any save or game issue caused by using this tool is your own responsibility.
5. For personal single-player automation and educational/research purposes only.

## 📁 Layout

```
├── install.bat / uninstall.bat        # double-click install / uninstall
├── start_panel.bat / start_watchdog.bat
├── tools/                             # runtime core: brain / panel / memory hook / decision engine / self-test
│   └── ghidra_scripts/                # Ghidra analysis scripts (for version porting, optional)
├── docs/                              # manual + reverse-engineering notes + this landing page
└── data/                              # optional enhancement data (empty by default)
```

## 🗺 Roadmap

- [ ] Support future game versions (requires re-locating function addresses)
- [x] Panel localization: Chinese / English
- [ ] More decision dimensions (e.g., tech-pick stewardship)

## License

PolyForm Noncommercial 1.0.0 (see `LICENSE`) — free for noncommercial use; **commercial use is not licensed**. This repository contains no Paradox Interactive copyrighted content.
