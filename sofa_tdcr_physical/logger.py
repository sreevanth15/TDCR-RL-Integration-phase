"""
Telemetry logging utilities for TDCR physical-grade simulation.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class LogPaths:
    jsonl_path: str
    state_path: Optional[str] = None


class LogWriter:
    def __init__(self, paths: LogPaths):
        self.paths = paths
        os.makedirs(os.path.dirname(self.paths.jsonl_path) or ".", exist_ok=True)
        self._f = open(self.paths.jsonl_path, "a", encoding="utf-8")
        self._jsonl_flush_every = 1
        self._write_count = 0

    def close(self):
        try:
            self._f.close()
        except Exception:
            pass

    def write_step(self, record: dict[str, Any], state: Optional[dict[str, Any]] = None):
        # JSONL rollout record
        self._f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._write_count += 1
        if self._write_count % self._jsonl_flush_every == 0:
            self._f.flush()

        # Latest state JSON (overwritten each step)
        if self.paths.state_path and state is not None:
            try:
                with open(self.paths.state_path, "w", encoding="utf-8") as sf:
                    json.dump(state, sf, ensure_ascii=False)
            except Exception:
                # Best-effort fallback: if dump fails for some rare value,
                # try writing a JSON string; otherwise keep previous state.
                try:
                    payload = json.dumps(state, ensure_ascii=False)
                    with open(self.paths.state_path, "w", encoding="utf-8") as sf:
                        sf.write(payload)
                except Exception:
                    pass


def utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

