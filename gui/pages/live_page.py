"""Live Capture page with continuous detection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import chess
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from capture.mss_capture import MssCapture
from capture.worker import CaptureWorker
from chess_engine.worker import AnalyzeWorker
from gui.widgets.board_view import BoardView
from gui.widgets.capture_preview import CapturePreview
from move_detection.diff_tracker import MoveHypothesis
from vision.grid import BoardGrid

if TYPE_CHECKING:
    from gui.app_state import AppState


class LivePage(QWidget):
    def __init__(self, state: AppState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state
        self._worker: Optional[CaptureWorker] = None
        self._frame_skip = 0
        self._prompt_open = False
        self._last_prompt_key = ""
        self._auto_mode = False  # continuous auto OFF by default (too noisy); use Before/After
        self._last_auto_uci = ""
        self._auto_lock_frames = 0  # frames to wait before re-lock after apply
        self._analyze_worker: Optional[AnalyzeWorker] = None

        title = QLabel("Live Capture")
        title.setObjectName("titleLabel")

        self.preview = CapturePreview()
        self.board_view = BoardView()
        self.board_view.set_board(state.board_state.board)
        self.board_view.square_clicked.connect(self._on_board_square_click)
        self._click_from: Optional[str] = None

        self.lbl_side = QLabel()
        self.lbl_turn = QLabel()
        self.lbl_best = QLabel("Best Move: —")
        self.lbl_eval = QLabel("Evaluation: —")
        self.lbl_conf = QLabel("Confidence: —")
        self.lbl_detect = QLabel("Detection: หยุดอยู่")
        self.lbl_fen = QLabel()
        self.lbl_fen.setObjectName("mutedLabel")
        self.lbl_fen.setWordWrap(True)
        self.lbl_explain = QLabel("")
        self.lbl_explain.setWordWrap(True)
        self.lbl_explain.setObjectName("mutedLabel")

        # Primary workflow: Before / After + chess logic
        scan_box = QGroupBox("จับการเดินจากภาพ + กฎหมากรุก (แนะนำ)")
        sb = QVBoxLayout(scan_box)
        sb.addWidget(QLabel(
            "1) กด «จำภาพก่อนเดิน» ตอนกระดานนิ่ง\n"
            "2) เดินในเกม (เราหรือคู่แข่ง) รอให้นิ่ง\n"
            "3) กด «จับการเดินหลังเดิน» — ระบบดูว่าตัวไหนหาย/มา แล้วคัดเฉพาะ legal move"
        ))
        row_scan = QHBoxLayout()
        self.btn_before = QPushButton("1. จำภาพก่อนเดิน")
        self.btn_before.setObjectName("primaryButton")
        self.btn_before.clicked.connect(self.lock_reference)
        self.btn_after = QPushButton("2. จับการเดินหลังเดิน")
        self.btn_after.setObjectName("primaryButton")
        self.btn_after.clicked.connect(self.confirm_pending)
        row_scan.addWidget(self.btn_before)
        row_scan.addWidget(self.btn_after)
        sb.addLayout(row_scan)

        manual_box = QGroupBox("อัปเดตมือ (ชัวร์ 100%)")
        mb = QVBoxLayout(manual_box)
        mb.addWidget(QLabel("คลิกช่องต้นทาง→ปลายทางบนกระดานขวา หรือพิมพ์ e2e4"))
        self.lbl_click = QLabel("คลิกช่อง: (ยังไม่เลือกต้นทาง)")
        mb.addWidget(self.lbl_click)
        uci_row = QHBoxLayout()
        self.uci_edit = QLineEdit()
        self.uci_edit.setPlaceholderText("e2e4 / Nf3 / O-O")
        self.uci_edit.returnPressed.connect(self.apply_uci_text)
        btn_uci = QPushButton("ใส่การเดิน")
        btn_uci.clicked.connect(self.apply_uci_text)
        uci_row.addWidget(self.uci_edit, 1)
        uci_row.addWidget(btn_uci)
        mb.addLayout(uci_row)

        info = QGroupBox("สถานะ")
        info_l = QVBoxLayout(info)
        for w in (
            self.lbl_side,
            self.lbl_turn,
            self.lbl_best,
            self.lbl_eval,
            self.lbl_conf,
            self.lbl_detect,
            self.lbl_fen,
            self.lbl_explain,
        ):
            info_l.addWidget(w)

        btn_capture = QPushButton("Capture Once")
        btn_capture.clicked.connect(self.capture_once)
        self.btn_start = QPushButton("Start Capture")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.clicked.connect(self.toggle_capture)
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.clicked.connect(self.toggle_pause)
        btn_analyze = QPushButton("Analyze")
        btn_analyze.setObjectName("primaryButton")
        btn_analyze.clicked.connect(self.analyze)
        self.btn_auto = QPushButton("Auto ต่อเนื่อง: ปิด")
        self.btn_auto.setToolTip("เปิดเฉพาะถ้า Before/After ใช้ได้แล้ว — ค่าเริ่มต้นปิดเพราะมักจับผิด")
        self.btn_auto.clicked.connect(self.toggle_auto_mode)
        self.btn_confirm = QPushButton("จับการเดินหลังเดิน")
        self.btn_confirm.setObjectName("primaryButton")
        self.btn_confirm.clicked.connect(self.confirm_pending)
        self.btn_manual = QPushButton("เลือกจากรายการ legal")
        self.btn_manual.clicked.connect(self.manual_pick_move)
        self.btn_lock = QPushButton("จำภาพก่อนเดิน")
        self.btn_lock.clicked.connect(self.lock_reference)
        btn_undo = QPushButton("Undo Last Detection")
        btn_undo.clicked.connect(self.undo)
        btn_correct = QPushButton("Correct Position")
        btn_recal = QPushButton("Recalibrate")
        btn_reset = QPushButton("Reset Game")
        btn_reset.setObjectName("dangerButton")
        btn_reset.clicked.connect(self.reset_game)
        self.btn_overlay = QPushButton("Toggle Overlay")
        self.btn_overlay.clicked.connect(self.toggle_overlay)

        self.btn_correct = btn_correct
        self.btn_recal = btn_recal

        buttons = QGridLayout()
        btns = [
            btn_capture,
            self.btn_start,
            self.btn_pause,
            btn_analyze,
            self.btn_auto,
            self.btn_confirm,
            self.btn_manual,
            self.btn_lock,
            btn_undo,
            btn_correct,
            btn_recal,
            btn_reset,
            self.btn_overlay,
        ]
        for i, b in enumerate(btns):
            buttons.addWidget(b, i // 3, i % 3)

        left = QVBoxLayout()
        left.addWidget(QLabel("ภาพกระดาน (warped + grid)"))
        left.addWidget(self.preview, 1)
        right = QVBoxLayout()
        right.addWidget(QLabel("กระดานที่ระบบเข้าใจ — คลิก from→to เพื่ออัปเดตมือ"))
        right.addWidget(self.board_view, 1)
        right.addWidget(scan_box)
        right.addWidget(manual_box)
        right.addWidget(info)
        right.addLayout(buttons)

        row = QHBoxLayout()
        row.addLayout(left, 1)
        row.addLayout(right, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(row)
        self.refresh_labels()
        state.board_changed.connect(self.on_board_changed)
        state.analysis_changed.connect(self.on_analysis_changed)
        state.capture_changed.connect(self.on_capture_changed)
        state.profile_changed.connect(self.refresh_labels)
        state.detection_message.connect(self.lbl_detect.setText)
        state.drift_warning.connect(self._on_drift)

    def refresh_labels(self) -> None:
        t = self.state.team
        self.lbl_side.setText(
            f"ฝ่ายผู้ใช้: {t.user_label()} "
            f"({'White' if t.user_is_white else 'Black'})"
        )
        is_user = self.state.board_state.is_user_turn(t.user_is_white)
        turn_side = "White" if self.state.board_state.side_to_move_is_white() else "Black"
        self.lbl_turn.setText(
            f"ตาเดิน: {turn_side} — {'ตาของฉัน' if is_user else 'ตาของคู่แข่ง'}"
        )
        self.lbl_fen.setText(f"FEN: {self.state.board_state.fen()}")
        self.board_view.set_orientation(self.state.orientation)
        self.board_view.set_board(self.state.board_state.board)
        conf = self.state.last_detection_confidence
        self.lbl_conf.setText(f"Confidence: {conf:.0%}" if conf is not None else "Confidence: —")

    def on_board_changed(self) -> None:
        self.refresh_labels()

    def on_analysis_changed(self) -> None:
        a = self.state.last_analysis
        if not a or not a.ok:
            self.lbl_best.setText(f"Best Move: — {a.error if a else ''}")
            self.lbl_eval.setText("Evaluation: —")
            self.lbl_explain.setText("")
            self.board_view.clear_arrows()
            return
        uci = a.best_move_uci
        arrow = f"{uci[0:2]} → {uci[2:4]}" if len(uci) >= 4 else uci
        self.lbl_best.setText(f"Best Move: {a.best_move_san}  ({arrow})")
        self.lbl_eval.setText(f"Evaluation: {a.evaluation.format_display()}")
        if a.lines:
            self.lbl_explain.setText(a.lines[0].explanation_th)
        arrows = []
        for i, line in enumerate(a.lines):
            if len(line.move_uci) >= 4:
                arrows.append((line.move_uci[0:2], line.move_uci[2:4], i))
        self.board_view.set_arrows(arrows)
        self.state.push_analysis_to_overlay()

    def on_capture_changed(self) -> None:
        if self.state.last_warped_bgr is not None:
            grid = BoardGrid(
                size=self.state.last_warped_bgr.shape[0], orientation=self.state.orientation
            )
            self.preview.set_grid(grid)
            self.preview.set_image(self.state.last_warped_bgr)

    def capture_once(self) -> None:
        if self.state.region is None:
            QMessageBox.warning(
                self, "ยังไม่ครบ", "กรุณาเลือกพื้นที่กระดานในหน้า Board Calibration ก่อน"
            )
            return
        try:
            cap = MssCapture(self.state.monitor_id)
            img = cap.grab(self.state.region)
            cap.close()
            self.state.last_roi_bgr = img
            warped = self.state.calibration.warp(img)
            self.state.last_warped_bgr = warped
            # Lock visual reference to current board (so next scan can see deltas)
            self.state.detection.set_reference_frame(warped, self.state.board_state.board)
            self.state.capture_changed.emit()
            self.state.status_message.emit("จับภาพสำเร็จ + ล็อกภาพอ้างอิงแล้ว")
            self.state.detection_message.emit("พร้อม — เดินหมากในเกม แล้วกด Confirm / สแกนการเดิน")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "จับภาพไม่สำเร็จ", str(exc))
            self.state.status_message.emit(f"จับภาพผิดพลาด: {exc}")

    def toggle_capture(self) -> None:
        if self._worker and self._worker.isRunning():
            self.stop_capture()
            return
        self.start_capture()

    def start_capture(self) -> None:
        if self.state.region is None:
            QMessageBox.warning(self, "ยังไม่ครบ", "ตั้งค่า ROI ใน Board Calibration ก่อน")
            return
        self.state.refresh_detection_config()
        self.state.detection.reset(self.state.board_state.board)
        # Immediate capture + visual lock so first move can be detected
        try:
            cap = MssCapture(self.state.monitor_id)
            img = cap.grab(self.state.region)
            cap.close()
            warped = self.state.calibration.warp(img)
            self.state.last_roi_bgr = img
            self.state.last_warped_bgr = warped
            self.state.detection.set_reference_frame(warped, self.state.board_state.board)
            self.state.capture_changed.emit()
        except Exception as exc:  # noqa: BLE001
            self.state.status_message.emit(f"ล็อกภาพเริ่มต้นไม่สำเร็จ: {exc}")
        self._worker = CaptureWorker(self)
        self._worker.configure(
            self.state.monitor_id,
            self.state.region,
            self.state.calibration,
            target_fps=12.0,
        )
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.error.connect(lambda m: self.state.status_message.emit(m))
        self._worker.status.connect(lambda m: self.state.detection_message.emit(m))
        self._worker.start()
        self.state.capture_active = True
        self.btn_start.setText("Stop Capture")
        self.state.status_message.emit(
            "เริ่มจับภาพอัตโนมัติ — เดินในเกม (เราหรือคู่แข่ง) ระบบจะจับและอัปเดตเอง"
        )
        self.state.detection_message.emit("Auto ON — รอการเคลื่อนไหวบนกระดาน")

    def stop_capture(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
            self._worker = None
        self.state.capture_active = False
        self.btn_start.setText("Start Capture")
        self.state.detection_message.emit("Detection: หยุดอยู่")

    def toggle_pause(self) -> None:
        if not self._worker:
            self.state.status_message.emit("ยังไม่ได้ Start Capture")
            return
        self.state.capture_paused = not self.state.capture_paused
        self._worker.set_paused(self.state.capture_paused)
        self.btn_pause.setText("Resume" if self.state.capture_paused else "Pause")

    def toggle_auto_mode(self) -> None:
        self._auto_mode = not self._auto_mode
        self.btn_auto.setText(
            "Auto ต่อเนื่อง: เปิด" if self._auto_mode else "Auto ต่อเนื่อง: ปิด"
        )
        self.state.detection_message.emit(
            "Auto ต่อเนื่องเปิด — อาจจับผิดได้ แนะนำ Before/After"
            if self._auto_mode
            else "ใช้ปุ่ม จำภาพก่อนเดิน → เดินเกม → จับการเดินหลังเดิน"
        )

    def _on_frame(self, roi, warped) -> None:
        try:
            self.state.last_roi_bgr = roi
            self.state.last_warped_bgr = warped
            # After auto-apply, wait a few frames then re-lock visual ref
            if self._auto_lock_frames > 0:
                self._auto_lock_frames -= 1
                if self._auto_lock_frames == 0:
                    self.state.detection.set_reference_frame(
                        warped, self.state.board_state.board
                    )
                    self.state.detection_message.emit("พร้อมจับตาถัดไป (ล็อกภาพใหม่แล้ว)")
                self._frame_skip = (self._frame_skip + 1) % 3
                if self._frame_skip == 0:
                    self.state.capture_changed.emit()
                return
            self._frame_skip = (self._frame_skip + 1) % 2
            if self._frame_skip == 0:
                self.state.capture_changed.emit()
            self._run_detection(warped)
        except Exception as exc:  # noqa: BLE001
            self.state.status_message.emit(f"frame error: {exc}")

    def _run_detection(self, warped) -> None:
        try:
            event = self.state.detection.on_frame(warped, self.state.board_state.board)
        except Exception as exc:  # noqa: BLE001
            self.state.detection_message.emit(f"detection error: {exc}")
            return

        # Always paint heat map so user sees which squares changed
        heat = getattr(event, "heat", None)
        if heat is not None:
            try:
                self.preview.set_heat(heat)
            except Exception:
                pass

        dbg = getattr(event, "debug", "") or event.message or event.kind
        self.state.detection_message.emit(dbg)

        if event.kind in ("idle", "watching"):
            if event.hypothesis and event.hypothesis.moves:
                self.lbl_conf.setText(f"Confidence: {event.hypothesis.confidence:.0%}")
                # Soft auto: if watching score is already very high, apply
                hyp = event.hypothesis
                top = hyp.moves[0]
                if (
                    self._auto_mode
                    and hyp.confidence >= 0.55
                    and top.uci() != self._last_auto_uci
                    and "กำลังจับ" in (event.message or "")
                ):
                    # wait for ready; don't apply mid-watch
                    pass
            return

        if not (event.hypothesis and event.hypothesis.moves):
            return

        hyp = event.hypothesis
        self.state.last_detection_confidence = hyp.confidence
        self.lbl_conf.setText(f"Confidence: {hyp.confidence:.0%}")
        top = hyp.moves[0]
        try:
            san = self.state.board_state.board.san(top)
        except Exception:
            san = top.uci()

        if top.uci() == self._last_auto_uci:
            return

        if self._auto_mode and event.kind == "move":
            self.state.detection_message.emit(
                f"Auto: {san} ({top.uci()}) conf={hyp.confidence:.0%} | {dbg}"
            )
            self._apply_move(top, hyp.confidence, auto=True)
            return

        if event.kind == "move":
            self.state.detection_message.emit(
                f"ตรวจพบ: {san} ({top.uci()}) — กดสแกนมือเพื่อยืนยัน"
            )

    def lock_reference(self) -> None:
        """Step 1: remember board image before a move."""
        warped = self._grab_warped()
        if warped is None:
            # try start capture grab
            if self.state.region is None:
                QMessageBox.warning(
                    self, "ยังไม่มีภาพ",
                    "ตั้ง Board Calibration แล้วกด Start Capture หรือ Capture Once ก่อน",
                )
                return
            QMessageBox.warning(self, "ไม่มีภาพ", "กด Capture Once หรือ Start Capture ก่อน")
            return
        self.state.detection.set_reference_frame(warped, self.state.board_state.board)
        self.state.detection.clear_pending()
        self._last_prompt_key = ""
        self._last_auto_uci = ""
        self._auto_lock_frames = 0
        self.preview.set_heat(None)
        self.state.detection_message.emit(
            "จำภาพก่อนเดินแล้ว → เดินในเกม → กด «จับการเดินหลังเดิน»"
        )
        self.state.status_message.emit("OK: จำภาพก่อนเดินแล้ว")
        QMessageBox.information(
            self,
            "จำภาพแล้ว",
            "บันทึกภาพกระดานตอนนี้แล้ว\n\n"
            "ต่อไป:\n"
            "1. เดินหมากในเกม (ฝั่งคุณหรือคู่แข่ง)\n"
            "2. รอให้นิ่ง\n"
            "3. กด «2. จับการเดินหลังเดิน»\n\n"
            "ระบบจะดูว่าตัวไหนหาย/มา แล้วเลือกเฉพาะการเดินที่ถูกกฎหมากรุก",
        )

    def _grab_warped(self):
        if self.state.last_warped_bgr is not None and self.state.capture_active:
            return self.state.last_warped_bgr
        if self.state.region is None:
            return self.state.last_warped_bgr
        try:
            cap = MssCapture(self.state.monitor_id)
            img = cap.grab(self.state.region)
            cap.close()
            warped = self.state.calibration.warp(img)
            self.state.last_roi_bgr = img
            self.state.last_warped_bgr = warped
            self.state.capture_changed.emit()
            return warped
        except Exception as exc:  # noqa: BLE001
            self.state.status_message.emit(f"จับภาพไม่สำเร็จ: {exc}")
            return self.state.last_warped_bgr

    def _prompt_move_choice(self, hyp: MoveHypothesis) -> None:
        if self._prompt_open:
            return
        self._prompt_open = True
        try:
            if hyp.needs_promotion_choice:
                self._prompt_promotion(hyp)
                return
            items = []
            board = self.state.board_state.board
            for m in hyp.moves[:12]:
                try:
                    items.append(f"{board.san(m)}  ({m.uci()})")
                except Exception:
                    items.append(m.uci())
            if not items:
                self.state.status_message.emit("ไม่มีรายการเดินให้เลือก")
                return
            choice, ok = QInputDialog.getItem(
                self,
                "ยืนยันการเดิน",
                hyp.message or "เลือกการเดินที่เกิดขึ้นในเกม",
                items,
                0,
                False,
            )
            if not ok:
                self.state.detection_message.emit("ยังไม่ยืนยัน — กด Confirm อีกครั้งหรือเลือกมือ")
                return
            idx = items.index(choice)
            self._apply_move(hyp.moves[idx], hyp.confidence)
        finally:
            self._prompt_open = False

    def _prompt_promotion(self, hyp: MoveHypothesis) -> None:
        promos = [m for m in hyp.moves if m.promotion]
        if not promos:
            return
        labels = []
        for m in promos:
            name = {
                chess.QUEEN: "Queen",
                chess.ROOK: "Rook",
                chess.BISHOP: "Bishop",
                chess.KNIGHT: "Knight",
            }.get(m.promotion, "?")
            labels.append(f"{m.uci()[:4]} → {name}")
        choice, ok = QInputDialog.getItem(
            self, "Pawn Promotion", "เลื่อนเป็นหมากชนิดใด?", labels, 0, False
        )
        if not ok:
            return
        self._apply_move(promos[labels.index(choice)], hyp.confidence)

    def confirm_pending(self) -> None:
        """Step 2: compare after-move image → chess-legal candidates only."""
        warped = self._grab_warped()
        if warped is None:
            QMessageBox.warning(self, "ไม่มีภาพ", "กด Start Capture หรือ Capture Once ก่อน")
            return
        if not self.state.detection.auto.locked:
            self.state.detection.set_reference_frame(warped, self.state.board_state.board)
            QMessageBox.information(
                self,
                "ยังไม่มีภาพก่อนเดิน",
                "เพิ่งจำภาพตอนนี้ให้แล้ว\n\n"
                "เดินในเกมก่อน แล้วค่อยกด «จับการเดินหลังเดิน» อีกครั้ง",
            )
            return

        heat = None
        try:
            event = self.state.detection.scan_now(warped, self.state.board_state.board)
            heat = getattr(event, "heat", None)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "สแกนล้มเหลว", str(exc))
            return

        if heat is not None:
            self.preview.set_heat(heat)

        dbg = getattr(event, "debug", "") or event.message
        self.state.detection_message.emit(dbg)

        hyp = event.hypothesis
        if hyp and hyp.moves:
            self.state.last_detection_confidence = hyp.confidence
            self.lbl_conf.setText(f"Confidence: {hyp.confidence:.0%}")
            top = hyp.moves[0]
            board = self.state.board_state.board
            try:
                san = board.san(top)
            except Exception:
                san = top.uci()
            piece = board.piece_at(top.from_square)
            pname = {
                "P": "เบี้ย", "N": "ม้า", "B": "บิชอป", "R": "เรือ", "Q": "ควีน", "K": "คิง",
                "p": "เบี้ย", "n": "ม้า", "b": "บิชอป", "r": "เรือ", "q": "ควีน", "k": "คิง",
            }.get(piece.symbol() if piece else "", "?")
            fr = chess.square_name(top.from_square)
            to = chess.square_name(top.to_square)
            alts = ""
            if len(hyp.moves) > 1:
                bits = []
                for m in hyp.moves[1:5]:
                    try:
                        bits.append(board.san(m))
                    except Exception:
                        bits.append(m.uci())
                alts = "\nทาง legal อื่น: " + ", ".join(bits)

            # Single clear legal explanation → apply with one confirm
            ans = QMessageBox.question(
                self,
                "การเดินตามกฎหมากรุก",
                f"หมากที่ออก: {pname} จาก {fr}\n"
                f"ไปช่อง: {to}\n"
                f"SAN: {san}   UCI: {top.uci()}\n\n"
                f"{dbg}{alts}\n\n"
                f"อัปเดตกระดานตามนี้?",
            )
            if ans == QMessageBox.StandardButton.Yes:
                self._apply_move(top, max(hyp.confidence, 0.6), auto=False)
            else:
                self._prompt_move_choice(hyp)
            return

        ans = QMessageBox.question(
            self,
            "จับ legal move ไม่ได้",
            f"{dbg}\n\n"
            "สาเหตุบ่อย: grid ไม่ตรงช่อง / ยังไม่วิ่ง / จำภาพหลังเดินแล้ว\n\n"
            "เลือกการเดินจากรายการ legal เองไหม?\n"
            "(หรือคลิก from→to บนกระดานขวา)",
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.manual_pick_move()

    def manual_pick_move(self) -> None:
        """Let user pick any legal move (works even when vision fails)."""
        board = self.state.board_state.board
        moves = list(board.legal_moves)
        if not moves:
            QMessageBox.information(self, "จบเกม", "ไม่มี legal move")
            return
        items = []
        move_list = []
        for m in moves:
            try:
                san = board.san(m)
            except Exception:
                san = m.uci()
            items.append(f"{san}  ({m.uci()})")
            move_list.append(m)
        choice, ok = QInputDialog.getItem(
            self,
            "เลือกการเดินมือ",
            "เลือกตาที่เพิ่งเดินในเกม:",
            items,
            0,
            False,
        )
        if not ok:
            return
        self._apply_move(move_list[items.index(choice)], 1.0, auto=False)

    def _on_board_square_click(self, sq: str) -> None:
        """Two-click move entry on 2D board — always reliable."""
        board = self.state.board_state.board
        if self._click_from is None:
            piece = board.piece_at(chess.parse_square(sq))
            if piece is None or piece.color != board.turn:
                self.lbl_click.setText(
                    f"ช่อง {sq} ไม่มีหมากฝั่งที่เดิน — คลิกช่องที่มีหมากฝั่ง {('White' if board.turn else 'Black')}"
                )
                return
            self._click_from = sq
            self.lbl_click.setText(f"ต้นทาง: {sq} → คลิกช่องปลายทาง")
            self.state.status_message.emit(f"เลือกต้นทาง {sq}")
            return

        fr = self._click_from
        to = sq
        self._click_from = None
        if fr == to:
            self.lbl_click.setText("ยกเลิก — คลิกต้นทางใหม่")
            return

        # Build UCI (promotion default queen)
        uci = fr + to
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            # try promotions
            found = None
            for promo in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
                m2 = chess.Move.from_uci(uci + chess.piece_symbol(promo).lower())
                # piece_symbol gives wrong case - use chess.Move with promotion
                m2 = chess.Move(
                    chess.parse_square(fr), chess.parse_square(to), promotion=promo
                )
                if m2 in board.legal_moves:
                    found = m2
                    break
            if found is None:
                self.lbl_click.setText(f"ผิดกฎ: {fr}→{to} — คลิกต้นทางใหม่")
                self.state.status_message.emit(f"การเดิน {fr}{to} ผิดกฎ")
                return
            move = found

        self.lbl_click.setText(f"อัปเดตแล้ว: {move.uci()} — คลิกต้นทางตาถัดไป")
        self._apply_move(move, 1.0, auto=False)

    def apply_uci_text(self) -> None:
        text = self.uci_edit.text().strip()
        if not text:
            return
        board = self.state.board_state.board
        move = None
        try:
            move = chess.Move.from_uci(text.lower())
            if move not in board.legal_moves:
                move = None
        except ValueError:
            move = None
        if move is None:
            try:
                move = board.parse_san(text)
            except Exception:
                move = None
        if move is None or move not in board.legal_moves:
            QMessageBox.warning(
                self,
                "เดินไม่ได้",
                f"ไม่เข้าใจหรือผิดกฎ: {text}\nตัวอย่าง: e2e4, e7e5, Nf3, O-O",
            )
            return
        self.uci_edit.clear()
        self._apply_move(move, 1.0, auto=False)

    def _apply_move(
        self, move: chess.Move, confidence: float, auto: bool = False
    ) -> None:
        try:
            self.state.board_state.push_move(move)
        except ValueError as exc:
            if not auto:
                QMessageBox.warning(self, "การเดินผิดกฎ", str(exc))
            else:
                self.state.detection_message.emit(f"ข้ามการเดินผิดกฎ: {move.uci()}")
            return

        self._last_auto_uci = move.uci()
        self._click_from = None
        self.state.last_detection_confidence = confidence
        # Re-lock after animation: wait frames then lock CURRENT image
        self.state.detection.apply_accepted(self.state.board_state.board, warped=None)
        self._auto_lock_frames = 8
        self._last_prompt_key = ""
        self.state.detection.clear_pending()

        if self.state.save_move_screenshots and self.state.last_warped_bgr is not None:
            self.state.board_screenshots.append(
                (self.state.board_state.fen(), self.state.last_warped_bgr.copy())
            )
        self.state.board_changed.emit()

        side = (
            "ฉัน"
            if not self.state.board_state.is_user_turn(self.state.team.user_is_white)
            else "คู่แข่ง"
        )
        # After push, turn flipped — the side that just moved is opposite of current turn
        just_moved_user = not self.state.board_state.is_user_turn(self.state.team.user_is_white)
        who = "ฉัน" if just_moved_user else "คู่แข่ง"
        tag = "Auto" if auto else "Manual"
        self.state.status_message.emit(
            f"{tag}: {who} เดิน {move.uci()} ({confidence:.0%})"
        )
        self.state.detection_message.emit(
            f"อัปเดต {move.uci()} แล้ว — รอภาพนิ่งแล้วล็อกใหม่จับตาถัดไป"
        )

        # Analyze when it becomes user's turn
        if (
            self.state.auto_analyze_on_user_turn
            and self.state.board_state.is_user_turn(self.state.team.user_is_white)
        ):
            self.analyze()
        elif not self.state.board_state.is_user_turn(self.state.team.user_is_white):
            self.lbl_explain.setText("ตาคู่แข่ง — รอเขาเดิน ระบบจะจับอัตโนมัติ")
            self.board_view.clear_arrows()
            self.state.overlay.clear()

    def analyze(self) -> None:
        """Always async — never freeze the window on Stockfish."""
        if self._analyze_worker is not None and self._analyze_worker.isRunning():
            self.state.status_message.emit("กำลังวิเคราะห์อยู่… รอสักครู่")
            return
        self.state.status_message.emit("กำลังวิเคราะห์ (พื้นหลัง)…")
        self.lbl_explain.setText("กำลังวิเคราะห์ด้วย Stockfish…")
        # Live analysis: short time so UI stays responsive
        self._analyze_worker = AnalyzeWorker(
            self.state, movetime_ms=600, multipv=3, parent=self
        )
        self._analyze_worker.finished_ok.connect(self._on_analyze_done)
        self._analyze_worker.failed.connect(self._on_analyze_fail)
        self._analyze_worker.start()

    def _on_analyze_done(self, result) -> None:
        self.state.last_analysis = result
        self.state.analysis_changed.emit()
        if result.error:
            self.state.status_message.emit(result.error)
            self.lbl_explain.setText(result.error)
        else:
            self.state.status_message.emit(
                f"Best: {result.best_move_san} {result.evaluation.format_display()}"
            )

    def _on_analyze_fail(self, msg: str) -> None:
        self.state.status_message.emit(f"วิเคราะห์ล้มเหลว: {msg}")
        self.lbl_explain.setText(msg)

    def undo(self) -> None:
        if self.state.board_state.undo_last():
            self.state.detection.reset(self.state.board_state.board)
            warped = self._grab_warped()
            if warped is not None:
                self.state.detection.set_reference_frame(warped, self.state.board_state.board)
            self.state.board_changed.emit()
            self.state.status_message.emit("ย้อนการเดินล่าสุดแล้ว + ล็อกภาพใหม่")
        else:
            self.state.status_message.emit("ไม่มีอะไรให้ย้อน")

    def reset_game(self) -> None:
        self.state.board_state.reset_standard()
        self.state.start_fen = self.state.board_state.fen()
        self.state.last_analysis = None
        self.state.board_screenshots.clear()
        self.state.detection.reset(self.state.board_state.board)
        warped = self._grab_warped()
        if warped is not None:
            self.state.detection.set_reference_frame(warped, self.state.board_state.board)
        self.board_view.clear_arrows()
        self.state.overlay.clear()
        self.state.board_changed.emit()
        self.state.analysis_changed.emit()
        self.state.status_message.emit("รีเซ็ตเกม + ล็อกภาพอ้างอิงแล้ว")

    def toggle_overlay(self) -> None:
        self.state.update_overlay_geometry()
        on = self.state.overlay.toggle()
        self.state.status_message.emit("Overlay เปิด" if on else "Overlay ปิด")
        if on:
            self.state.push_analysis_to_overlay()

    def _on_drift(self, msg: str) -> None:
        self.lbl_detect.setText(msg)
        self.state.status_message.emit(msg)
