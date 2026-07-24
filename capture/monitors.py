"""Monitor enumeration via MSS."""

from __future__ import annotations

from dataclasses import dataclass

import mss


@dataclass
class MonitorInfo:
    index: int
    left: int
    top: int
    width: int
    height: int
    name: str

    def label(self) -> str:
        return f"จอ {self.index}: {self.width}×{self.height} @ ({self.left},{self.top})"


def list_monitors() -> list[MonitorInfo]:
    result: list[MonitorInfo] = []
    with mss.mss() as sct:
        # monitors[0] is virtual all; 1..n are physical
        for i, mon in enumerate(sct.monitors):
            if i == 0:
                name = "ทั้งระบบ (virtual)"
            else:
                name = f"Monitor {i}"
            result.append(
                MonitorInfo(
                    index=i,
                    left=int(mon["left"]),
                    top=int(mon["top"]),
                    width=int(mon["width"]),
                    height=int(mon["height"]),
                    name=name,
                )
            )
    return result
