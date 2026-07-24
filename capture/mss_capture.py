"""MSS screen capture (primary, DPI physical pixels)."""

from __future__ import annotations

import logging
from typing import Optional

import mss
import numpy as np

from capture.base import CaptureBackend, CaptureRegion
from capture.monitors import list_monitors


logger = logging.getLogger(__name__)


class MssCapture(CaptureBackend):
    def __init__(self, monitor_index: int = 1) -> None:
        self.monitor_index = monitor_index
        self._sct = mss.mss()

    def set_monitor(self, index: int) -> None:
        self.monitor_index = index

    def grab(self, region: Optional[CaptureRegion] = None) -> np.ndarray:
        if region is not None:
            shot = self._sct.grab(region.as_mss())
        else:
            mons = self._sct.monitors
            idx = self.monitor_index
            if idx < 0 or idx >= len(mons):
                idx = 1 if len(mons) > 1 else 0
            shot = self._sct.grab(mons[idx])
        # bgra → bgr
        img = np.array(shot, dtype=np.uint8)
        bgr = img[:, :, :3].copy()
        return bgr

    def grab_monitor(self) -> np.ndarray:
        return self.grab(None)

    def close(self) -> None:
        try:
            self._sct.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("mss close: %s", exc)
