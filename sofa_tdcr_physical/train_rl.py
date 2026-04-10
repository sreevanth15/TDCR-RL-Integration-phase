"""
RL-infused (data-driven) training harness for TDCR physical-grade scene.

This is designed to work with minimal external dependencies:
- It collects datasets by random motor-angle exploration using `env_gym`.
- It fits a quadratic regression model that approximates tip position as a
  function of the 9 motor angles. This gives you an explicit mathematical
  equation usable for your real world mapping.
- It then performs a simple RL-like "reward-guided" random shooting using
  the learned model to choose actions, while still validating with the real
  simulator through the Gym environment.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

from env_gym import TDCRPhysicalEnv
from physical_config import (
    NUM_CABLES,
    THETA_MIN_RAD,
    THETA_MAX_RAD,
    THETA0_RAD,
)


def quadratic_features(theta: np.ndarray, include_bias: bool = True) -> np.ndarray:
    """
    Quadratic polynomial features:
      [1, theta_i, theta_i*theta_j for i<=j]
    """
    theta = np.asarray(theta, dtype=np.float64).reshape(-1)
    assert theta.size == NUM_CABLES
    feats = []
    if include_bias:
        feats.append(1.0)
    feats.extend(theta.tolist())
    # i <= j terms
    for i in range(NUM_CABLES):
        for j in range(i, NUM_CABLES):
            feats.append(float(theta[i] * theta[j]))
    return np.asarray(feats, dtype=np.float64)


def fit_quadratic_model(dataset: Dict[str, np.ndarray]):
    """
    dataset:
      - 'theta': (N, 9)
      - 'tip'  : (N, 3)
    returns:
      coeffs: (3, F) where tip_coord = sum_f coeffs[coord,f] * features_f
      meta: dict
    """
    theta = dataset["theta"]  # (N,9)
    tip = dataset["tip"]  # (N,3)
    N = theta.shape[0]
    F = quadratic_features(theta[0]).size

    X = np.zeros((N, F), dtype=np.float64)
    for i in range(N):
        X[i, :] = quadratic_features(theta[i])

    # Solve separately for x,y,z
    coeffs = np.zeros((3, F), dtype=np.float64)
    for coord in range(3):
        y = tip[:, coord]
        w, *_ = np.linalg.lstsq(X, y, rcond=None)
        coeffs[coord, :] = w

    meta = {
        "feature_type": "quadratic_theta_features",
        "num_cables": NUM_CABLES,
        "feature_dim": int(F),
    }
    return coeffs, meta


def predict_tip(coeffs: np.ndarray, theta: np.ndarray) -> np.ndarray:
    feats = quadratic_features(theta)
    # coeffs shape (3,F)
    return (coeffs @ feats).astype(np.float64)


def dataset_random_exploration(
    env: TDCRPhysicalEnv,
    num_steps: int,
    rng: np.random.Generator,
):
    """
    One long stream of (theta, tip) tuples gathered from env.step.
    """
    thetas = []
    tips = []

    obs, info = env.reset(seed=None)
    for _ in range(num_steps):
        action = rng.uniform(float(THETA_MIN_RAD), float(THETA_MAX_RAD), size=(NUM_CABLES,)).astype(np.float32)
        obs, reward, terminated, truncated, info = env.step(action)
        tip = np.array(info["tip"], dtype=np.float64)
        thetas.append(action.astype(np.float64))
        tips.append(tip)
        if terminated or truncated:
            obs, info = env.reset()

    dataset = {
        "theta": np.stack(thetas, axis=0),
        "tip": np.stack(tips, axis=0),
    }
    return dataset


def rl_like_policy_improvement(
    env: TDCRPhysicalEnv,
    coeffs: np.ndarray,
    num_episodes: int,
    horizon: int,
    candidate_samples: int,
    rng: np.random.Generator,
):
    """
    RL-like loop: for each step, sample candidate actions, predict tip using the
    learned equation, and choose the action that minimizes predicted distance.
    Still validated by env.step (real simulator).
    """
    rollouts = []

    for ep in range(num_episodes):
        obs, info = env.reset()
        target = np.array(info["target"], dtype=np.float64)
        action = np.ones(NUM_CABLES, dtype=np.float64) * float(THETA0_RAD)

        ep_traj = {"episode": ep, "target": target.tolist(), "steps": []}

        for st in range(horizon):
            # Candidate set around previous action (improves stability)
            center = np.clip(action, float(THETA_MIN_RAD), float(THETA_MAX_RAD))
            spread = 0.15 * (float(THETA_MAX_RAD) - float(THETA_MIN_RAD))
            cand = center + rng.uniform(-spread, spread, size=(candidate_samples, NUM_CABLES))
            cand = np.clip(cand, float(THETA_MIN_RAD), float(THETA_MAX_RAD))

            best_a = None
            best_d = None
            for k in range(candidate_samples):
                a = cand[k]
                pred_tip = predict_tip(coeffs, a)
                d = float(np.linalg.norm(pred_tip - target))
                if best_d is None or d < best_d:
                    best_d = d
                    best_a = a

            action = np.array(best_a, dtype=np.float32)
            obs, reward, terminated, truncated, info = env.step(action)

            ep_traj["steps"].append(
                {
                    "step": st,
                    "action_theta_rad": action.astype(np.float64).tolist(),
                    "tip": info["tip"],
                    "dist_mm": info["dist_mm"],
                    "reward": float(reward),
                    "done": bool(terminated or truncated),
                }
            )

            if terminated or truncated:
                break

        rollouts.append(ep_traj)

    return rollouts


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_steps", type=int, default=200, help="Random steps for dataset collection")
    ap.add_argument("--episodes", type=int, default=3, help="Improvement episodes (RL-like)")
    ap.add_argument("--horizon", type=int, default=20, help="Max steps per episode")
    ap.add_argument("--candidates", type=int, default=80, help="Candidates per decision")
    ap.add_argument("--max_steps_per_episode", type=int, default=120)
    args = ap.parse_args()

    out_dir = os.path.join(os.path.dirname(__file__), "training_runs", time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)

    print(f"[TRAIN] output -> {out_dir}")
    env = TDCRPhysicalEnv(max_steps=args.max_steps_per_episode)
    rng = np.random.default_rng(0)

    print("[TRAIN] Collecting dataset (random exploration)...")
    dataset = dataset_random_exploration(env, num_steps=args.dataset_steps, rng=rng)
    np.savez(os.path.join(out_dir, "dataset.npz"), theta=dataset["theta"], tip=dataset["tip"])

    print("[TRAIN] Fitting quadratic equation mapping theta->tip...")
    coeffs, meta = fit_quadratic_model(dataset)

    np.savez(os.path.join(out_dir, "equation_coeffs.npz"), coeffs=coeffs, meta=json.dumps(meta))
    with open(os.path.join(out_dir, "equation_params.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "coeffs": coeffs.tolist()}, f, indent=2)

    print("[TRAIN] RL-like policy improvement loop...")
    rollouts = rl_like_policy_improvement(
        env,
        coeffs=coeffs,
        num_episodes=args.episodes,
        horizon=args.horizon,
        candidate_samples=args.candidates,
        rng=rng,
    )
    with open(os.path.join(out_dir, "rollouts.json"), "w", encoding="utf-8") as f:
        json.dump(rollouts, f, indent=2)

    print("[TRAIN] Done.")


if __name__ == "__main__":
    main()

