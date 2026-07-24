"""Optional DXCam backend (Windows). Falls back if unavailable."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from capture.base import CaptureBackend, CaptureRegion


logger = logging.getLogger(__name__)


class DxcamCapture(CaptureBackend):
    def __init__(self, monitor_index: int = 0) -> None:
        self.monitor_index = max(0, monitor_index - 1)  # DXCam often 0-based physical
        self._camera = None
        try:
            import dxcam

            self._camera = dxcam.create(output_idx=self.monitor_index)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DXCam unavailable: %s", exc)
            raise

    def grab(self, region: Optional[CaptureRegion] = None) -> np.ndarray:
        if self._camera is None:
            raise RuntimeError("DXCam not initialized")
        if region is not None:
            frame = self._camera.grab(
                region=(
                    region.left,
                    region.top,
                    region.left + region.width,
                    region.top + region.height,
                )
            )
        else:
            frame = self._camera.grab()
        if frame is None:
            raise RuntimeError("DXCam returned empty frame")
        # DXCam is RGB
        import cv2

        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def close(self) -> None:
        self._camera = None


def try_create_dxcam(monitor_index: int = 1) -> Optional[DxcamCapture]:
    try:
        return DxcamCapture(monitor_index=monitor_index)
    except Exception:
        return None
