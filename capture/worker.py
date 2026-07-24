"""Background continuous screen capture worker."""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
from PySide6.QtCore import QMutex, QThread, Signal

from capture.base import CaptureRegion
from capture.mss_capture import MssCapture
from vision.perspective import PerspectiveCalibration

logger = logging.getLogger(__name__)


class CaptureWorker(QThread):
    """Grab frames at target FPS; emit ROI and warped images."""

    frame_ready = Signal(object, object)  # roi_bgr, warped_bgr
    error = Signal(str)
    status = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = False
        self._paused = False
        self._mutex = QMutex()
        self.monitor_id = 1
        self.region: Optional[CaptureRegion] = None
        self.calibration: Optional[PerspectiveCalibration] = None
        self.target_fps = 15.0

    def configure(
        self,
        monitor_id: int,
        region: CaptureRegion,
        calibration: PerspectiveCalibration,
        target_fps: float = 15.0,
    ) -> None:
        self._mutex.lock()
        self.monitor_id = monitor_id
        self.region = region
        self.calibration = calibration
        self.target_fps = max(5.0, min(30.0, target_fps))
        self._mutex.unlock()

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self.status.emit("paused" if paused else "capturing")

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        self._running = True
        cap: Optional[MssCapture] = None
        try:
            cap = MssCapture(self.monitor_id)
            self.status.emit("continuous capture started")
            interval = 1.0 / self.target_fps
            while self._running:
                t0 = time.perf_counter()
                if self._paused:
                    time.sleep(0.05)
                    continue
                self._mutex.lock()
                region = self.region
                cal = self.calibration
                mon = self.monitor_id
                self._mutex.unlock()
                if region is None or cal is None:
                    self.error.emit("ROI / Calibration not set")
                    time.sleep(0.5)
                    continue
                try:
                    if cap.monitor_index != mon:
                        cap.close()
                        cap = MssCapture(mon)
                    roi = cap.grab(region)
                    warped = cal.warp(roi)
                    self.frame_ready.emit(roi, warped)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("capture frame failed")
                    self.error.emit(f"Capture error: {exc}")
                    time.sleep(0.3)
                elapsed = time.perf_counter() - t0
                sleep_for = interval - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            if cap is not None:
                cap.close()
            self.status.emit("capture stopped")
