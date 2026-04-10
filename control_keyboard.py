#!/usr/bin/env python3
# TDCR physical controller (keyboard) — 12 motors.
#
# Run in:
#   cd ...\SOFA_v25.12.00_Win64\sofa_tdcr_physical
#   python control_keyboard.py
#
# Keys (single key, no Enter — Windows):
#   1-9 a s d tighten: theta[i] += step
#   qwertyuio j k l loosen: theta[i] -= step (same mapping order)
#   z  reset: all theta -> THETA0
#   +/- stiffness: multiplies Young's modulus
#   ESC quit
#
# Writes:
#   tdcr_physical_cmd.json  with fields:
#     { "theta": [rad x 12], "young": kPa, "reset": bool }

from __future__ import annotations

import json
import os
import sys

from physical_config import (
    CMD_FILE,
    KEY_STEP_THETA_RAD,
    NUM_CABLES,
    RESET_WAIT_S,
    THETA0_RAD,
    THETA_MAX_RAD,
    THETA_MIN_RAD,
    YOUNG_KPA,
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


HERE = os.path.dirname(os.path.abspath(__file__))
CMD_PATH = os.path.join(HERE, CMD_FILE)

YOUNG_MIN = 50.0
YOUNG_MAX = 50000.0


def read_cmd() -> dict:
    try:
        with open(CMD_PATH, "r", encoding="utf-8") as f:
            s = json.load(f)
    except Exception:
        s = {"theta": [THETA0_RAD] * NUM_CABLES, "young": YOUNG_KPA, "reset": False}
    if "theta" not in s or not isinstance(s["theta"], list):
        s["theta"] = [THETA0_RAD] * NUM_CABLES
    # pad/trim
    theta = [float(x) for x in s["theta"][:NUM_CABLES]]
    while len(theta) < NUM_CABLES:
        theta.append(THETA0_RAD)
    s["theta"] = theta
    s["young"] = float(s.get("young", YOUNG_KPA))
    s["reset"] = bool(s.get("reset", False))
    return s


def write_cmd(s: dict) -> None:
    with open(CMD_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f)


def show(s: dict) -> None:
    theta = s["theta"]
    rows = []
    for i in range(0, NUM_CABLES, 3):
        rows.append(" ".join(f"{theta[j]:+.2f}" for j in range(i, min(i + 3, NUM_CABLES))))
    body = "\n    ".join(rows)
    print(f"  theta(rad):\n    {body}   | E={s['young']:.0f}kPa reset={s['reset']}")


INC_KEYS = list("123456789asd")
DIGIT_INC = {k: i for i, k in enumerate(INC_KEYS)}
DEC_KEYS = list("qwertyuiojkl")
KEY_DEC = {k: i for i, k in enumerate(DEC_KEYS)}


def apply_delta_theta(idx: int, delta: float) -> None:
    s = read_cmd()
    s["reset"] = False
    s["theta"][idx] = _clamp(s["theta"][idx] + delta, THETA_MIN_RAD, THETA_MAX_RAD)
    write_cmd(s)
    show(s)


def apply_reset() -> None:
    s = read_cmd()
    s["theta"] = [THETA0_RAD] * NUM_CABLES
    s["reset"] = True
    write_cmd(s)
    print("  Reset sent.")
    # Let SOFA pick the reset; then clear the flag
    s["reset"] = False
    write_cmd(s)


def stiffness(mult: float) -> None:
    s = read_cmd()
    y = float(s.get("young", YOUNG_KPA)) * mult
    s["young"] = max(YOUNG_MIN, min(YOUNG_MAX, y))
    s["reset"] = False
    write_cmd(s)
    show(s)


def run_windows_keys() -> None:
    import msvcrt

    print("\n  TDCR physical keyboard (12 motors)\n")
    print("  1-9 a s d tighten   q w e r t y u i o j k l loosen   z reset\n  +/- stiffness   ESC quit\n")
    s = read_cmd()
    write_cmd(s)
    show(s)

    while True:
        ch = msvcrt.getch()
        if ch in (b"\x1b",):  # ESC
            print("\nBye.")
            break
        if ch in (b"\r", b"\n"):
            continue
        if ch in (b"\xe0", b"\x00"):
            msvcrt.getch()
            continue

        k = ch.decode("utf-8", errors="ignore").lower()
        if not k:
            continue

        if k in DIGIT_INC:
            apply_delta_theta(DIGIT_INC[k], +KEY_STEP_THETA_RAD)
        elif k in KEY_DEC:
            apply_delta_theta(KEY_DEC[k], -KEY_STEP_THETA_RAD)
        elif k == "z":
            apply_reset()
        elif k == "+" or k == "=":
            stiffness(2.0)
        elif k == "-":
            stiffness(0.5)
        elif k == "h":
            print("  1-9 a s d +, qwertyuio j k l -, z reset, +/- stiffness, ESC quit")
        else:
            print(f"  Unknown key: {repr(k)} (h for help)")


def run_line_mode() -> None:
    print("\nLine mode (type: <index> <delta>), example: 1 +0.05 ; q to quit.")
    while True:
        try:
            line = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not line:
            continue
        if line in ("q", "quit", "exit"):
            break
        if line == "z":
            apply_reset()
            continue
        if line in ("+", "-"):
            stiffness(2.0 if line == "+" else 0.5)
            continue
        parts = line.split()
        if len(parts) != 2:
            print("Expected: <index 1-12> <delta_theta_rad>  or  z")
            continue
        idx = int(parts[0]) - 1
        delta = float(parts[1])
        if 0 <= idx < NUM_CABLES:
            apply_delta_theta(idx, delta)
        else:
            print("Index must be 1..12")


def main() -> None:
    if sys.platform == "win32" and sys.stdin.isatty():
        try:
            run_windows_keys()
        except Exception:
            run_line_mode()
    else:
        run_line_mode()


if __name__ == "__main__":
    # Ensure cmd exists
    if not os.path.exists(CMD_PATH):
        write_cmd({"theta": [THETA0_RAD] * NUM_CABLES, "young": YOUNG_KPA, "reset": False})
    main()

