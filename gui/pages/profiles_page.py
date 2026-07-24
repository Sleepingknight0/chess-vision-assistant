"""Profiles management (Phase 1 basic)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from profiles.models import Profile

if TYPE_CHECKING:
    from gui.app_state import AppState


class ProfilesPage(QWidget):
    def __init__(self, state: AppState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state

        title = QLabel("Profiles")
        title.setObjectName("titleLabel")

        self.list = QListWidget()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("New Profile name")

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh)
        btn_load = QPushButton("Load selected")
        btn_load.clicked.connect(self.load_selected)
        btn_save = QPushButton("Save current")
        btn_save.setObjectName("primaryButton")
        btn_save.clicked.connect(self.save_current)
        btn_new = QPushButton("Create new from current")
        btn_new.clicked.connect(self.create_new)

        row = QHBoxLayout()
        row.addWidget(btn_refresh)
        row.addWidget(btn_load)
        row.addWidget(btn_save)
        row.addWidget(self.name_edit, 1)
        row.addWidget(btn_new)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(
            QLabel("Each Profile stores ROI, 4 corner points, side, orientation, engine, thresholds")
        )
        layout.addLayout(row)
        layout.addWidget(self.list, 1)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        for name in self.state.profiles.list_names():
            mark = " ★" if name == self.state.profile.name else ""
            self.list.addItem(name + mark)

    def load_selected(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        name = item.text().replace(" ★", "")
        try:
            profile = self.state.profiles.load(name)
            self.state.apply_profile(profile)
            self.state.config.set("active_profile", name)
            self.state.config.save()
            self.refresh()
            self.state.status_message.emit(f"Loaded Profile: {name}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Load failed", str(exc))

    def save_current(self) -> None:
        self.state.save_profile()
        self.refresh()

    def create_new(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Name empty", "Enter a Profile name first")
            return
        self.state.sync_profile_from_state()
        new_p = Profile.from_dict(self.state.profile.to_dict())
        new_p.name = name
        self.state.profile = new_p
        self.state.save_profile()
        self.refresh()
        self.state.status_message.emit(f"Created Profile: {name}")
