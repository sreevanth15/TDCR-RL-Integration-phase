#!/usr/bin/env python3
"""
TDCR physical-grade SOFA scene (θ control + research logging).

This scene reuses the geometry + cable placement from `sofa_tdcr/tdcr.py`
by importing it dynamically and overriding only the controller logic.

Control interface:
  Command file:  tdcr_physical_cmd.json
    - theta: 9 motor spool angles in radians (absolute)
    - young: Young modulus (kPa)
    - reset: boolean

  State file: tdcr_physical_state.json
    - tip: [x,y,z] in mm
    - theta_cmd_rad: commanded angles
    - theta_meas_rad: estimated angles from cable displacement
    - disp_mm_meas / disp_mm_cmd
    - cable_forces_N (best-effort)
    - fem_vonMises (best-effort)
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import time
from typing import Any, Optional

import Sofa, Sofa.Core

from logger import LogPaths, LogWriter
from motor_spool import make_default_spool, MotorSpool
from physical_config import (
    CMD_FILE,
    JSONL_LOG_FILE,
    MAX_PULL_MM,
    SOFA_STEP_WAIT_S,
    STATE_FILE,
    LOG_EVERY_N_STEPS,
    NUM_CABLES,
    NUM_SECTIONS,
    POISSON,
    RESET_WAIT_S,
    SIM_RAMP_DISP_MM_PER_STEP,
    SPOOL_RADIUS_MM,
    THETA0_RAD,
    THETA_MAX_RAD,
    THETA_MIN_RAD,
    TOTAL_MASS_G,
    YOUNG_KPA,
)


HERE = os.path.dirname(os.path.abspath(__file__))


def _load_reference_tdcr():
    """
    Load `sofa_tdcr/tdcr.py` as a module without changing your geometry code.
    """
    ref_path = os.path.join(HERE, "..", "sofa_tdcr", "tdcr.py")
    ref_path = os.path.abspath(ref_path)
    spec = importlib.util.spec_from_file_location("tdcr_ref", ref_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import tdcr.py from: {ref_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tdcr_ref = _load_reference_tdcr()


# Prevent repeated side effects from the reference import:
# the reference scene creates log CSV in sofa_tdcr/. We do not rely on it.
try:
    _tdcr_here = getattr(tdcr_ref, "HERE", None)
    if _tdcr_here:
        for fn in ["tdcr_cmd.json", "bending_data.csv"]:
            p = os.path.join(_tdcr_here, fn)
            if os.path.exists(p):
                os.remove(p)
except Exception:
    pass


CMD_PATH = os.path.join(HERE, CMD_FILE)
STATE_PATH = os.path.join(HERE, STATE_FILE)


def _safe_scalar_from_value(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        if isinstance(v, (list, tuple)):
            if len(v) == 0:
                return None
            # Vec3 case -> magnitude
            if len(v) == 3 and all(isinstance(x, (int, float)) for x in v):
                return float(math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]))
            return float(v[0])
        return float(v)
    except Exception:
        return None


def _get_data_scalar(obj: Any, data_name: str) -> Optional[float]:
    try:
        data_obj = getattr(obj, data_name)
        return _safe_scalar_from_value(data_obj.value)
    except Exception:
        return None


class TDCRPhysicalController(Sofa.Core.Controller):
    def __init__(
        self,
        cable_nodes,
        fem_ff,
        tip_mo,
        base_tip,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._cables = list(cable_nodes)
        self._fem = fem_ff
        self._tip = tip_mo
        self._base_tip = list(base_tip)

        n = len(self._cables)
        self._spool: MotorSpool = make_default_spool(
            SPOOL_RADIUS_MM=SPOOL_RADIUS_MM,
            THETA0_RAD=THETA0_RAD,
            THETA_MIN_RAD=THETA_MIN_RAD,
            THETA_MAX_RAD=THETA_MAX_RAD,
            MAX_PULL_MM=MAX_PULL_MM,
        )

        self._disp = [0.0] * n
        self._disp_target = [0.0] * n
        self._theta_cmd = [THETA0_RAD] * n

        self._young = YOUNG_KPA
        self._step = 0
        self._t0 = time.time()
        self._last_mt = 0.0

        # Ensure cmd exists so a fresh start works.
        if not os.path.exists(CMD_PATH):
            with open(CMD_PATH, "w", encoding="utf-8") as f:
                json.dump({"theta": [THETA0_RAD] * n, "young": self._young, "reset": False}, f)

        # Logging
        run_ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        jsonl_path = os.path.join(HERE, "runs", f"{JSONL_LOG_FILE}.{run_ts}.jsonl")
        state_path = STATE_PATH
        self._log = LogWriter(LogPaths(jsonl_path=jsonl_path, state_path=state_path))

        # Make the UI/game loop print instructions once.
        print("[PHYS] TDCR physical controller ready.")
        print(f"[PHYS] cmd={CMD_PATH}")
        print(f"[PHYS] state={STATE_PATH}")
        print(f"[PHYS] log={jsonl_path}")
        print("  Keyboard: python control_keyboard.py  (new terminal)")

    def _angle(self, tp):
        h = math.sqrt(float(tp[0]) ** 2 + float(tp[2]) ** 2)
        return math.degrees(math.atan2(h, max(float(tp[1]), 0.001)))

    def _disp3(self, tp):
        d = [float(tp[i]) - self._base_tip[i] for i in range(3)]
        return math.sqrt(sum(x * x for x in d))

    def _read_cmd_if_updated(self):
        try:
            if not os.path.exists(CMD_PATH):
                return
            mt = os.path.getmtime(CMD_PATH)
            if mt <= self._last_mt:
                return
            self._last_mt = mt

            with open(CMD_PATH, "r", encoding="utf-8") as f:
                cmd = json.load(f)

            if cmd.get("reset", False):
                self._theta_cmd = [THETA0_RAD] * len(self._cables)
                self._disp_target = [0.0] * len(self._cables)
                self._disp = [0.0] * len(self._cables)
                for cn in self._cables:
                    cn.CableConstraint.value.value = [0.0]
                # Clear reset so it doesn't keep re-triggering
                cmd["reset"] = False
                cmd["theta"] = [THETA0_RAD] * len(self._cables)
                with open(CMD_PATH, "w", encoding="utf-8") as f:
                    json.dump(cmd, f)
                print("[PHYS] RESET applied.")
                return

            theta = cmd.get("theta", [THETA0_RAD] * len(self._cables))
            if not isinstance(theta, list):
                theta = [THETA0_RAD] * len(self._cables)
            while len(theta) < len(self._cables):
                theta.append(THETA0_RAD)
            theta = [float(x) for x in theta[: len(self._cables)]]

            self._theta_cmd = theta
            self._disp_target = [
                self._spool.theta_to_deltaL_mm(th) for th in self._theta_cmd
            ]

            ny = float(cmd.get("young", self._young))
            if abs(ny - self._young) > 1.0:
                self._young = ny
                self._fem.youngModulus.value = self._young
                print(f"[PHYS] E={self._young:.0f} kPa")
        except Exception:
            # Keep the sim running even if file parsing fails
            pass

    def onAnimateBeginEvent(self, _):
        self._read_cmd_if_updated()

        # Ramp imposed displacement toward target (motor/spool angle -> deltaL).
        for i, cn in enumerate(self._cables):
            diff = self._disp_target[i] - self._disp[i]
            if abs(diff) > 1e-6:
                step = min(abs(diff), SIM_RAMP_DISP_MM_PER_STEP) * (1.0 if diff > 0 else -1.0)
                self._disp[i] += step
                cn.CableConstraint.value.value = [self._disp[i]]

    def onAnimateEndEvent(self, _):
        self._step += 1
        try:
            pos = self._tip.position.value
            if len(pos) == 0:
                return

            tp = pos[0]
            ang = self._angle(tp)
            dsp = self._disp3(tp)

            # Read best-effort cable outputs
            disp_meas = []
            theta_meas = []
            forces = []
            lengths = []
            for cn in self._cables:
                disp_now = _get_data_scalar(cn.CableConstraint, "displacement")
                if disp_now is None:
                    disp_now = float(cn.CableConstraint.value.value[0]) if hasattr(cn.CableConstraint, "value") else self._disp[0]
                theta_now = self._spool.deltaL_mm_to_theta_rad(disp_now)
                f_now = _get_data_scalar(cn.CableConstraint, "force")
                L_now = _get_data_scalar(cn.CableConstraint, "cableLength")
                disp_meas.append(disp_now)
                theta_meas.append(theta_now)
                forces.append(f_now)
                lengths.append(L_now)

            # FEM stress Von Mises (if available in this build)
            von_mean = None
            von_max = None
            try:
                st = self._fem.stressVonMisesElement.value
                if isinstance(st, (list, tuple)) and len(st) > 0:
                    st2 = [float(x) for x in st]
                    von_mean = sum(st2) / len(st2)
                    von_max = max(st2)
            except Exception:
                pass

            t = time.time() - self._t0

            # State for the external Gym env / haptics
            state = {
                "time_s": round(t, 6),
                "step": self._step,
                "tip": [round(float(tp[i]), 4) for i in range(3)],
                "theta_cmd_rad": [round(float(x), 6) for x in self._theta_cmd],
                "theta_meas_rad": [round(float(x), 6) for x in theta_meas],
                "disp_mm_cmd": [round(float(x), 6) for x in self._disp_target],
                "disp_mm_meas": [round(float(x), 6) for x in disp_meas],
                "cable_forces_N": [None if x is None else round(float(x), 6) for x in forces],
                "cableLengths": [None if x is None else round(float(x), 6) for x in lengths],
                "bend_angle_deg": round(float(ang), 5),
                "tip_disp_mm": round(float(dsp), 5),
                "fem_vonMises": {"mean": von_mean, "max": von_max},
            }

            # Rollout record (JSONL) for future researchers
            record = dict(state)
            record["simTimeSeconds"] = record["time_s"]
            record["utc"] = time.time()

            if LOG_EVERY_N_STEPS <= 1 or (self._step % LOG_EVERY_N_STEPS) == 0:
                self._log.write_step(record, state=state)
            else:
                # Still update the state file, just not the JSONL each step
                self._log.write_step(record, state=state)

        except Exception:
            # Never crash the sim due to logging
            pass


def createScene(root):
    # Override controller class inside the reference tdcr.py scene.
    tdcr_ref.TDCRController = TDCRPhysicalController
    return tdcr_ref.createScene(root)

