"""Settings and hotkeys."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.paths import config_path, logs_dir, user_data_dir

if TYPE_CHECKING:
    from gui.app_state import AppState


class SettingsPage(QWidget):
    def __init__(self, state: AppState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state

        title = QLabel("Settings")
        title.setObjectName("titleLabel")

        hotkeys = state.config.get("hotkeys") or {}
        self.edits: dict[str, QLineEdit] = {}
        form = QFormLayout()
        labels = {
            "toggle_capture": "เริ่ม/หยุดจับภาพ (F8)",
            "analyze": "วิเคราะห์ (F9)",
            "toggle_overlay": "เปิด/ปิด Overlay (F10)",
            "undo_detection": "ย้อนการตรวจจับ (Ctrl+Z)",
            "recalibrate": "Calibrate ใหม่ (Ctrl+Shift+C)",
        }
        for key, lab in labels.items():
            edit = QLineEdit(str(hotkeys.get(key, "")))
            self.edits[key] = edit
            form.addRow(lab, edit)

        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.5, 0.99)
        self.conf_spin.setSingleStep(0.05)
        self.conf_spin.setValue(state.profile.thresholds.confidence)
        self.debounce = QSpinBox()
        self.debounce.setRange(300, 700)
        self.debounce.setSuffix(" ms")
        self.debounce.setValue(state.profile.thresholds.debounce_ms)
        form.addRow("Confidence threshold", self.conf_spin)
        form.addRow("Debounce (นิ่งก่อนยืนยัน)", self.debounce)

        self.chk_auto_recal = QCheckBox("Auto Recalibration (เมื่อตรวจขอบกระดานได้มั่นใจ)")
        self.chk_auto_recal.setChecked(state.auto_recalibrate)
        self.chk_auto_analyze = QCheckBox("วิเคราะห์อัตโนมัติเฉพาะตาของผู้ใช้")
        self.chk_auto_analyze.setChecked(state.auto_analyze_on_user_turn)

        self.overlay_opacity = QDoubleSpinBox()
        self.overlay_opacity.setRange(0.2, 1.0)
        self.overlay_opacity.setSingleStep(0.05)
        self.overlay_opacity.setValue(state.profile.overlay.arrow_opacity)
        self.overlay_thick = QSpinBox()
        self.overlay_thick.setRange(1, 12)
        self.overlay_thick.setValue(state.profile.overlay.arrow_thickness)
        form.addRow("Overlay ความโปร่งใสลูกศร", self.overlay_opacity)
        form.addRow("Overlay ความหนาลูกศร", self.overlay_thick)

        btn_save = QPushButton("บันทึก Settings")
        btn_save.setObjectName("primaryButton")
        btn_save.clicked.connect(self.save)

        box = QGroupBox("Hotkeys & Detection")
        bl = QVBoxLayout(box)
        bl.addLayout(form)
        bl.addWidget(self.chk_auto_recal)
        bl.addWidget(self.chk_auto_analyze)
        bl.addWidget(btn_save)

        paths = QGroupBox("ที่เก็บข้อมูล (local)")
        pl = QVBoxLayout(paths)
        pl.addWidget(QLabel(f"User data: {user_data_dir()}"))
        pl.addWidget(QLabel(f"Config: {config_path()}"))
        pl.addWidget(QLabel(f"Logs: {logs_dir()}"))

        ethics = QGroupBox("ขอบเขตการใช้งาน")
        el = QVBoxLayout(ethics)
        el.addWidget(
            QLabel(
                "• ใช้สำหรับฝึกซ้อม เล่นส่วนตัว เล่นกับบอท และวิเคราะห์เกมที่อนุญาต\n"
                "• ห้ามควบคุมเมาส์ / เดินหมากอัตโนมัติ / หลบระบบป้องกันการโกง\n"
                "• ไม่อัปโหลดภาพหน้าจอหรือข้อมูลเกมออกจากเครื่อง\n"
                "• Overlay แสดงผลอย่างเดียว — click-through ไม่บังเกม"
            )
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(box)
        layout.addWidget(paths)
        layout.addWidget(ethics)
        layout.addStretch(1)

    def save(self) -> None:
        hk = {k: e.text().strip() for k, e in self.edits.items()}
        self.state.config.set("hotkeys", hk)
        self.state.profile.thresholds.confidence = self.conf_spin.value()
        self.state.profile.thresholds.debounce_ms = self.debounce.value()
        self.state.auto_recalibrate = self.chk_auto_recal.isChecked()
        self.state.auto_analyze_on_user_turn = self.chk_auto_analyze.isChecked()
        self.state.profile.overlay.arrow_opacity = self.overlay_opacity.value()
        self.state.profile.overlay.arrow_thickness = self.overlay_thick.value()
        self.state.overlay.set_style(
            self.overlay_opacity.value(), self.overlay_thick.value()
        )
        self.state.refresh_detection_config()
        self.state.config.set("auto_recalibrate", self.state.auto_recalibrate)
        self.state.config.save()
        self.state.save_profile()
        self.state.status_message.emit("บันทึก Settings แล้ว")
