# TDCR Physical-Grade Data Schema

This document defines the data written by the TDCR physical-grade SOFA scene
(`tdcr_physical.py`) and consumed by:
- `env_gym.py`
- `train_rl.py`

All units are written explicitly below.

## 1) Command file
File: `tdcr_physical_cmd.json`

Fields:
- `theta`: array of 9 motor spool angles in radians (absolute). Length must be 9.
- `young`: Young modulus in kPa.
- `reset`: boolean. When `true`, the controller sets all cables to zero displacement.

## 2) State file (latest snapshot)
File: `tdcr_physical_state.json`

Fields (written every simulation step):
- `tip`: `[x, y, z]` in mm.
- `theta_cmd_rad`: 9-element list, commanded motor angles in radians.
- `theta_meas_rad`: 9-element list, measured/estimated motor angles in radians.
  - This is best-effort estimated from CableConstraint displacement.
- `disp_mm_cmd`: 9-element list, commanded tendon/cable displacement in mm.
- `disp_mm_meas`: 9-element list, measured tendon/cable displacement in mm (best-effort).
- `cable_forces_N`: 9-element list, estimated cable forces in N (best-effort; may contain `null`).
- `cableLengths`: 9-element list, estimated cable length in mm (best-effort; may contain `null`).
- `bend_angle_deg`: continuum bend angle in degrees (best-effort derived from tip position).
- `tip_disp_mm`: tip displacement magnitude vs. initial base tip in mm.
- `fem_vonMises`: object:
  - `mean`: mean Von Mises stress across elements (if available; else `null`)
  - `max`: max Von Mises stress across elements (if available; else `null`)

## 3) JSONL rollout log
Location: `runs/<JSONL_LOG_FILE>.<timestamp>.jsonl`

Each line is one JSON record (one simulation step):
- All the same fields as the state snapshot (see above).
- Plus:
  - `simTimeSeconds`: float, simulation elapsed seconds.
  - `utc`: timestamp as a Unix float (seconds since epoch).

## 4) Training dataset artifacts
Produced by `train_rl.py` in `training_runs/<timestamp>/`:
- `dataset.npz`
  - `theta`: shape `(N, 9)`, motor angles used.
  - `tip`: shape `(N, 3)`, measured tip position in mm.
- `equation_coeffs.npz` and `equation_params.json`
  - Quadratic regression coefficients for mapping theta -> tip.
- `rollouts.json`
  - RL-like candidate action selection trajectories validated by the simulator.

