"""Load/save profiles under %APPDATA%."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.paths import profiles_dir
from profiles.models import Profile, default_roblox_profile


logger = logging.getLogger(__name__)


class ProfileManager:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or profiles_dir()
        self.directory.mkdir(parents=True, exist_ok=True)

    def list_names(self) -> list[str]:
        names = [p.stem for p in self.directory.glob("*.json")]
        return sorted(names)

    def path_for(self, name: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return self.directory / f"{safe}.json"

    def save(self, profile: Profile) -> Path:
        path = self.path_for(profile.name)
        path.write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Saved profile %s → %s", profile.name, path)
        return path

    def load(self, name: str) -> Profile:
        path = self.path_for(name)
        if not path.is_file():
            raise FileNotFoundError(f"Profile not found: {name}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return Profile.from_dict(data)

    def ensure_default(self) -> Profile:
        names = self.list_names()
        if "roblox_light_dark_cherry" in names:
            return self.load("roblox_light_dark_cherry")
        if names:
            return self.load(names[0])
        profile = default_roblox_profile()
        self.save(profile)
        return profile
