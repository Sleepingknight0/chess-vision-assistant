"""Profile dataclasses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from board_detection.color_mapping import DEFAULT_BLACK_LABEL, DEFAULT_WHITE_LABEL


@dataclass
class EngineSettings:
    path: str = ""
    threads: int = 2
    skill_level: int = 20
    preset: str = "balanced"
    multipv: int = 3
    depth: int = 18
    movetime_ms: int = 750

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EngineSettings:
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class OverlaySettings:
    enabled: bool = False
    arrow_opacity: float = 0.85
    arrow_thickness: int = 4
    color_from: str = "#f1c40f"
    color_to: str = "#2ecc71"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OverlaySettings:
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class ThresholdSettings:
    confidence: float = 0.85
    debounce_ms: int = 500
    occupancy_diff: float = 0.12

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThresholdSettings:
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class Profile:
    name: str = "default"
    monitor_id: int = 1
    region: list[int] = field(default_factory=lambda: [0, 0, 800, 800])
    corners: list[list[float]] = field(default_factory=list)
    orientation_deg: int = 0
    my_pieces_at_bottom: bool = True
    user_is_white: bool = True
    team_labels: dict[str, str] = field(
        default_factory=lambda: {
            "white": DEFAULT_WHITE_LABEL,
            "black": DEFAULT_BLACK_LABEL,
        }
    )
    warped_size: int = 512
    engine: EngineSettings = field(default_factory=EngineSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    thresholds: ThresholdSettings = field(default_factory=ThresholdSettings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "monitor_id": self.monitor_id,
            "region": list(self.region),
            "corners": [list(c) for c in self.corners],
            "orientation_deg": self.orientation_deg,
            "my_pieces_at_bottom": self.my_pieces_at_bottom,
            "user_is_white": self.user_is_white,
            "team_labels": dict(self.team_labels),
            "warped_size": self.warped_size,
            "engine": self.engine.to_dict(),
            "overlay": self.overlay.to_dict(),
            "thresholds": self.thresholds.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        eng = EngineSettings.from_dict(data.get("engine") or {})
        ov = OverlaySettings.from_dict(data.get("overlay") or {})
        th = ThresholdSettings.from_dict(data.get("thresholds") or {})
        return cls(
            name=data.get("name", "default"),
            monitor_id=int(data.get("monitor_id", 1)),
            region=list(data.get("region") or [0, 0, 800, 800]),
            corners=[list(c) for c in (data.get("corners") or [])],
            orientation_deg=int(data.get("orientation_deg", 0)),
            my_pieces_at_bottom=bool(data.get("my_pieces_at_bottom", True)),
            user_is_white=bool(data.get("user_is_white", True)),
            team_labels=dict(
                data.get("team_labels")
                or {"white": DEFAULT_WHITE_LABEL, "black": DEFAULT_BLACK_LABEL}
            ),
            warped_size=int(data.get("warped_size", 512)),
            engine=eng,
            overlay=ov,
            thresholds=th,
        )


def default_roblox_profile() -> Profile:
    return Profile(name="roblox_light_dark_cherry")
