"""Small always-on-top toolbar shown just below the in-game overlay board.

Quick access to "apply Best Move" and "re-analyze" while you look at the real
game. IMPORTANT: the Best Move button only RECORDS your move into the program
(advances the assistant's board) — it never clicks in the game.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from capture.base import CaptureRegion


class OverlayToolbar(QWidget):
    apply_best_requested = Signal()
    apply_win_requested = Signal()  # play the PV2 win-focused move
    opponent_move_requested = Signal()  # toggle click-to-move on the overlay
    auto_cycle_requested = Signal()  # toggle the my-move ↔ opponent-move loop
    analyze_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("God Board Controls")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet(
            "QWidget#bar {background: rgba(20,22,30,236); border-radius:10px;}"
            "QLabel {color:#e8eaed;}"
            "QPushButton {padding:7px 14px; border-radius:7px; background:#2d3340;"
            " color:#e8eaed;}"
            "QPushButton#best {background:#2ecc71; color:#0b1020; font-weight:bold;}"
            "QPushButton#best:disabled {background:#3a4048; color:#9aa0a6;}"
            "QPushButton#win {background:#e67e22; color:#0b1020; font-weight:bold;}"
            "QPushButton#win:disabled {background:#3a4048; color:#9aa0a6;}"
            "QPushButton#opp:checked {background:#f1c40f; color:#0b1020;"
            " font-weight:bold;}"
            "QPushButton#auto:checked {background:#a29bfe; color:#0b1020;"
            " font-weight:bold;}"
        )

        bar = QWidget(self)
        bar.setObjectName("bar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)

        self.lbl_best = QLabel("Best: —")
        self.lbl_best.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.btn_best = QPushButton("เดินตาม Best Move")
        self.btn_best.setObjectName("best")
        self.btn_best.setToolTip(
            "บันทึกตาคุณตาม Stockfish (ในโปรแกรม) — คุณเดินในเกมเอง"
        )
        self.btn_best.clicked.connect(self.apply_best_requested)
        self.btn_win = QPushButton("⚔️ เอาชนะ")
        self.btn_win.setObjectName("win")
        self.btn_win.setToolTip("เดินตาที่เน้นเอาชนะ/บุก (PV2)")
        self.btn_win.clicked.connect(self.apply_win_requested)
        self.btn_opp = QPushButton("คลิกใส่ตาคู่แข่ง")
        self.btn_opp.setObjectName("opp")
        self.btn_opp.setCheckable(True)
        self.btn_opp.setToolTip(
            "เปิดโหมดคลิกบนกระดานในเกม แล้วคลิกต้นทาง→ปลายทางที่คู่แข่งเดิน"
        )
        self.btn_opp.clicked.connect(self.opponent_move_requested)
        self.btn_auto = QPushButton("วนอัตโนมัติ")
        self.btn_auto.setObjectName("auto")
        self.btn_auto.setCheckable(True)
        self.btn_auto.setToolTip(
            "เปิดโหมดวน: กด Best Move → สลับใส่ตาคู่แข่งให้เอง → เสร็จแล้ววนกลับ"
            " มาปุ่มเขียวเอง ไม่ต้องกดสลับเอง"
        )
        self.btn_auto.clicked.connect(self.auto_cycle_requested)
        self.btn_analyze = QPushButton("วิเคราะห์ใหม่")
        self.btn_analyze.clicked.connect(self.analyze_requested)

        lay.addWidget(self.lbl_best)
        lay.addWidget(self.btn_best)
        lay.addWidget(self.btn_win)
        lay.addWidget(self.btn_opp)
        lay.addWidget(self.btn_auto)
        lay.addWidget(self.btn_analyze)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(bar)
        self.adjustSize()
        self.hide()

    def set_best(self, text: str, enabled: bool) -> None:
        self.lbl_best.setText(text)
        self.btn_best.setEnabled(enabled)

    def set_win_enabled(self, enabled: bool) -> None:
        self.btn_win.setEnabled(enabled)

    def set_click_mode(self, on: bool) -> None:
        self.btn_opp.setChecked(on)
        self.btn_opp.setText("ใส่ตาคู่แข่ง: เปิด" if on else "คลิกใส่ตาคู่แข่ง")

    def set_auto_cycle(self, on: bool) -> None:
        self.btn_auto.setChecked(on)
        self.btn_auto.setText("วนอัตโนมัติ: เปิด" if on else "วนอัตโนมัติ")

    def place_under(self, region: CaptureRegion) -> None:
        """Center this bar just below the board region, clamped to the screen."""
        self.adjustSize()
        cx = int(region.left + region.width / 2 - self.width() / 2)
        y = int(region.top + region.height + 8)
        # Keep the whole bar on-screen (it grew wide; must not run off an edge).
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.screenAt(
            QPoint(int(region.left + region.width / 2), y)
        ) or QGuiApplication.primaryScreen()
        if screen is not None:
            g = screen.availableGeometry()
            cx = max(g.left(), min(cx, g.right() - self.width()))
            y = max(g.top(), min(y, g.bottom() - self.height()))
        self.move(max(0, cx), max(0, y))

    def _apply_no_activate(self) -> None:
        """Windows: receive clicks without stealing focus from the game."""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            if hwnd == 0:
                return
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x80
            user32 = ctypes.windll.user32
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                get_long = user32.GetWindowLongPtrW
                set_long = user32.SetWindowLongPtrW
            else:
                get_long = user32.GetWindowLongW
                set_long = user32.SetWindowLongW
            style = get_long(hwnd, GWL_EXSTYLE)
            style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            set_long(hwnd, GWL_EXSTYLE, style)
        except Exception:  # noqa: BLE001
            pass

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_no_activate()
