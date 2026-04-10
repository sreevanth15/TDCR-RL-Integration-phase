# TDCR Physical (SOFA) - Complete Status and Usage Guide

This folder contains the current physical-grade TDCR workflow: simulation, motor-space control, logging, and training tooling.

It is designed to run in your SOFA Windows bundle and to stay compatible with your TDCR geometry workflow.

## 1) What this package does today

- Runs a **4-section x 3 tendons = 12 cables** TDCR simulation.
- Uses a **motor spool model** (`theta -> pulled tendon length`) to command cable displacements.
- Controls simulation from a second terminal via keyboard.
- Streams simulation state to JSON and JSONL for data collection / RL.
- Supports equation fitting and RL-style random-shooting training.

## 2) Core architecture

- `tdcr_physical.py` is the physical scene entry point.
- It dynamically imports `../sofa_tdcr/tdcr.py` and reuses its geometry + scene creation.
- It overrides only the controller with `TDCRPhysicalController`.
- Control is file-based:
  - command input: `tdcr_physical_cmd.json`
  - measured state output: `tdcr_physical_state.json`
  - rollout logs: `runs/tdcr_physical_log.jsonl.<timestamp>.jsonl`

This keeps one source of truth for TDCR scene structure while adding physical control behavior in this folder.

## 3) Geometry and tendon setup (current status)

- Primary geometry source (preferred):
  - `sofa_tdcr_physical/4_sec_Backbone_3T.STL` (or case variants)
- At startup, `tdcr_physical.py` copies this into:
  - `sofa_tdcr_physical/tdcr_surface.stl`
- Then it configures reference scene globals:
  - `NUM_SECTIONS = 4`
  - `TENDONS_PER_SECTION = 3`
  - `NUM_CABLES = 12`
  - section height from STL extent when available

### Important physical note

Current stable model uses `CableConstraint + BarycentricMapping` (standard robust setup).  
The previous experimental sliding-constraint tendon-guide attempt caused solver rank-deficiency and segfault on play in this SOFA build, so it was reverted for stability.

## 4) Physics model

Main parameters are in `physical_config.py`.

- Material:
  - `YOUNG_KPA = 600.0`
  - `POISSON = 0.45`
  - `TOTAL_MASS_G = 30.0`
- FEM annulus:
  - `INNER_R_MM = 6.5`
  - `OUTER_R_MM = 18.5`
- Tendon nominal placement:
  - radius offset: `CABLE_OFFSET_MM = 12.0`
  - angular layout: `[90, 210, 330]` deg
- Base fixation:
  - clamp below `BASE_FIX_Y_MM = 12.0`
- Motor spool model:
  - `deltaL_mm = SPOOL_RADIUS_MM * theta_rad`
  - with limits via `THETA_MIN_RAD`, `THETA_MAX_RAD`, `MAX_PULL_MM`
  - neutral pretension through `THETA0_RAD`

## 5) Control model (keyboard / command file)

Controller script: `control_keyboard.py`  
Writes command file: `tdcr_physical_cmd.json`

Command schema:

```json
{
  "theta": [0.0, 0.0, "... 12 values total ..."],
  "young": 600.0,
  "reset": false
}
```

- `theta[i]` are motor spool angles in rad (12 channels).
- Scene converts them to target displacement through spool model.
- Displacements are ramped with `SIM_RAMP_DISP_MM_PER_STEP`.

## 6) Keyboard mapping (12 motors)

Run in a second terminal:

`python control_keyboard.py`

Keys (single press, no Enter on Windows):

- Tighten motors 1..12: `1 2 3 4 5 6 7 8 9 a s d`
- Loosen motors 1..12: `q w e r t y u i o j k l`
- Reset all motors to neutral: `z`
- Stiffness scale:
  - `+` or `=` : multiply Young's modulus by 2
  - `-` : multiply by 0.5
- Quit controller: `ESC`

## 7) How to run

### Step A: launch SOFA scene

Preferred:
- `run_physical_imgui.bat` (full UI: scene graph, play/step/reset)

Alternative:
- `run_physical_glfw.bat` (minimal 3D view only)
- `run_physical.bat` (default GUI)

### Step B: press play

- In ImGui press `Play` (or `Space` depending on GUI/keybinds).

### Step C: send commands

- In a new terminal in this folder:
  - `python control_keyboard.py`

## 8) Logging and exported state

`TDCRPhysicalController` writes:

- `tdcr_physical_state.json` (latest snapshot for external clients/RL)
- `runs/tdcr_physical_log.jsonl.<timestamp>.jsonl` (time series)

State fields include:

- `tip` (mm)
- `theta_cmd_rad`
- `theta_meas_rad` (back-estimated from measured displacement)
- `disp_mm_cmd`
- `disp_mm_meas`
- `cable_forces_N` (best-effort)
- `cableLengths` (best-effort)
- `bend_angle_deg`
- `tip_disp_mm`
- `fem_vonMises` (mean/max, best-effort by build)

## 9) RL / data pipeline

With SOFA running and animation active:

- `python train_rl.py --dataset_steps 200 --episodes 3`

Expected outputs are placed under:

- `training_runs/<timestamp>/`

Pipeline currently:
- random exploration data collection
- equation fitting for motor-to-tip mapping
- reward-guided random-shooting loop

## 10) Utility scripts in this folder

- `run_physical_imgui.bat` - launch with ImGui.
- `run_physical_glfw.bat` - launch with GLFW.
- `run_physical.bat` - launch default GUI.
- `reset_sofa_imgui_layout.bat` - clear broken ImGui layout.
- `fix_sofa_after_move_or_reinstall.bat` - reset stale plugin path cache after moving/reinstalling SOFA.

## 11) Troubleshooting

### A) Thousands of plugin path errors (`error 123`, bad `...bin\C:\...` merged paths)

Cause: stale `%LOCALAPPDATA%\SOFA\config\loadedPlugins.ini` after moving/renaming install folders.

Fix:
- run `fix_sofa_after_move_or_reinstall.bat`
- relaunch SOFA

### B) Black or tiny ImGui viewport

Fix:
- run `reset_sofa_imgui_layout.bat`
- relaunch with `run_physical_imgui.bat`

### C) Scene opens but does not move

Checklist:
- press Play in GUI
- confirm `control_keyboard.py` is running in second terminal
- confirm `tdcr_physical_cmd.json` updates while pressing keys

### D) SOFA exits immediately on Play with solver error

If you see messages like:
- `Invalid Linear System to solve (size mismatch)`

this indicates a constraint-system issue in the scene variant. Use the current stable version in this folder (without experimental sliding constraints).

## 12) Known limitations / next steps

- Tendon-hole sliding realism is currently approximated by robust cable mapping, not full frictional sliding contact in holes.
- Cable force/stress availability depends on SOFA build/component exposure.
- Next upgrades (optional):
  - explicit tendon-guide mechanics with stable formulation
  - spool friction/backlash and motor dynamics
  - section coupling calibration against hardware experiments

## 13) Quick reference

- Scene: `tdcr_physical.py`
- Physical params: `physical_config.py`
- Keyboard control: `control_keyboard.py`
- Motor model: `motor_spool.py`
- RL env: `env_gym.py`
- Training launcher: `train_rl.py`

