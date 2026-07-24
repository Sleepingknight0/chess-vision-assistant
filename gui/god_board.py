"""God-tier side-panel chess board — no vision, manual opponent moves + Stockfish.

Layout (always):
  - Your pieces at the BOTTOM of the board
  - Opponent at the TOP
You enter opponent moves by hand. Stockfish analyzes YOUR turns brutally hard.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import chess
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.paths import config_path, user_data_dir
from board_detection.orientation import BoardOrientation
from capture.base import CaptureRegion
from chess_core.board_state import BoardState
from chess_engine.analysis_types import AnalysisLine, AnalysisResult, EvalScore
from chess_engine.opening_book import OpeningBook
from chess_engine.ponder import ContinuousAnalyzer
from chess_engine.stockfish_engine import PRESETS, StockfishEngine
from gui.widgets.board_view import BoardView
from gui.widgets.position_editor import PositionEditorWidget
from overlay.overlay_window import OverlayWindow
from overlay.setup_frame import OverlaySetupWindow
from overlay.toolbar import OverlayToolbar
from storage.config_store import sanitize_config_dict
from vision.grid import BoardGrid
from vision.perspective import PerspectiveCalibration

logger = logging.getLogger(__name__)


def _merge_user_config(**updates) -> None:
    """Update keys in user config.json without ever writing plaintext API keys."""
    import json

    cfg = config_path()
    data: dict = {}
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {}
    data.update(updates)
    data = sanitize_config_dict(data)
    user_data_dir().mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")


class DeepAnalyzeWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        engine: StockfishEngine,
        fen: str,
        movetime_ms: int,
        multipv: int,
        threads: int,
        hash_mb: int = 512,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.fen = fen
        self.movetime_ms = movetime_ms
        self.multipv = multipv
        self.threads = threads
        self.hash_mb = hash_mb

    def run(self) -> None:
        try:
            result = self.engine.analyze(
                self.fen,
                movetime_ms=self.movetime_ms,
                multipv=self.multipv,
                threads=self.threads,
                skill_level=20,
                hash_mb=self.hash_mb,
            )
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class GodBoardWindow(QMainWindow):
    """Compact always-on-top chess coach board."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Chess Vision Assistant — Stockfish")
        self.resize(460, 820)
        self.setMinimumWidth(380)
        # Side of screen, stays on top
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.user_is_white = True
        self.board_state = BoardState.standard()
        self.engine = StockfishEngine(self._default_stockfish())
        self.engine.set_syzygy_path(self._load_syzygy_path())
        self.book = OpeningBook(self._default_book())
        self._click_from: Optional[str] = None
        self._last_analysis: Optional[AnalysisResult] = None
        self._predicted_opp_move: Optional[str] = None  # for pondering
        self._win_move: Optional[str] = None  # parallel "win-focused" move (PV2)
        self.movetime_ms = 3000  # think budget per move, then STOP (no CPU peg)
        self.multipv = 3
        self.depth_cap = 48  # safety cap; time is the real bound
        # Leave a core free so the machine stays responsive. Large hash keeps the
        # transposition table warm across moves (helps the pondering design).
        self.threads = max(2, (os.cpu_count() or 4) - 1)
        self.hash_mb = 1024

        # Bounded/pondering analyzer — thinks hard briefly then rests
        self._analyzer = ContinuousAnalyzer(self.engine)
        self._analyzer.updated.connect(self._on_analysis)
        self._analyzer.depth_info.connect(self._on_depth)
        self._analyzer.start()

        # In-game overlay (arrows over the real game board; no capture)
        self.overlay = OverlayWindow()
        self.overlay.square_clicked.connect(self._on_square)
        self.overlay_toolbar = OverlayToolbar()
        self.overlay_toolbar.apply_best_requested.connect(self.apply_best)
        self.overlay_toolbar.apply_win_requested.connect(self.apply_win)
        self.overlay_toolbar.opponent_move_requested.connect(self.toggle_overlay_click)
        self.overlay_toolbar.auto_cycle_requested.connect(self.toggle_auto_cycle)
        self.overlay_toolbar.analyze_requested.connect(self.analyze_now)
        self._overlay_click = False
        self._auto_cycle = False
        self._overlay_setup: Optional[OverlaySetupWindow] = None
        self._overlay_corners_abs: Optional[list[tuple[float, float]]] = (
            self._load_overlay_corners()
        )

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        title = QLabel("Chess Vision Assistant")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        # ── Tab: Play ─────────────────────────────────────────────
        play = QWidget()
        layout = QVBoxLayout(play)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        sub = QLabel(
            "คุณอยู่ล่างเสมอ · คู่แข่งอยู่บน\n"
            "ใส่การเดินคู่แข่งเอง · เดินตามลูกศร Stockfish"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color:#9aa0a6;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Side select
        side_row = QHBoxLayout()
        side_row.addWidget(QLabel("ฉันเล่นเป็น:"))
        self.side_combo = QComboBox()
        self.side_combo.addItem("White (Light Cherry) — ล่าง", True)
        self.side_combo.addItem("Black (Dark Cherry) — ล่าง", False)
        self.side_combo.currentIndexChanged.connect(self._on_side_changed)
        side_row.addWidget(self.side_combo, 1)
        layout.addLayout(side_row)

        # Board
        self.board_view = BoardView()
        self.board_view.setMinimumHeight(320)
        self.board_view.square_clicked.connect(self._on_square)
        layout.addWidget(self.board_view, 1)

        self.lbl_turn = QLabel()
        self.lbl_turn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_turn.setWordWrap(True)
        layout.addWidget(self.lbl_turn)

        self.lbl_status = QLabel("พร้อม")
        self.lbl_status.setStyleSheet("color:#a29bfe;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        self.lbl_depth = QLabel("")
        self.lbl_depth.setStyleSheet("color:#2ecc71; font-weight:bold;")
        layout.addWidget(self.lbl_depth)

        # Engine suggestion box
        eng_box = QGroupBox("Stockfish (แรง)")
        el = QVBoxLayout(eng_box)
        self.lbl_best = QLabel("🔥 แรงสุด: —")
        self.lbl_best.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_best.setStyleSheet("color:#2ecc71;")
        self.lbl_best.setWordWrap(True)
        self.lbl_win = QLabel("⚔️ เอาชนะ: —")
        self.lbl_win.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_win.setStyleSheet("color:#e67e22;")
        self.lbl_win.setWordWrap(True)
        self.lbl_eval = QLabel("Eval: —")
        self.lbl_lines = QLabel("")
        self.lbl_lines.setWordWrap(True)
        self.lbl_lines.setStyleSheet("color:#9aa0a6;")
        el.addWidget(self.lbl_best)
        el.addWidget(self.lbl_win)
        el.addWidget(self.lbl_eval)
        el.addWidget(self.lbl_lines)

        btn_apply_best = QPushButton("🔥 เดินแรงสุด")
        btn_apply_best.setObjectName("primaryButton")
        btn_apply_best.setToolTip("เดินตาที่แรง/ถูกต้องที่สุด ไร้ที่ติ (PV1)")
        btn_apply_best.clicked.connect(self.apply_best)
        self.btn_apply_win = QPushButton("⚔️ เดินเอาชนะ")
        self.btn_apply_win.setStyleSheet(
            "background:#e67e22; color:#0b1020; font-weight:bold;"
        )
        self.btn_apply_win.setToolTip("เดินตาที่เน้นเอาชนะ/กดดันคู่แข่ง (PV2)")
        self.btn_apply_win.clicked.connect(self.apply_win)
        btn_analyze = QPushButton("วิเคราะห์ใหม่")
        btn_analyze.clicked.connect(self.analyze_now)
        row_e = QHBoxLayout()
        row_e.addWidget(btn_apply_best, 1)
        row_e.addWidget(self.btn_apply_win, 1)
        el.addLayout(row_e)
        el.addWidget(btn_analyze)
        layout.addWidget(eng_box)

        # Manual UCI
        uci_row = QHBoxLayout()
        self.uci_edit = QLineEdit()
        self.uci_edit.setPlaceholderText("ใส่การเดิน: e2e4 / Nf3 / O-O")
        self.uci_edit.returnPressed.connect(self.apply_text_move)
        btn_go = QPushButton("ใส่")
        btn_go.clicked.connect(self.apply_text_move)
        uci_row.addWidget(self.uci_edit, 1)
        uci_row.addWidget(btn_go)
        layout.addLayout(uci_row)

        # History
        layout.addWidget(QLabel("ประวัติ"))
        self.hist = QListWidget()
        self.hist.setMaximumHeight(90)
        layout.addWidget(self.hist)

        # Controls
        ctrl = QHBoxLayout()
        btn_undo = QPushButton("Undo")
        btn_undo.clicked.connect(self.undo)
        btn_new = QPushButton("เกมใหม่")
        btn_new.clicked.connect(self.new_game)
        btn_setup = QPushButton("ตั้งค่าหมาก…")
        btn_setup.setToolTip("ไปหน้าแก้ตำแหน่งเมื่อหมากเพี้ยน")
        btn_setup.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        self.chk_top = QCheckBox("Always on top")
        self.chk_top.setChecked(True)
        self.chk_top.toggled.connect(self._toggle_on_top)
        ctrl.addWidget(btn_undo)
        ctrl.addWidget(btn_new)
        ctrl.addWidget(btn_setup)
        ctrl.addWidget(self.chk_top)
        layout.addLayout(ctrl)

        # Overlay controls
        ov_row = QHBoxLayout()
        self.btn_ov = QPushButton("Overlay: ปิด")
        self.btn_ov.setToolTip("แสดงลูกศร Best Move ซ้อนบนกระดานในเกมจริง")
        self.btn_ov.clicked.connect(self.toggle_overlay)
        btn_ov_pos = QPushButton("ตั้งตำแหน่ง Overlay")
        btn_ov_pos.setToolTip("ลากกรอบ 4 มุมให้ตรงกระดานในเกม")
        btn_ov_pos.clicked.connect(self.setup_overlay)
        self.btn_ov_click = QPushButton("คลิก Overlay: ปิด")
        self.btn_ov_click.setToolTip(
            "เปิด = คลิกช่องบนเกมจริงเพื่อบันทึกการเดิน (คลิกจะไม่ทะลุไปเกมชั่วคราว)"
        )
        self.btn_ov_click.clicked.connect(self.toggle_overlay_click)
        ov_row.addWidget(self.btn_ov, 1)
        ov_row.addWidget(btn_ov_pos, 1)
        ov_row.addWidget(self.btn_ov_click, 1)
        layout.addLayout(ov_row)

        # Engine settings — row 1: compute options
        set_row = QHBoxLayout()
        set_row.addWidget(QLabel("คิด(ms)"))
        self.spin_time = QSpinBox()
        self.spin_time.setRange(200, 30000)
        self.spin_time.setValue(self.movetime_ms)
        self.spin_time.setSingleStep(500)
        self.spin_time.valueChanged.connect(lambda v: setattr(self, "movetime_ms", v))
        set_row.addWidget(self.spin_time, 1)
        set_row.addWidget(QLabel("PV"))
        self.spin_pv = QSpinBox()
        self.spin_pv.setRange(1, 5)
        self.spin_pv.setValue(self.multipv)
        self.spin_pv.valueChanged.connect(lambda v: setattr(self, "multipv", v))
        set_row.addWidget(self.spin_pv)
        self.chk_max = QCheckBox("แรงสุด")
        self.chk_max.setChecked(True)
        self.chk_max.setToolTip(
            "คิดแบบ PV1 (แรงที่สุด/ลึกสุดต่อการเดินหลัก) — ปิดถ้าอยากเห็น 3 ทางเลือก"
        )
        self.chk_max.toggled.connect(lambda _: self.analyze_now())
        set_row.addWidget(self.chk_max)
        self.chk_winmore = QCheckBox("คู่ขนาน")
        self.chk_winmore.setChecked(True)
        self.chk_winmore.setToolTip(
            "แสดง 2 ตาพร้อมกัน: 🔥 แรงสุด (PV1 ไร้ที่ติ) และ ⚔️ เอาชนะ (PV2 บุก/"
            "กดดันคู่แข่ง) — เลือกเดินได้เอง"
        )
        self.chk_winmore.toggled.connect(lambda _: self._maybe_analyze())
        set_row.addWidget(self.chk_winmore)
        layout.addLayout(set_row)

        # Engine settings — row 2: opening book / engine / tablebase files
        res_row = QHBoxLayout()
        self.chk_book = QCheckBox("ตำรา")
        self.chk_book.setChecked(True)
        self.chk_book.setToolTip(
            "เปิด = เดินตามตำราเปิดเกม (ไวและไร้ที่ติ) — ถ้าออกนอกตำราเอนจินคิดเอง"
        )
        self.chk_book.toggled.connect(self._on_book_toggled)
        res_row.addWidget(self.chk_book)
        btn_book = QPushButton("Book…")
        btn_book.setToolTip("เลือกไฟล์ opening book (.bin)")
        btn_book.clicked.connect(self.pick_book)
        res_row.addWidget(btn_book, 1)
        btn_sf = QPushButton("Stockfish…")
        btn_sf.clicked.connect(self.pick_stockfish)
        res_row.addWidget(btn_sf, 1)
        self.btn_tb = QPushButton("Tablebase…")
        self.btn_tb.setToolTip(
            "เลือกโฟลเดอร์ Syzygy tablebase → เล่นเกมท้ายเป๊ะแบบสมบูรณ์แบบ (ไร้พลาด)"
        )
        self.btn_tb.clicked.connect(self.pick_tablebase)
        res_row.addWidget(self.btn_tb, 1)
        layout.addLayout(res_row)

        self.lbl_tb = QLabel("")
        self.lbl_tb.setStyleSheet("color:#9aa0a6;")
        self.lbl_tb.setWordWrap(True)
        layout.addWidget(self.lbl_tb)

        self.lbl_click = QLabel("คลิกช่องต้นทาง → ปลายทาง เพื่อบันทึกการเดิน")
        self.lbl_click.setStyleSheet("color:#9aa0a6;")
        self.lbl_click.setWordWrap(True)
        layout.addWidget(self.lbl_click)

        # Wrap the play tab in a scroll area so controls never overflow the frame
        play_scroll = QScrollArea()
        play_scroll.setWidgetResizable(True)
        play_scroll.setWidget(play)
        play_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.tabs.addTab(play_scroll, "เล่น")

        # ── Tab: Setup position ───────────────────────────────────
        setup = QWidget()
        setup_l = QVBoxLayout(setup)
        setup_l.setContentsMargins(4, 4, 4, 4)
        hint = QLabel(
            "เมื่อเดินผิดจนหมากเพี้ยนทั้งกระดาน — มาหน้านี้\n"
            "เลือกชนิดหมาก แล้วคลิกช่องเพื่อวาง / เลือกลบหมากเพื่อลบ\n"
            "ตั้งตาเดิน แล้วกด «ใช้ตำแหน่งนี้»"
        )
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#9aa0a6;")
        setup_l.addWidget(hint)

        self.pos_editor = PositionEditorWidget()
        setup_l.addWidget(self.pos_editor, 1)

        fen_row = QHBoxLayout()
        self.fen_edit = QLineEdit()
        self.fen_edit.setPlaceholderText("วาง FEN ที่นี่ แล้วกด ใช้ FEN")
        btn_fen = QPushButton("ใช้ FEN")
        btn_fen.clicked.connect(self._apply_fen_from_edit)
        fen_row.addWidget(self.fen_edit, 1)
        fen_row.addWidget(btn_fen)
        setup_l.addLayout(fen_row)

        apply_row = QHBoxLayout()
        btn_load_cur = QPushButton("โหลดตำแหน่งปัจจุบัน")
        btn_load_cur.clicked.connect(self._load_current_into_editor)
        btn_apply_pos = QPushButton("ใช้ตำแหน่งนี้")
        btn_apply_pos.setObjectName("primaryButton")
        btn_apply_pos.setToolTip("แทนที่กระดานเล่นด้วยตำแหน่งที่แก้ — ล้างประวัติเดิน")
        btn_apply_pos.clicked.connect(self._apply_editor_position)
        btn_back_play = QPushButton("กลับไปเล่น")
        btn_back_play.clicked.connect(lambda: self.tabs.setCurrentIndex(0))
        apply_row.addWidget(btn_load_cur)
        apply_row.addWidget(btn_apply_pos, 2)
        apply_row.addWidget(btn_back_play)
        setup_l.addLayout(apply_row)

        self.lbl_setup = QLabel("")
        self.lbl_setup.setStyleSheet("color:#a29bfe;")
        self.lbl_setup.setWordWrap(True)
        setup_l.addWidget(self.lbl_setup)

        self.tabs.addTab(setup, "ตั้งค่าหมาก")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._apply_orientation()
        if self._overlay_corners_abs:
            self._apply_overlay_geometry()  # ready — one click on Overlay to show
        self._refresh_all()
        self._validate_engine()
        self._refresh_tb_label()
        # If white to move and user is white → analyze
        self._maybe_analyze()

        # Park on right side of primary screen
        self._dock_right()

    def _default_stockfish(self) -> str:
        candidates = [
            Path(__file__).resolve().parent.parent / "engines" / "stockfish.exe",
            Path(r"C:\Users\BlueWhaleX\Downloads\Chess\engines\stockfish.exe"),
        ]
        for p in candidates:
            if p.is_file():
                return str(p)
        # config
        cfg = config_path()
        if cfg.is_file():
            try:
                import json

                data = json.loads(cfg.read_text(encoding="utf-8"))
                sp = data.get("stockfish_path") or ""
                if sp and Path(sp).is_file():
                    return sp
            except Exception:
                pass
        return ""

    def _default_book(self) -> str:
        cfg = config_path()
        if cfg.is_file():
            try:
                import json

                data = json.loads(cfg.read_text(encoding="utf-8"))
                bp = str(data.get("book_path") or "")
                if bp and Path(bp).is_file():
                    return bp
            except Exception:  # noqa: BLE001
                pass
        bundled = Path(__file__).resolve().parent.parent / "engines" / "books" / "komodo.bin"
        return str(bundled) if bundled.is_file() else ""

    def _dock_right(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        w, h = self.width(), min(self.height(), geo.height() - 40)
        self.setGeometry(geo.right() - w - 12, geo.top() + 20, w, h)

    def _toggle_on_top(self, on: bool) -> None:
        flags = self.windowFlags()
        if on:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _apply_orientation(self) -> None:
        # User always at bottom
        ori = BoardOrientation(
            rotation_deg=0,
            my_pieces_at_bottom=True,
            user_is_white=self.user_is_white,
        )
        self.board_view.set_orientation(ori)
        if hasattr(self, "pos_editor"):
            self.pos_editor.board_view.set_orientation(ori)

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            # Entering setup: sync editor from live board
            self._load_current_into_editor()

    def _load_current_into_editor(self) -> None:
        fen = self.board_state.fen()
        self.pos_editor.set_fen(fen)
        self.fen_edit.setText(fen)
        self._apply_orientation()
        self.lbl_setup.setText("โหลดตำแหน่งจากหน้าเล่นแล้ว — แก้ได้เลย")

    def _apply_fen_from_edit(self) -> None:
        text = self.fen_edit.text().strip()
        if not text:
            return
        try:
            chess.Board(text)
        except ValueError as exc:
            QMessageBox.warning(self, "FEN ไม่ถูกต้อง", str(exc))
            return
        self.pos_editor.set_fen(text)
        self.lbl_setup.setText("ใส่ FEN ในตัวแก้แล้ว — กด «ใช้ตำแหน่งนี้» เพื่อยืนยัน")

    def _apply_editor_position(self) -> None:
        """Replace live board with edited position (clears move history)."""
        fen = self.pos_editor.fen()
        try:
            board = chess.Board(fen)
        except ValueError as exc:
            QMessageBox.warning(self, "ตำแหน่งใช้ไม่ได้", str(exc))
            return
        # Soft check: both kings present (common mess after bad edits)
        if board.king(chess.WHITE) is None or board.king(chess.BLACK) is None:
            ans = QMessageBox.question(
                self,
                "ไม่มี King ครบ",
                "กระดานไม่มี King ขาวหรือดำครบ — ยังใช้ตำแหน่งนี้ต่อไหม?",
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
        self.board_state.set_fen(fen)
        self._click_from = None
        self._last_analysis = None
        self.board_view.clear_arrows()
        self._clear_reco()
        self.fen_edit.setText(fen)
        self._refresh_all()
        self.tabs.setCurrentIndex(0)
        self.lbl_status.setText("ใช้ตำแหน่งที่แก้แล้ว — ประวัติเดินถูกล้าง")
        self.lbl_setup.setText("ใช้ตำแหน่งนี้แล้ว")
        self._maybe_analyze()

    def _on_side_changed(self) -> None:
        self.user_is_white = bool(self.side_combo.currentData())
        self._apply_orientation()
        self._apply_overlay_geometry()  # grid orientation follows my side
        self._update_overlay()
        self._refresh_all()
        self._maybe_analyze()

    def _is_user_turn(self) -> bool:
        return self.board_state.is_user_turn(self.user_is_white)

    def _refresh_all(self) -> None:
        self.board_view.set_board(self.board_state.board)
        self.overlay.set_position(self.board_state.board)
        if self._is_user_turn():
            side = "White" if self.board_state.side_to_move_is_white() else "Black"
            self.lbl_turn.setText(f"▶ ตาคุณ ({side}) — ดูลูกศร Stockfish แล้วเดินในเกม")
            self.lbl_turn.setStyleSheet("color:#2ecc71;")
        else:
            side = "White" if self.board_state.side_to_move_is_white() else "Black"
            self.lbl_turn.setText(
                f"▶ ตาคู่แข่ง ({side}) อยู่ด้านบน — คลิกเดินที่คู่แข่งเดินในเกม"
            )
            self.lbl_turn.setStyleSheet("color:#f1c40f;")

        # History
        self.hist.clear()
        sans = self.board_state.san_history()
        ucis = self.board_state.history_uci
        for i, uci in enumerate(ucis):
            san = sans[i] if i < len(sans) else uci
            who = "คุณ" if self._move_was_user(i) else "คู่แข่ง"
            self.hist.addItem(f"{i + 1}. [{who}] {san}  ({uci})")

        # Auto-cycle: flip opponent-entry mode to match whose turn it is now
        self._apply_auto_cycle()
        # Always show what is driving the move (book / engine / tablebase)
        self._refresh_engine_status()

    def _move_was_user(self, ply_index: int) -> bool:
        # ply 0 = white; user_is_white → even plies are user if white
        white_move = ply_index % 2 == 0
        return white_move == self.user_is_white

    def _on_square(self, sq: str) -> None:
        """Square click from the program board OR the in-game overlay."""
        self._on_square_inner(sq)
        # Mirror the selection state onto the overlay highlight
        self.overlay.set_selected(self._click_from)

    def _on_square_inner(self, sq: str) -> None:
        board = self.board_state.board
        if self._click_from is None:
            piece = board.piece_at(chess.parse_square(sq))
            if piece is None or piece.color != board.turn:
                self.lbl_click.setText(
                    f"{sq}: ไม่มีหมากฝั่งที่ต้องเดิน — คลิกหมากฝั่ง {'ขาว' if board.turn else 'ดำ'}"
                )
                return
            self._click_from = sq
            who = "คุณ" if self._is_user_turn() else "คู่แข่ง"
            self.lbl_click.setText(f"[{who}] ต้นทาง {sq} → คลิกปลายทาง")
            return

        fr = self._click_from
        if sq == fr:
            self._click_from = None  # click same square = deselect
            self.lbl_click.setText("ยกเลิก — เลือกต้นทางใหม่")
            return
        move = self._parse_move(fr + sq)
        if move is not None:
            self._click_from = None
            self._push(move)
            return
        # Not a legal destination. If they clicked another of their own pieces,
        # switch the selection to it; otherwise KEEP the selection so a misclick
        # near the target doesn't force them to start over (green dots guide them).
        piece = board.piece_at(chess.parse_square(sq))
        if piece is not None and piece.color == board.turn:
            self._click_from = sq
            who = "คุณ" if self._is_user_turn() else "คู่แข่ง"
            self.lbl_click.setText(f"[{who}] เลือกใหม่ {sq} → คลิกปลายทาง (จุดเขียว)")
            return
        self.lbl_click.setText(
            f"{fr}→{sq} เดินไม่ได้ — คลิกช่องที่มีจุดเขียว (ต้นทางยังเลือก {fr} อยู่)"
        )

    def _parse_move(self, text: str) -> Optional[chess.Move]:
        board = self.board_state.board
        text = text.strip()
        try:
            m = chess.Move.from_uci(text.lower())
            if m in board.legal_moves:
                return m
        except ValueError:
            pass
        # promotions
        if len(text) == 4:
            for promo in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
                m = chess.Move(
                    chess.parse_square(text[:2]),
                    chess.parse_square(text[2:4]),
                    promotion=promo,
                )
                if m in board.legal_moves:
                    return m
        try:
            m = board.parse_san(text)
            if m in board.legal_moves:
                return m
        except Exception:
            pass
        return None

    def apply_text_move(self) -> None:
        text = self.uci_edit.text().strip()
        if not text:
            return
        move = self._parse_move(text)
        if move is None:
            QMessageBox.warning(self, "เดินไม่ได้", f"ผิดกฎหรือไม่เข้าใจ: {text}")
            return
        self.uci_edit.clear()
        self._push(move)

    def apply_best(self) -> None:
        if not self._is_user_turn():
            QMessageBox.information(
                self, "ยังไม่ใช่ตาคุณ",
                "ตอนนี้เป็นตาคู่แข่ง — ใส่การเดินของคู่แข่งก่อน (คลิกช่องบนกระดาน)",
            )
            return
        if not self._last_analysis or not self._last_analysis.ok:
            self.analyze_now()
            self.lbl_status.setText("กำลังวิเคราะห์… กดอีกครั้งเมื่อได้ Best Move")
            return
        uci = self._last_analysis.best_move_uci
        move = self._parse_move(uci)
        if move is None:
            QMessageBox.warning(self, "Error", f"Best move ใช้ไม่ได้: {uci}")
            return
        self._push(move)

    def _clear_reco(self) -> None:
        """Reset the recommendation display (both 🔥 best and ⚔️ win)."""
        self._win_move = None
        self.lbl_best.setText("🔥 แรงสุด: —")
        self.lbl_win.setText("⚔️ เอาชนะ: —")
        self.lbl_eval.setText("Eval: —")
        self.lbl_lines.setText("")
        self.btn_apply_win.setEnabled(False)

    def apply_win(self) -> None:
        """Play the win-focused move (PV2). Falls back to best if none."""
        if not self._is_user_turn():
            QMessageBox.information(
                self, "ยังไม่ใช่ตาคุณ",
                "ตอนนี้เป็นตาคู่แข่ง — ใส่การเดินของคู่แข่งก่อน",
            )
            return
        if not self._win_move:
            self.apply_best()
            return
        move = self._parse_move(self._win_move)
        if move is None:
            QMessageBox.warning(self, "Error", f"ตาเอาชนะใช้ไม่ได้: {self._win_move}")
            return
        self._push(move)

    def _push(self, move: chess.Move) -> None:
        try:
            self.board_state.push_move(move)
        except ValueError as exc:
            QMessageBox.warning(self, "ผิดกฎ", str(exc))
            return
        self._click_from = None
        self.overlay.set_selected(None)
        self.lbl_click.setText(f"บันทึก {move.uci()} แล้ว")
        self.board_view.clear_arrows()
        self._last_analysis = None
        self._clear_reco()
        self._update_overlay()
        self._refresh_all()
        self._maybe_analyze()

    def undo(self) -> None:
        if self.board_state.undo_last():
            self._click_from = None
            self._last_analysis = None
            self.board_view.clear_arrows()
            self._update_overlay()
            self._refresh_all()
            self._maybe_analyze()
            self.lbl_status.setText("Undo แล้ว")
        else:
            self.lbl_status.setText("ไม่มีให้ Undo")

    def new_game(self) -> None:
        self.board_state.reset_standard()
        self._click_from = None
        self._last_analysis = None
        self.board_view.clear_arrows()
        self._update_overlay()
        self._refresh_all()
        self._maybe_analyze()
        self.lbl_status.setText("เริ่มเกมใหม่")

    def _maybe_analyze(self) -> None:
        if self.board_state.board.is_game_over():
            self._analyzer.idle()
            res = self.board_state.board.result()
            self.lbl_status.setText(f"จบเกม: {res}")
            self.lbl_depth.setText("")
            return
        if self._is_user_turn():
            # Opening book first — instant, theory-perfect. Out of book → engine.
            bm = self.book.lookup(self.board_state.board)
            if bm is not None:
                self._analyzer.idle()
                self._show_book_move(bm)
                return
            self.analyze_now()
        else:
            self._ponder()

    def _book_result(self, board: chess.Board, move: chess.Move) -> AnalysisResult:
        san = board.san(move)
        result = AnalysisResult(fen=board.fen())
        result.lines = [
            AnalysisLine(
                multipv=1,
                move_uci=move.uci(),
                move_san=san,
                pv_uci=[move.uci()],
                pv_san=[san],
                score=EvalScore(),
                depth=0,
                explanation_th=f"📖 ตำราเปิดเกม (สายที่พิสูจน์แล้ว) — {san}",
            )
        ]
        result.best_move_uci = move.uci()
        result.best_move_san = san
        return result

    def _show_book_move(self, move: chess.Move) -> None:
        result = self._book_result(self.board_state.board, move)
        self._on_analysis(result)
        self.lbl_depth.setText("📖 จากตำราเปิดเกม (เดินได้เลย ไม่ต้องรอคิด)")
        self.lbl_status.setText(
            f"ตำรา: {result.best_move_san} — เดินในเกม แล้วกด «เดินตาม Best Move»"
        )

    def _on_book_toggled(self, on: bool) -> None:
        self.book.enabled = bool(on)
        self._maybe_analyze()

    # -- win-more move selection ---------------------------------------

    def _winmore_reorder(self, result: AnalysisResult) -> None:
        """Move the sharpest near-best line to the front of result.lines."""
        idx = self._winmore_index(self.board_state.board, result.lines)
        if idx > 0:
            line = result.lines.pop(idx)
            result.lines.insert(0, line)
            result.best_move_uci = line.move_uci
            result.best_move_san = line.move_san
            result.evaluation = line.score

    def _winmore_index(self, board: chess.Board, lines: list) -> int:
        """Index of the sharpest move within a small eval margin of the best.

        Only kicks in when the position is roughly equal to a modest edge —
        where inducing a mistake matters. Never touches forced mates or clearly
        winning/losing positions (there we just play the objective best)."""

        def stm_cp(line) -> Optional[int]:
            ev = line.score
            if ev.mate is not None or ev.cp is None:
                return None
            return ev.cp if board.turn == chess.WHITE else -ev.cp

        best = stm_cp(lines[0])
        if best is None or not (-30 <= best <= 250):
            return 0
        margin = 30
        best_i, best_bonus = 0, None
        for i, line in enumerate(lines):
            c = stm_cp(line)
            if c is None or c < best - margin:
                continue
            try:
                mv = chess.Move.from_uci(line.move_uci)
            except ValueError:
                continue
            if mv not in board.legal_moves:
                continue
            bonus = self._complexity_bonus(board, mv)
            if best_bonus is None or bonus > best_bonus:
                best_bonus, best_i = bonus, i
        return best_i

    def _complexity_bonus(self, board: chess.Board, move: chess.Move) -> float:
        """Higher = keeps more practical winning chances vs a weaker opponent."""
        after = board.copy()
        after.push(move)
        b = 4.0 * chess.popcount(after.occupied)  # more pieces on = more play
        q_before = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(
            board.pieces(chess.QUEEN, chess.BLACK)
        )
        q_after = len(after.pieces(chess.QUEEN, chess.WHITE)) + len(
            after.pieces(chess.QUEEN, chess.BLACK)
        )
        if q_after < q_before:
            b -= 40.0  # keep queens → keep attacking chances
        if after.is_check():
            b += 30.0  # forcing moves make weak players err
        # Aggression: play toward the enemy king and put their pieces under fire —
        # weak opponents crack under pressure far more than in quiet positions.
        ek = board.king(not board.turn)
        if ek is not None:
            b += max(0, 7 - chess.square_distance(move.to_square, ek)) * 2.0
        for qsq in after.pieces(chess.QUEEN, not board.turn):
            if after.is_attacked_by(board.turn, qsq):
                b += 25.0  # threatening the enemy queen
        if after.is_repetition(3):
            b -= 800.0
        elif after.is_repetition(2):
            b -= 200.0
        if after.is_insufficient_material():
            b -= 800.0
        return b

    def analyze_now(self) -> None:
        if not self.engine.path:
            self.lbl_status.setText("ยังไม่มี Stockfish — กด Stockfish… เพื่อเลือกไฟล์")
            return
        # Max-strength mode: MultiPV 1 lets Stockfish prune hardest and search
        # deepest on the single best move.
        eff_multipv = 1 if self.chk_max.isChecked() else self.multipv
        if self.chk_winmore.isChecked():
            eff_multipv = max(eff_multipv, 3)  # need alternatives to choose a sharp one
        # Bounded think: search hard for the budget, then STOP (no CPU peg).
        self._analyzer.analyze(
            self.board_state.fen(),
            eff_multipv,
            self.threads,
            self.hash_mb,
            self.movetime_ms / 1000.0,
            self.depth_cap,
        )
        self.lbl_status.setText(
            f"Stockfish คิด {self.movetime_ms/1000:.1f} วิ แล้วพัก (ไม่หน่วงเครื่อง)…"
        )

    def _ponder(self) -> None:
        """Opponent's turn: guess their reply and think ahead on that line so a
        matching move gives an instant deep answer (warms the TT). No guess →
        idle (no CPU burn while you enter their move)."""
        board = self.board_state.board
        mv = self._predicted_opp_move
        if mv:
            try:
                m = chess.Move.from_uci(mv)
            except ValueError:
                m = None
            if m is not None and m in board.legal_moves:
                ahead = board.copy()
                ahead.push(m)
                if not ahead.is_game_over():
                    self._analyzer.analyze(
                        ahead.fen(),
                        1,
                        self.threads,
                        self.hash_mb,
                        self.movetime_ms / 1000.0,
                        self.depth_cap,
                    )
                    self.lbl_depth.setText("")
                    self.lbl_status.setText(
                        f"คิดล่วงหน้า — เดาคู่แข่งเดิน {board.san(m)} "
                        "(ถ้าเดาถูกจะตอบได้ลึกทันที)"
                    )
                    return
        self._analyzer.idle()
        self.lbl_depth.setText("")
        self.lbl_status.setText("รอใส่การเดินของคู่แข่ง (ด้านบน)")

    def _on_depth(self, depth: int, tbhits: int = 0) -> None:
        self._refresh_engine_status(depth=depth, tbhits=tbhits)

    def _tb_verdict(self) -> str:
        """Read the exact tablebase verdict from the latest eval (user's POV)."""
        a = self._last_analysis
        if not a or not a.ok:
            return ""
        ev = a.evaluation
        if ev.mate is not None:
            white_wins = ev.mate > 0
            return "ชนะแน่นอน 🏆" if white_wins == self.user_is_white else "ต้องป้องกัน (ฝ่ายตรงข้ามชนะได้)"
        if ev.cp is not None:
            if ev.cp == 0:
                return "เสมอแน่นอน (ไม่มีทางชนะ)"
            white_better = ev.cp > 0
            return "ได้เปรียบ" if white_better == self.user_is_white else "เสียเปรียบ"
        return ""

    def _refresh_engine_status(self, depth: Optional[int] = None, tbhits: int = 0) -> None:
        """Always show WHAT is driving the current move: book / engine / tablebase."""
        n = chess.popcount(self.board_state.board.occupied)
        tb_on = bool(self.engine.syzygy_path)
        if n <= 5:
            if tb_on:
                base = f"📚 Tablebase ทำงาน · เหลือ {n} หมาก"
                v = self._tb_verdict()
                if v:
                    base += f" · {v}"
                if tbhits > 0:
                    base += f" · แตะฐานข้อมูล {tbhits:,} ครั้ง ✓"
            else:
                base = f"เหลือ {n} หมาก — ยังไม่ได้ตั้ง Tablebase (กดปุ่ม Tablebase…)"
        elif n <= 7:
            base = f"🧠 เอนจิน · เกมท้าย {n} หมาก (Tablebase 5 หมากจะทำงานเมื่อเหลือ ≤5)"
        else:
            base = "🧠 เอนจิน"
        if depth is not None:
            base += f" · ลึก {depth} ply"
        self.lbl_depth.setText(base)

    def _on_analysis(self, result: AnalysisResult) -> None:
        # Stale guard: streamed results for a previous position may still arrive
        # right after a move; ignore them (the analyzer has already retargeted).
        if result.fen != self.board_state.fen():
            return
        self._last_analysis = result
        if result.error:
            self.lbl_status.setText(result.error)
            return

        # Parallel mode: PV1 stays the objective-best (flawless) move; separately
        # pick PV2 = the win-focused move (sharpest near-best). Show BOTH.
        parallel = self.chk_winmore.isChecked() and self._is_user_turn() and len(result.lines) >= 2
        self._win_move = None
        win_san = None
        if parallel:
            wi = self._winmore_index(self.board_state.board, result.lines)
            if wi != 0:
                self._win_move = result.lines[wi].move_uci
                win_san = result.lines[wi].move_san

        # Predicted opponent reply (for pondering) — from the objective best line.
        if self._is_user_turn() and result.lines and len(result.lines[0].pv_uci) >= 2:
            self._predicted_opp_move = result.lines[0].pv_uci[1]

        self.lbl_best.setText(
            f"🔥 แรงสุด: {result.best_move_san}  ({result.best_move_uci})"
        )
        if self._win_move:
            self.lbl_win.setText(f"⚔️ เอาชนะ: {win_san}  ({self._win_move})")
            self.btn_apply_win.setEnabled(True)
        else:
            self.lbl_win.setText("⚔️ เอาชนะ: — (เท่ากับตาแรงสุด)")
            self.btn_apply_win.setEnabled(False)
        self.lbl_eval.setText(f"Eval: {result.evaluation.format_display()}")

        lines = []
        for i, line in enumerate(result.lines):
            pv = " ".join(line.pv_san[:6])
            lines.append(f"#{i + 1} {line.move_san} {line.score.format_display()}  {pv}")
        self.lbl_lines.setText("\n".join(lines))
        # Board view: best (green rank 0) + win (orange rank 1)
        bview = []
        if len(result.best_move_uci) >= 4:
            bview.append((result.best_move_uci[0:2], result.best_move_uci[2:4], 0))
        if self._win_move and len(self._win_move) >= 4:
            bview.append((self._win_move[0:2], self._win_move[2:4], 4))
        self.board_view.set_arrows(bview)
        self._update_overlay()
        if self._is_user_turn():
            extra = f" · ⚔️ เอาชนะ: {win_san}" if self._win_move else ""
            self.lbl_status.setText(f"🔥 {result.best_move_san}{extra} — เลือกเดินได้")
        else:
            self.lbl_status.setText("วิเคราะห์แล้ว (ยังเป็นตาคู่แข่ง)")

    # ------------------------------------------------------------------
    # Overlay over the real game

    def _load_overlay_corners(self) -> Optional[list[tuple[float, float]]]:
        cfg = config_path()
        if cfg.is_file():
            try:
                import json

                data = json.loads(cfg.read_text(encoding="utf-8"))
                pts = data.get("overlay_corners_abs")
                if pts and len(pts) == 4:
                    return [(float(p[0]), float(p[1])) for p in pts]
            except Exception as exc:  # noqa: BLE001
                logger.warning("load overlay corners: %s", exc)
        return None

    def _save_overlay_corners(self) -> None:
        if not self._overlay_corners_abs:
            return
        try:
            _merge_user_config(
                overlay_corners_abs=[[x, y] for x, y in self._overlay_corners_abs]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("save overlay corners: %s", exc)

    def setup_overlay(self) -> None:
        if self._overlay_setup is not None:
            self._overlay_setup.close()
        self._overlay_setup = OverlaySetupWindow(self._overlay_corners_abs)
        self._overlay_setup.confirmed.connect(self._on_overlay_positioned)
        self._overlay_setup.show()

    def _on_overlay_positioned(self, corners) -> None:
        self._overlay_corners_abs = [(float(x), float(y)) for x, y in corners]
        self._save_overlay_corners()
        self._apply_overlay_geometry()
        if not self.overlay._enabled:
            self.overlay.set_enabled(True)
            self.btn_ov.setText("Overlay: เปิด")
        self._update_overlay()
        self._sync_overlay_toolbar_visibility()
        self.lbl_status.setText("ตั้งตำแหน่ง Overlay แล้ว — ลูกศรจะขึ้นเมื่อถึงตาคุณ")

    def _apply_overlay_geometry(self) -> None:
        if not self._overlay_corners_abs:
            return
        xs = [p[0] for p in self._overlay_corners_abs]
        ys = [p[1] for p in self._overlay_corners_abs]
        left, top = int(min(xs)), int(min(ys))
        region = CaptureRegion(
            left, top, int(max(xs)) - left + 1, int(max(ys)) - top + 1
        )
        rel = [(x - left, y - top) for x, y in self._overlay_corners_abs]
        cal = PerspectiveCalibration(corners=rel, warped_size=512)
        ori = BoardOrientation(
            rotation_deg=0,
            my_pieces_at_bottom=True,
            user_is_white=self.user_is_white,
        )
        grid = BoardGrid(size=512, orientation=ori)
        self.overlay.set_board_geometry(region, cal, grid)
        self.overlay.set_position(self.board_state.board)
        self.overlay_toolbar.place_under(region)

    def toggle_overlay(self) -> None:
        if not self._overlay_corners_abs:
            self.setup_overlay()
            return
        on = self.overlay.toggle()
        self.btn_ov.setText("Overlay: เปิด" if on else "Overlay: ปิด")
        if on:
            self._apply_overlay_geometry()
            self._update_overlay()
        elif self._overlay_click:
            # Overlay hidden → click mode off too, for predictability
            self._overlay_click = False
            self.overlay.set_interactive(False)
            self.btn_ov_click.setText("คลิก Overlay: ปิด")
        self._sync_overlay_toolbar_visibility()

    def toggle_overlay_click(self) -> None:
        if not self._overlay_corners_abs:
            self.setup_overlay()
            return
        self._set_overlay_click(not self._overlay_click)

    def _set_overlay_click(self, on: bool) -> None:
        self._overlay_click = bool(on)
        if self._overlay_click and not self.overlay._enabled:
            self.overlay.set_enabled(True)
            self.btn_ov.setText("Overlay: เปิด")
            self._apply_overlay_geometry()
            self._update_overlay()
        self.overlay.set_interactive(self._overlay_click)
        self._sync_overlay_toolbar_visibility()
        self.overlay_toolbar.set_click_mode(self._overlay_click)
        self.btn_ov_click.setText(
            "คลิก Overlay: เปิด" if self._overlay_click else "คลิก Overlay: ปิด"
        )
        self.lbl_status.setText(
            "คลิกช่องบนเกมจริงได้เลย = คลิกกระดานโปรแกรม (ปิดโหมดนี้ก่อนจะคลิกเล่นเกมเอง)"
            if self._overlay_click
            else "Overlay กลับเป็นแบบคลิกทะลุแล้ว — คลิกเกมได้ปกติ"
        )

    def toggle_auto_cycle(self) -> None:
        if not self._overlay_corners_abs:
            self.setup_overlay()
            return
        self._auto_cycle = not self._auto_cycle
        self.overlay_toolbar.set_auto_cycle(self._auto_cycle)
        if self._auto_cycle:
            self._apply_auto_cycle()
            self.lbl_status.setText(
                "วนอัตโนมัติ: เปิด — กด Best Move → ใส่ตาคู่แข่ง → วนกลับเอง"
            )
        else:
            self.lbl_status.setText("วนอัตโนมัติ: ปิด")

    def _apply_auto_cycle(self) -> None:
        """When on: opponent's turn → click mode on; my turn → click mode off."""
        if not self._auto_cycle or not self._overlay_corners_abs:
            return
        want_click = not self._is_user_turn()
        if want_click != self._overlay_click:
            self._set_overlay_click(want_click)

    def _refresh_overlay_toolbar(self) -> None:
        a = self._last_analysis
        if not self._is_user_turn():
            self.overlay_toolbar.set_best("ตาคู่แข่ง — ใส่การเดินเขาก่อน", False)
        elif a is not None and a.ok:
            self.overlay_toolbar.set_best(f"🔥 {a.best_move_san}", True)
        else:
            self.overlay_toolbar.set_best("กำลังคิด…", False)
        self.overlay_toolbar.set_win_enabled(
            self._is_user_turn() and self._win_move is not None
        )
        self.overlay_toolbar.set_click_mode(self._overlay_click)
        self.overlay_toolbar.set_auto_cycle(self._auto_cycle)

    def _sync_overlay_toolbar_visibility(self) -> None:
        if self.overlay._enabled and self._overlay_corners_abs:
            self.overlay_toolbar.show()
        else:
            self.overlay_toolbar.hide()

    def _update_overlay(self) -> None:
        self._refresh_overlay_toolbar()
        if not self.overlay._enabled:
            return
        a = self._last_analysis
        if a is None or not a.ok or not self._is_user_turn():
            self.overlay.clear()
            return
        # Two parallel arrows: 🔥 best (green, rank 0) and ⚔️ win (orange, rank 4)
        arrows = []
        if len(a.best_move_uci) >= 4:
            arrows.append((a.best_move_uci[0:2], a.best_move_uci[2:4], 0))
        label = f"🔥 แรงสุด: {a.best_move_san}"
        if self._win_move and len(self._win_move) >= 4:
            arrows.append((self._win_move[0:2], self._win_move[2:4], 4))
            try:
                wsan = self.board_state.board.san(chess.Move.from_uci(self._win_move))
            except Exception:  # noqa: BLE001
                wsan = self._win_move
            label += f"   ⚔️ เอาชนะ: {wsan}"
        self.overlay.set_arrows(
            arrows,
            label=label,
            evaluation=a.evaluation.format_display(),
        )

    def _load_syzygy_path(self) -> str:
        cfg = config_path()
        if cfg.is_file():
            try:
                import json

                data = json.loads(cfg.read_text(encoding="utf-8"))
                sp = str(data.get("syzygy_path") or "")
                if sp and Path(sp).is_dir():
                    return sp
            except Exception:  # noqa: BLE001
                pass
        # Auto-detect the bundled tablebase folder if it has files
        bundled = Path(__file__).resolve().parent.parent / "engines" / "syzygy"
        if bundled.is_dir() and any(bundled.glob("*.rtbw")):
            return str(bundled)
        return ""

    def pick_book(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "เลือก opening book", "", "Polyglot book (*.bin);;All (*.*)"
        )
        if not path:
            return
        self.book.set_path(path)
        try:
            _merge_user_config(book_path=path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("save book path: %s", exc)
        self.lbl_status.setText("ตั้ง Opening Book แล้ว")
        self._maybe_analyze()

    def _refresh_tb_label(self) -> None:
        book = "ตำรา ✓" if self.book.available() else "ตำรา ✗"
        if self.engine.syzygy_path:
            tb = "Tablebase ✓ (เกมท้ายไร้พลาด)"
        else:
            tb = "Tablebase ✗ (ยังไม่ได้ตั้ง)"
        self.lbl_tb.setText(f"{book} · {tb}")

    def pick_tablebase(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "เลือกโฟลเดอร์ Syzygy tablebase (.rtbw/.rtbz)"
        )
        if not folder:
            return
        self._analyzer.pause()  # free the engine before changing options
        self.engine.set_syzygy_path(folder)
        self._analyzer.invalidate_config()  # re-send SyzygyPath on next search
        try:
            _merge_user_config(syzygy_path=folder)
        except Exception as exc:  # noqa: BLE001
            logger.warning("save syzygy path: %s", exc)
        self._refresh_tb_label()
        self.lbl_status.setText("ตั้ง Tablebase แล้ว — เกมท้าย ≤7 หมากจะเล่นแบบไร้พลาด")
        self._maybe_analyze()

    def pick_stockfish(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "เลือก stockfish.exe", "", "Executable (*.exe);;All (*.*)"
        )
        if not path:
            return
        # Free the engine from the analyzer thread before swapping the binary.
        self._analyzer.pause()
        self.engine.set_path(path)
        ok, msg = self.engine.validate()
        self.lbl_status.setText(msg)
        if ok:
            try:
                _merge_user_config(stockfish_path=path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("save config: %s", exc)
            self._maybe_analyze()

    def _validate_engine(self) -> None:
        if not self.engine.path:
            self.lbl_status.setText("เลือก stockfish.exe ก่อน (ปุ่ม Stockfish…)")
            return
        ok, msg = self.engine.validate()
        self.lbl_status.setText(msg if ok else msg)

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self._analyzer.shutdown()  # stop the analysis thread before closing engine
        except Exception:
            pass
        try:
            self.overlay.force_disable()
            self.overlay_toolbar.close()
            if self._overlay_setup is not None:
                self._overlay_setup.close()
        except Exception:
            pass
        try:
            self.engine.close()
        except Exception:
            pass
        super().closeEvent(event)
