"""Board calibration: monitor, ROI, 4 corners, warped grid preview."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from capture.base import CaptureRegion
from capture.monitors import list_monitors
from capture.mss_capture import MssCapture
from gui.widgets.capture_preview import CapturePreview
from gui.widgets.corner_editor import CornerEditor
from gui.widgets.region_selector import RegionSelector
from vision.grid import BoardGrid
from vision.perspective import PerspectiveCalibration, default_corners

if TYPE_CHECKING:
    from gui.app_state import AppState


class CalibrationPage(QWidget):
    def __init__(self, state: AppState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state
        self._selector: Optional[RegionSelector] = None

        title = QLabel("Board Calibration")
        title.setObjectName("titleLabel")

        self.monitor_combo = QComboBox()
        self._reload_monitors()
        self.monitor_combo.currentIndexChanged.connect(self._on_monitor)

        btn_region = QPushButton("เลือกพื้นที่กระดาน")
        btn_region.setObjectName("primaryButton")
        btn_region.clicked.connect(self.select_region)

        btn_snap = QPushButton("จับภาพ ROI")
        btn_snap.clicked.connect(self.grab_roi)

        self.warped_size = QSpinBox()
        self.warped_size.setRange(256, 1024)
        self.warped_size.setSingleStep(64)
        self.warped_size.setValue(state.calibration.warped_size)

        self.chk_grid = QCheckBox("แสดง Grid 8×8")
        self.chk_grid.setChecked(True)

        self.orient_combo = QComboBox()
        self.orient_combo.addItems(["0°", "90°", "180°", "270°"])
        self.orient_combo.setCurrentIndex(["0", "90", "180", "270"].index(str(state.orientation.rotation_deg)))

        self.side_combo = QComboBox()
        self.side_combo.addItems(
            [
                f"ฉันเล่นเป็น Light Cherry (White)",
                f"ฉันเล่นเป็น Dark Cherry (Black)",
            ]
        )
        self.side_combo.setCurrentIndex(0 if state.team.user_is_white else 1)

        self.bottom_combo = QComboBox()
        self.bottom_combo.addItems(["หมากของฉันอยู่ด้านล่างจอ", "หมากของฉันอยู่ด้านบนจอ"])
        self.bottom_combo.setCurrentIndex(0 if state.orientation.my_pieces_at_bottom else 1)

        self.white_name = QComboBox()
        self.white_name.setEditable(True)
        self.white_name.addItems(["Light Cherry", "Pink Team", "White"])
        self.white_name.setCurrentText(state.team.white_label)

        self.black_name = QComboBox()
        self.black_name.setEditable(True)
        self.black_name.addItems(["Dark Cherry", "Blue Team", "Black"])
        self.black_name.setCurrentText(state.team.black_label)

        btn_apply_setup = QPushButton("ใช้การตั้งค่าฝ่าย/มุม")
        btn_apply_setup.clicked.connect(self.apply_setup)

        btn_warp = QPushButton("อัปเดต Perspective Preview")
        btn_warp.setObjectName("primaryButton")
        btn_warp.clicked.connect(self.update_warp)

        btn_save = QPushButton("บันทึก Profile")
        btn_save.clicked.connect(self.save_profile)

        self.chk_auto_recal = QCheckBox("เปิด Auto Recalibration (ถ้าจับขอบกระดานได้มั่นใจ)")
        self.chk_auto_recal.setChecked(state.auto_recalibrate)
        self.chk_auto_recal.toggled.connect(self._on_auto_recal)

        self.corner_editor = CornerEditor()
        self.warp_preview = CapturePreview()

        if state.last_roi_bgr is not None:
            self.corner_editor.set_image(state.last_roi_bgr)
        if state.calibration.corners:
            self.corner_editor.set_corners(state.calibration.corners)

        self.corner_editor.corners_changed.connect(lambda _: self.update_warp())

        controls = QGroupBox("จอ / ROI / ฝ่าย")
        cl = QVBoxLayout(controls)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Monitor:"))
        row1.addWidget(self.monitor_combo, 1)
        row1.addWidget(btn_region)
        row1.addWidget(btn_snap)
        cl.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Warped size:"))
        row2.addWidget(self.warped_size)
        row2.addWidget(self.chk_grid)
        row2.addWidget(QLabel("หมุน:"))
        row2.addWidget(self.orient_combo)
        cl.addLayout(row2)
        row3 = QHBoxLayout()
        row3.addWidget(self.side_combo, 1)
        row3.addWidget(self.bottom_combo, 1)
        cl.addLayout(row3)
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("ชื่อฝ่าย White:"))
        row4.addWidget(self.white_name, 1)
        row4.addWidget(QLabel("ชื่อฝ่าย Black:"))
        row4.addWidget(self.black_name, 1)
        row4.addWidget(btn_apply_setup)
        cl.addLayout(row4)
        row5 = QHBoxLayout()
        row5.addWidget(btn_warp)
        row5.addWidget(btn_save)
        cl.addLayout(row5)
        cl.addWidget(self.chk_auto_recal)

        previews = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("ปรับ 4 มุมบนภาพ ROI"))
        left.addWidget(self.corner_editor, 1)
        right = QVBoxLayout()
        right.addWidget(QLabel("Preview หลัง Perspective + Grid 64 ช่อง"))
        right.addWidget(self.warp_preview, 1)
        previews.addLayout(left, 1)
        previews.addLayout(right, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(controls)
        layout.addLayout(previews, 1)

        hint = QLabel(
            "ลากจุดสีทั้ง 4 ให้ตรงมุมกระดานจริง (ซ้ายบน → ขวาบน → ขวาล่าง → ซ้ายล่าง) "
            "จากนั้นกดอัปเดต Preview — ตัด UI Roblox และท้องฟ้าออกจาก ROI"
        )
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def _reload_monitors(self) -> None:
        self.monitor_combo.clear()
        for m in list_monitors():
            self.monitor_combo.addItem(m.label(), m.index)
        idx = self.monitor_combo.findData(self.state.monitor_id)
        if idx >= 0:
            self.monitor_combo.setCurrentIndex(idx)

    def _on_monitor(self) -> None:
        data = self.monitor_combo.currentData()
        if data is not None:
            self.state.monitor_id = int(data)

    def select_region(self) -> None:
        screens = QGuiApplication.screens()
        mon_idx = self.state.monitor_id
        if mon_idx <= 0:
            geo = screens[0].geometry()
            for s in screens:
                geo = geo.united(s.geometry())
        else:
            si = mon_idx - 1
            if si < 0 or si >= len(screens):
                si = 0
            geo = screens[si].geometry()

        self._selector = RegionSelector(geo)
        self._selector.region_selected.connect(self._on_region)
        self._selector.cancelled.connect(lambda: self.state.status_message.emit("ยกเลิกเลือกพื้นที่"))
        self._selector.show()

    def _on_region(self, region: CaptureRegion) -> None:
        self.state.region = region
        self.state.status_message.emit(
            f"เลือกพื้นที่ {region.width}×{region.height} @ ({region.left},{region.top})"
        )
        self.grab_roi()

    def grab_roi(self) -> None:
        if self.state.region is None:
            QMessageBox.information(self, "ยังไม่มี ROI", "กด «เลือกพื้นที่กระดาน» ก่อน")
            return
        try:
            cap = MssCapture(self.state.monitor_id)
            img = cap.grab(self.state.region)
            cap.close()
            self.state.last_roi_bgr = img
            h, w = img.shape[:2]
            if not self.corner_editor.corners() or len(self.corner_editor.corners()) != 4:
                self.corner_editor.set_corners(default_corners(float(w), float(h)))
            self.corner_editor.set_image(img)
            # If corners out of bounds, reset
            corners = self.corner_editor.corners()
            if any(x < 0 or y < 0 or x >= w or y >= h for x, y in corners):
                self.corner_editor.set_corners(default_corners(float(w), float(h)))
            self.update_warp()
            self.state.status_message.emit("จับภาพ ROI สำเร็จ")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "จับภาพไม่สำเร็จ", str(exc))

    def apply_setup(self) -> None:
        self.state.team.user_is_white = self.side_combo.currentIndex() == 0
        self.state.team.white_label = self.white_name.currentText().strip() or "Light Cherry"
        self.state.team.black_label = self.black_name.currentText().strip() or "Dark Cherry"
        rot = [0, 90, 180, 270][self.orient_combo.currentIndex()]
        self.state.orientation.rotation_deg = rot
        self.state.orientation.my_pieces_at_bottom = self.bottom_combo.currentIndex() == 0
        self.state.orientation.user_is_white = self.state.team.user_is_white
        self.state.profile_changed.emit()
        self.state.board_changed.emit()
        self.state.status_message.emit(
            f"ฝ่าย: {self.state.team.user_label()} / หมุน {rot}°"
        )

    def update_warp(self) -> None:
        if self.state.last_roi_bgr is None:
            return
        size = self.warped_size.value()
        corners = self.corner_editor.corners()
        if len(corners) != 4:
            return
        cal = PerspectiveCalibration(corners=corners, warped_size=size)
        self.state.calibration = cal
        try:
            warped = cal.warp(self.state.last_roi_bgr)
            self.state.last_warped_bgr = warped
            grid = BoardGrid(size=size, orientation=self.state.orientation)
            self.warp_preview.set_grid(grid)
            self.warp_preview.set_show_grid(self.chk_grid.isChecked())
            self.warp_preview.set_image(warped)
            self.state.capture_changed.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Perspective ล้มเหลว", str(exc))

    def _on_auto_recal(self, on: bool) -> None:
        self.state.auto_recalibrate = on
        self.state.detection.auto_recalibrate = on

    def save_profile(self) -> None:
        self.apply_setup()
        self.update_warp()
        self.state.auto_recalibrate = self.chk_auto_recal.isChecked()
        self.state.save_profile()
        # Sync detection orientation after calibration
        self.state.refresh_detection_config()
        self.state.detection.reset(self.state.board_state.board)
        if self.state.last_warped_bgr is not None:
            self.state.detection.set_reference_frame(self.state.last_warped_bgr)
        self.state.update_overlay_geometry()
        QMessageBox.information(self, "บันทึกแล้ว", f"บันทึก Profile «{self.state.profile.name}» แล้ว")
