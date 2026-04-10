"""
Motor spool model for TDCR physical-grade simulation.

We model each tendon as wound on a spool:
  deltaL_mm = spool_radius_mm * (theta_rad - theta0_rad)

Control input can be motor angles (theta). The SOFA mechanics still actuate
using CableConstraint displacement (valueType='displacement').
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass(frozen=True)
class MotorSpool:
    spool_radius_mm: float
    theta0_rad: float
    theta_min_rad: float
    theta_max_rad: float
    max_pull_mm: float

    def theta_to_deltaL_mm(self, theta_rad: float) -> float:
        theta_rad = clamp(theta_rad, self.theta_min_rad, self.theta_max_rad)
        d = self.spool_radius_mm * (theta_rad - self.theta0_rad)
        return clamp(d, 0.0, self.max_pull_mm)

    def deltaL_mm_to_theta_rad(self, deltaL_mm: float) -> float:
        d = clamp(deltaL_mm, 0.0, self.max_pull_mm)
        # Avoid division by zero in a pathological config
        if abs(self.spool_radius_mm) < 1e-9:
            return self.theta_min_rad
        return self.theta0_rad + (d / self.spool_radius_mm)


def make_default_spool(**cfg) -> MotorSpool:
    """
    Convenience constructor using keys from physical_config.py.
    """
    return MotorSpool(
        spool_radius_mm=float(cfg["SPOOL_RADIUS_MM"]),
        theta0_rad=float(cfg["THETA0_RAD"]),
        theta_min_rad=float(cfg["THETA_MIN_RAD"]),
        theta_max_rad=float(cfg["THETA_MAX_RAD"]),
        max_pull_mm=float(cfg["MAX_PULL_MM"]),
    )

