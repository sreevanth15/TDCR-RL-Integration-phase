# TDCR Physical-Grade (Motor + Spool + RL Logging)

This folder contains a “physical-grade” TDCR simulation scaffold that:
- Reuses the geometry/cable placement from `sofa_tdcr/tdcr.py`
- Adds a **motor spool model** that converts motor spool angle `theta` to
  tendon/cable displacement `deltaL`
- Controls the robot using a **9-motor** command interface
- Records research data (JSONL rollouts + latest state JSON)
- Provides an RL-ready Gymnasium environment and a first “equation fitting”
  trainer.

## Prerequisites
- SOFA is installed in `SOFA_v25.12.00_Win64/` as before.
- `gymnasium` and `numpy` are available for `env_gym.py` and `train_rl.py`.

## Run SOFA
Option 1 (recommended, avoids ImGui viewport issues):
1. Open `sofa_tdcr_physical` folder
2. Click `reset_sofa_imgui_layout.bat` if the viewport looks black
3. Run:
   - `run_physical_glfw.bat`
4. In SOFA, press the **▶ Play** button.

Option 2:
- `run_physical.bat` (ImGui UI)

## Control with keyboard (9 motors)
Open a second terminal in `sofa_tdcr_physical`:
- `python control_keyboard.py`

Keys (single key, no Enter on Windows):
- `1-9` tighten: increases `theta[i]`
- `q w e r t y u i o` loosen: decreases `theta[i]`
- `z` reset (all theta to THETA0)
- `+ / -` stiffness (Young modulus multiplier)
- `ESC` quit

The command file is: `tdcr_physical_cmd.json`.

## Logs / data
- Latest state snapshot: `tdcr_physical_state.json`
- JSONL step rollouts: `runs/tdcr_physical_log.jsonl.<timestamp>.jsonl`

## RL/data training
With SOFA running + Play pressed:
- `python train_rl.py --dataset_steps 200 --episodes 3`

This will:
1. Randomly explore motor angles through the Gym env
2. Fit a quadratic equation mapping `theta` -> tip position
3. Run an RL-like reward-guided random shooting loop
4. Save outputs in `sofa_tdcr_physical/training_runs/<timestamp>/`

## Notes
- Cable force and stress are logged “best-effort” (SOFA build differences).
- If you want more physical realism (tendon/tube routing constraints, motor spool friction/backlash,
  and 3 stacked FEM bodies with coupling), we can extend this scaffold in a follow-up.

