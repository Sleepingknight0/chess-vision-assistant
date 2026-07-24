"""Capture backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class CaptureRegion:
    left: int
    top: int
    width: int
    height: int

    def as_mss(self) -> dict:
        return {
            "left": int(self.left),
            "top": int(self.top),
            "width": int(self.width),
            "height": int(self.height),
        }

    def to_list(self) -> list[int]:
        return [self.left, self.top, self.width, self.height]

    @classmethod
    def from_list(cls, values: list[int] | tuple[int, ...]) -> CaptureRegion:
        return cls(int(values[0]), int(values[1]), int(values[2]), int(values[3]))


class CaptureBackend(ABC):
    @abstractmethod
    def grab(self, region: Optional[CaptureRegion] = None) -> np.ndarray:
        """Return BGR image (OpenCV order)."""

    @abstractmethod
    def close(self) -> None:
        ...
