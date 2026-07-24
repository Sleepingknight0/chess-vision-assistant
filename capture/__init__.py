"""Screen capture backends."""

from capture.base import CaptureBackend, CaptureRegion
from capture.monitors import list_monitors
from capture.mss_capture import MssCapture

__all__ = ["CaptureBackend", "CaptureRegion", "MssCapture", "list_monitors"]
