"""Frame stability / debounce helpers for auto move detection."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class StabilityGate:
    """Detect motion then wait for stillness before confirming a board change."""

    debounce_ms: int = 350
    motion_threshold: float = 2.8  # mean abs gray diff (sensitive for Roblox)
    _stable_since: float | None = field(default=None, repr=False)
    _last_gray: np.ndarray | None = field(default=None, repr=False)
    _pending_change: bool = False
    _motion_peak: float = 0.0

    def reset(self) -> None:
        self._stable_since = None
        self._last_gray = None
        self._pending_change = False
        self._motion_peak = 0.0

    def update(self, warped_bgr: np.ndarray) -> tuple[bool, float]:
        """Return (is_stable_long_enough, motion_score)."""
        gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.resize(gray, (96, 96))
        motion = 0.0
        if self._last_gray is not None:
            motion = float(np.mean(cv2.absdiff(gray, self._last_gray)))
        self._last_gray = gray

        now = time.monotonic()
        if motion >= self.motion_threshold:
            self._stable_since = None
            self._pending_change = True
            self._motion_peak = max(self._motion_peak, motion)
            return False, motion

        if self._stable_since is None:
            self._stable_since = now
        elapsed_ms = (now - self._stable_since) * 1000.0
        stable = elapsed_ms >= self.debounce_ms
        return stable, motion

    def consume_pending(self) -> bool:
        """True if there was motion then became stable (ready to evaluate move)."""
        if self._pending_change:
            self._pending_change = False
            self._motion_peak = 0.0
            return True
        return False

    @property
    def has_pending(self) -> bool:
        return self._pending_change
