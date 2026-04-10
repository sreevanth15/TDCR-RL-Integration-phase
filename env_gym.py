"""
Gymnasium environment for TDCR physical-grade scene.

The environment controls NUM_CABLES motor spool angles via:
  - Command file: tdcr_physical_cmd.json
  - State file   : tdcr_physical_state.json

You must run SOFA (tdcr_physical.py) and press Play before calling reset/step.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional, Tuple

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from physical_config import (
    CMD_FILE,
    NUM_CABLES,
    NUM_SECTIONS,
    TENDONS_PER_SECTION,
    STATE_FILE,
    THETA0_RAD,
    THETA_MAX_RAD,
    THETA_MIN_RAD,
    MAX_PULL_MM,
    SOFA_STEP_WAIT_S,
    RESET_WAIT_S,
    STATE_SETTLE_STEPS,
)


HERE = os.path.dirname(os.path.abspath(__file__))
CMD_PATH = os.path.join(HERE, CMD_FILE)
STATE_PATH = os.path.join(HERE, STATE_FILE)


# Wide bounds for a 3x stacked robot (mm). Adjust later if you want tighter clipping.
TIP_MIN = np.array([-200.0, 0.0, -200.0], dtype=np.float32)
TIP_MAX = np.array([200.0, 450.0, 200.0], dtype=np.float32)


class TDCRPhysicalEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, max_steps: int = 120):
        super().__init__()

        self.action_space = spaces.Box(
            low=float(THETA_MIN_RAD),
            high=float(THETA_MAX_RAD),
            shape=(NUM_CABLES,),
            dtype=np.float32,
        )

        self.observation_space = spaces.Box(
            low=TIP_MIN,
            high=TIP_MAX,
            shape=(3,),
            dtype=np.float32,
        )

        self._max_steps = int(max_steps)
        self._step_count = 0
        self._prev_dist: Optional[float] = None
        self._prev_action = np.zeros(NUM_CABLES, dtype=np.float32)

        # Target tip position for this episode
        self._target = np.zeros(3, dtype=np.float32)

        self._young_kpa = 600.0

    def _write_cmd(self, theta: np.ndarray, reset: bool = False):
        theta = np.asarray(theta, dtype=np.float32).reshape(-1)
        if theta.size < NUM_CABLES:
            theta = np.pad(theta, (0, NUM_CABLES - theta.size), constant_values=THETA0_RAD)
        theta = theta[:NUM_CABLES]

        # Prevent "squeezing"/shortening: in a real TDCR you mostly bend via
        # differential tendon pulls inside each section. Pulling all 3 tendons
        # together (common-mode) tends to compress/shorten the structure.
        #
        # We enforce per-section zero-mean *offsets* around THETA0:
        #   theta_sec <- THETA0 + (theta_sec - mean(theta_sec))
        # This keeps average tendon pull near the neutral pretension and
        # strongly encourages bending rather than squeezing.
        th = theta.reshape(NUM_SECTIONS, TENDONS_PER_SECTION)
        th = THETA0_RAD + (th - th.mean(axis=1, keepdims=True))
        theta = th.reshape(NUM_CABLES)
        theta = np.clip(theta, float(THETA_MIN_RAD), float(THETA_MAX_RAD)).astype(np.float32)

        cmd = {
            "theta": [float(x) for x in theta.tolist()],
            "young": float(self._young_kpa),
            "reset": bool(reset),
        }
        with open(CMD_PATH, "w", encoding="utf-8") as f:
            json.dump(cmd, f)

    def _read_state_tip(self) -> Optional[np.ndarray]:
        if not os.path.exists(STATE_PATH):
            return None
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                st = json.load(f)
            tip = st.get("tip", None)
            if tip and len(tip) == 3:
                return np.array(tip, dtype=np.float32)
        except Exception:
            return None
        return None

    def _wait_for_update(self, timeout_s: float = 2.0):
        if not os.path.exists(STATE_PATH):
            time.sleep(SOFA_STEP_WAIT_S)
            return False
        try:
            m0 = os.path.getmtime(STATE_PATH)
        except Exception:
            time.sleep(SOFA_STEP_WAIT_S)
            return False

        t0 = time.time()
        while time.time() - t0 < timeout_s:
            time.sleep(0.02)
            try:
                if os.path.getmtime(STATE_PATH) > m0:
                    return True
            except Exception:
                pass
        return False

    def _sample_target(self) -> np.ndarray:
        # Sample inside a "mostly reachable" workspace for the current model.
        # Empirically with the default physical settings, tip Y stays near ~280-330mm.
        # Keeping targets in this band reduces "it doesn't go there" episodes.
        x = self.np_random.uniform(-120.0, 120.0)
        y = self.np_random.uniform(260.0, 340.0)
        z = self.np_random.uniform(-120.0, 120.0)
        return np.array([x, y, z], dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        # Reset robot to neutral
        self._write_cmd(np.array([THETA0_RAD] * NUM_CABLES, dtype=np.float32), reset=True)
        time.sleep(RESET_WAIT_S)

        self._target = self._sample_target()
        self._step_count = 0
        self._prev_dist = None
        self._prev_action = np.zeros(NUM_CABLES, dtype=np.float32)

        # settle a bit more
        for _ in range(STATE_SETTLE_STEPS):
            self._wait_for_update()

        tip = self._read_state_tip()
        if tip is None:
            tip = np.zeros(3, dtype=np.float32)
        obs = np.clip(tip, TIP_MIN, TIP_MAX)
        info = {"target": self._target.tolist(), "tip": tip.tolist()}
        return obs, info

    def step(self, action: np.ndarray):
        action = np.asarray(action, dtype=np.float32).reshape(-1)
        if action.size < NUM_CABLES:
            action = np.pad(action, (0, NUM_CABLES - action.size), constant_values=THETA0_RAD)
        action = action[:NUM_CABLES]
        action = np.clip(action, float(THETA_MIN_RAD), float(THETA_MAX_RAD))
        self._write_cmd(action, reset=False)

        # Wait for SOFA to write updated state
        for _ in range(STATE_SETTLE_STEPS):
            self._wait_for_update()

        tip = self._read_state_tip()
        if tip is None:
            tip = np.zeros(3, dtype=np.float32)

        dist = float(np.linalg.norm(tip - self._target))
        progress = (self._prev_dist - dist) if self._prev_dist is not None else 0.0

        # Reward: progress + distance penalty + goal bonus + smoothness
        r_progress = progress * 2.0
        r_dist = -dist * 0.02
        r_goal = 100.0 if dist < 5.0 else 0.0
        delta_a = float(np.linalg.norm(action - self._prev_action))
        r_smooth = -delta_a * 0.05

        # Extra penalty for "common-mode pull" away from neutral (squeezing).
        # Note: action is the *requested* theta; _write_cmd applies the projection
        # before sending to SOFA. We still penalize the raw command to teach the
        # policy to stay in-bounds naturally.
        asec = action.reshape(NUM_SECTIONS, TENDONS_PER_SECTION)
        common = asec.mean(axis=1) - float(THETA0_RAD)  # (3,)
        r_common = -0.8 * float(np.linalg.norm(common))

        reward = float(r_progress + r_dist + r_goal + r_smooth + r_common)

        self._step_count += 1
        terminated = dist < 5.0
        truncated = self._step_count >= self._max_steps

        self._prev_dist = dist
        self._prev_action = action.copy()

        obs = np.clip(tip, TIP_MIN, TIP_MAX)
        info = {
            "dist_mm": dist,
            "tip": tip.tolist(),
            "target": self._target.tolist(),
            "step": self._step_count,
        }
        return obs, reward, terminated, truncated, info

    def close(self):
        # Leave robot in neutral (best-effort)
        try:
            self._write_cmd(np.array([THETA0_RAD] * NUM_CABLES, dtype=np.float32), reset=True)
        except Exception:
            pass

