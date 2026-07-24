"""Team skin labels → Chess White / Black."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


DEFAULT_WHITE_LABEL = "Light Cherry"
DEFAULT_BLACK_LABEL = "Dark Cherry"


@dataclass
class TeamMapping:
    """Display names for sides; engine always uses White/Black."""

    white_label: str = DEFAULT_WHITE_LABEL
    black_label: str = DEFAULT_BLACK_LABEL
    user_is_white: bool = True
    # Optional BGR samples for future vision (not required Phase 1)
    white_sample_bgr: Optional[tuple[int, int, int]] = None
    black_sample_bgr: Optional[tuple[int, int, int]] = None

    def label_for_white(self) -> str:
        return self.white_label

    def label_for_black(self) -> str:
        return self.black_label

    def user_label(self) -> str:
        return self.white_label if self.user_is_white else self.black_label

    def opponent_label(self) -> str:
        return self.black_label if self.user_is_white else self.white_label

    def side_from_label(self, label: str) -> Optional[bool]:
        """Return True if white, False if black, None if unknown."""
        if label.strip().lower() == self.white_label.strip().lower():
            return True
        if label.strip().lower() == self.black_label.strip().lower():
            return False
        return None

    def swap_labels(self) -> None:
        self.white_label, self.black_label = self.black_label, self.white_label

    def to_dict(self) -> dict:
        return {
            "white": self.white_label,
            "black": self.black_label,
            "user_is_white": self.user_is_white,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TeamMapping:
        return cls(
            white_label=data.get("white", DEFAULT_WHITE_LABEL),
            black_label=data.get("black", DEFAULT_BLACK_LABEL),
            user_is_white=bool(data.get("user_is_white", True)),
        )


def default_team_mapping(user_is_white: bool = True) -> TeamMapping:
    return TeamMapping(user_is_white=user_is_white)
