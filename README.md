# AimLite

A lightweight fullscreen aim trainer for players whose computers can't run Aimlabs or KovaaK's.

Built with Python and pygame. No launcher, no account, no internet connection required. Launches instantly and runs on low-end and older hardware.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![pygame](https://img.shields.io/badge/pygame-2.0+-green) ![Platform](https://img.shields.io/badge/platform-Windows-lightgrey) ![License](https://img.shields.io/badge/license-MIT-orange)

---

## Download

**No Python required — just download and run.**

👉 [Download AimLite.exe (latest release)](../../releases/latest)

> **Windows SmartScreen warning:** Windows may show a "Windows protected your PC" popup the first time you run it. This happens to all unsigned executables from small developers — it does not mean the file is dangerous. Click **"More info"** → **"Run anyway"** to launch it. The source code is fully public and auditable above.

---

## Training Modes

| Mode | Description |
|------|-------------|
| **Regular Flick** | 3 clustered targets. Click one, it respawns nearby. Trains flick speed and accuracy. |
| **Small Flick** | Same as above but with smaller targets. Trains precision. |
| **Tracking** | A moving humanoid target that strafes, crouches, and jumps. Trains target tracking. |
| **Reaction** | One target spawns at a time after a random delay. Measures pure reaction speed. |

Session length is selectable: 30, 60, or 120 seconds.

---

## Game Sensitivity Profiles

AimLite simulates the sensitivity of each supported game so your mouse movement feels identical to what you'd get in-game. Set your real in-game values and DPI, and the trainer matches it exactly.

| Game | Yaw | Notes |
|------|-----|-------|
| **Counter-Strike 2** | 0.022°/count | Source engine standard |
| **Valorant** | 0.07°/count | Includes ADS/scoped multiplier |
| **Marvel Rivals** | 0.0066°/count | Same scale as Overwatch 2 |
| **Rainbow Six Siege** | 0.0057°/count | Full x_factor + scope modifier ADS chain |
| **Overwatch 2** | 0.0066°/count | ADS as % of hipfire |

Right-click while playing to toggle ADS sensitivity.

The settings screen shows your **cm/360** live so you can verify it matches your in-game feel.

---

## Running from Source

If you'd rather run from source or you're on Linux/Mac:

**Requirements**
- Python 3.10 or newer
- pygame

**Install and run**
```bash
git clone https://github.com/NaoWasTaken/AimLite.git
cd AimLite
pip install pygame
python aim_trainer.py
```

---

## Controls

| Input | Action |
|-------|--------|
| Left click | Shoot |
| Right click | Toggle ADS |
| Escape | Open settings / pause |
| F10 | Quit immediately |

---

## Settings & Profiles

All settings are saved automatically to `sensitivity_profiles.json` in the same folder as the exe. This includes:

- Per-game sensitivity, DPI, yaw, and FOV
- Crosshair size, thickness, gap, color, and dot toggle
- Audio volumes

High scores are saved to `scores.json` in the same folder.

To reset everything, just delete those two files.

---

## Why does this exist?

Aimlabs requires a modern GPU and a decent amount of RAM to run smoothly. KovaaK's is paid. If you have an older or budget PC, both of them are either unplayable or inaccessible.

AimLite runs on integrated graphics and old hardware because it's just shapes on a dark background — exactly as much as an aim trainer needs to be.

---

## License

MIT — do whatever you want with it.
