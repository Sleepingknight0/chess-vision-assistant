"""Stockfish engine settings and analysis page."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chess_engine.stockfish_engine import PRESETS
from chess_engine.worker import AnalyzeWorker, GrokValidateWorker, GrokWorker

if TYPE_CHECKING:
    from gui.app_state import AppState


class EnginePage(QWidget):
    def __init__(self, state: AppState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state
        self._worker: Optional[AnalyzeWorker] = None
        self._grok_worker: Optional[GrokWorker] = None
        self._grok_validate_worker: Optional[GrokValidateWorker] = None

        title = QLabel("Engine Analysis")
        title.setObjectName("titleLabel")

        self.path_edit = QLineEdit(state.engine.path or state.config.get("stockfish_path", ""))
        btn_browse = QPushButton("เลือก stockfish.exe…")
        btn_browse.clicked.connect(self.browse)
        btn_validate = QPushButton("ตรวจสอบ Engine")
        btn_validate.clicked.connect(self.validate)
        self.lbl_engine_status = QLabel("ยังไม่ได้ตรวจสอบ")
        self.lbl_engine_status.setObjectName("mutedLabel")

        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(btn_browse)
        path_row.addWidget(btn_validate)

        self.preset = QComboBox()
        for key, meta in PRESETS.items():
            self.preset.addItem(meta["label"], key)
        idx = self.preset.findData(state.profile.engine.preset)
        if idx >= 0:
            self.preset.setCurrentIndex(idx)

        self.multipv = QSpinBox()
        self.multipv.setRange(1, 5)
        self.multipv.setValue(state.profile.engine.multipv)

        self.threads = QSpinBox()
        self.threads.setRange(1, 32)
        self.threads.setValue(state.profile.engine.threads)

        self.skill = QSpinBox()
        self.skill.setRange(0, 20)
        self.skill.setValue(state.profile.engine.skill_level)

        self.movetime = QSpinBox()
        self.movetime.setRange(50, 30000)
        self.movetime.setSuffix(" ms")
        self.movetime.setValue(state.profile.engine.movetime_ms)

        form = QFormLayout()
        form.addRow("ระดับวิเคราะห์", self.preset)
        form.addRow("Top lines (MultiPV)", self.multipv)
        form.addRow("CPU Threads", self.threads)
        form.addRow("Skill Level", self.skill)
        form.addRow("Move Time", self.movetime)

        btn_analyze = QPushButton("วิเคราะห์ตำแหน่งปัจจุบัน")
        btn_analyze.setObjectName("primaryButton")
        btn_analyze.clicked.connect(self.analyze)
        btn_save = QPushButton("บันทึกการตั้งค่า Engine")
        btn_save.clicked.connect(self.save_settings)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("ผลวิเคราะห์จะแสดงที่นี่…")

        box = QGroupBox("Stockfish (local UCI)")
        bl = QVBoxLayout(box)
        bl.addLayout(path_row)
        bl.addWidget(self.lbl_engine_status)
        bl.addLayout(form)
        bl.addWidget(btn_analyze)
        bl.addWidget(btn_save)

        # --- Grok (xAI API) — optional cloud analysis ---
        # Never prefill the real key into the widget (clipboard/screenshot risk).
        # Empty field + existing secret → keep previous on save.
        self.grok_key = QLineEdit()
        self.grok_key.setEchoMode(QLineEdit.EchoMode.Password)
        src = self.state.config.grok_api_key_source()
        if src == "env":
            self.grok_key.setPlaceholderText("ใช้จาก environment (XAI_API_KEY) — ไม่เขียนลงดิสก์")
        elif src in ("protected", "legacy"):
            self.grok_key.setPlaceholderText("บันทึกไว้แล้ว (เข้ารหัส DPAPI) — ใส่ใหม่เพื่อเปลี่ยน")
        else:
            self.grok_key.setPlaceholderText("xai-… หรือตั้ง XAI_API_KEY ใน environment")
        self.grok_model = QLineEdit(state.grok.model)
        btn_grok_validate = QPushButton("ตรวจสอบ Grok")
        btn_grok_validate.clicked.connect(self.validate_grok)
        self.btn_grok_analyze = QPushButton("ให้ Grok วิเคราะห์ตำแหน่งนี้")
        self.btn_grok_analyze.setObjectName("primaryButton")
        self.btn_grok_analyze.clicked.connect(self.analyze_grok)
        btn_clear_key = QPushButton("ลบ Key ที่บันทึก")
        btn_clear_key.clicked.connect(self.clear_grok_key)
        self.lbl_grok_status = QLabel("ยังไม่ได้ตรวจสอบ")
        self.lbl_grok_status.setObjectName("mutedLabel")
        self.lbl_grok_status.setWordWrap(True)

        grok_form = QFormLayout()
        grok_form.addRow("API Key", self.grok_key)
        grok_form.addRow("โมเดล", self.grok_model)
        grok_btns = QHBoxLayout()
        grok_btns.addWidget(btn_grok_validate)
        grok_btns.addWidget(btn_clear_key)
        grok_btns.addWidget(self.btn_grok_analyze, 1)

        grok_box = QGroupBox("Grok (xAI API — ตัวเลือกเสริม)")
        gl = QVBoxLayout(grok_box)
        gl.addLayout(grok_form)
        gl.addLayout(grok_btns)
        gl.addWidget(self.lbl_grok_status)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(box)
        layout.addWidget(grok_box)
        layout.addWidget(QLabel("ผลลัพธ์"))
        layout.addWidget(self.output, 1)

        note = QLabel(
            "Stockfish วิเคราะห์บนเครื่องคุณเท่านั้น — ถ้าใช้ Grok โปรแกรมจะส่งเฉพาะ FEN "
            "ของตำแหน่งไปยัง xAI เมื่อคุณกดปุ่มเท่านั้น และไม่เดินหมากแทนคุณ"
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

    def browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "เลือก stockfish.exe",
            "",
            "Executable (*.exe);;All files (*.*)",
        )
        if path:
            self.path_edit.setText(path)
            self.state.engine.set_path(path)

    def validate(self) -> None:
        self.state.engine.set_path(self.path_edit.text().strip())
        ok, msg = self.state.engine.validate()
        self.lbl_engine_status.setText(msg)
        self.lbl_engine_status.setObjectName("statusOk" if ok else "statusError")
        self.lbl_engine_status.style().unpolish(self.lbl_engine_status)
        self.lbl_engine_status.style().polish(self.lbl_engine_status)
        self.state.status_message.emit(msg)

    def save_settings(self) -> None:
        self.state.engine.set_path(self.path_edit.text().strip())
        eng = self.state.profile.engine
        eng.path = self.path_edit.text().strip()
        eng.preset = self.preset.currentData()
        eng.multipv = self.multipv.value()
        eng.threads = self.threads.value()
        eng.skill_level = self.skill.value()
        eng.movetime_ms = self.movetime.value()
        preset = PRESETS.get(eng.preset, PRESETS["balanced"])
        if eng.preset in PRESETS:
            eng.movetime_ms = preset["movetime_ms"]
            self.movetime.setValue(eng.movetime_ms)
        self.state.config.set("stockfish_path", eng.path)
        self._apply_grok_settings()
        self.state.config.save()
        self.state.save_profile()
        self.state.status_message.emit("บันทึกการตั้งค่า Engine แล้ว")

    def _apply_grok_settings(self) -> None:
        typed = self.grok_key.text().strip()
        if typed:
            # New key entered — encrypt to disk (never plaintext)
            self.state.config.set_grok_api_key(typed)
            self.grok_key.clear()
            self.grok_key.setPlaceholderText(
                "บันทึกไว้แล้ว (เข้ารหัส DPAPI) — ใส่ใหม่เพื่อเปลี่ยน"
            )
        # Reload resolved key (env > protected)
        key = self.state.config.get_grok_api_key()
        model = self.grok_model.text().strip()
        self.state.grok.configure(key, model)
        self.grok_model.setText(self.state.grok.model)
        self.state.config.set("grok_model", self.state.grok.model)

    def clear_grok_key(self) -> None:
        self.grok_key.clear()
        self.state.config.set_grok_api_key("")
        self.state.config.save()
        self.state.grok.configure("", self.grok_model.text())
        src = self.state.config.grok_api_key_source()
        if src == "env":
            self.lbl_grok_status.setText(
                "ลบ key บนดิสก์แล้ว — ยังใช้ได้จาก environment variable"
            )
            self.grok_key.setPlaceholderText(
                "ใช้จาก environment (XAI_API_KEY) — ไม่เขียนลงดิสก์"
            )
            self.state.grok.configure(self.state.config.get_grok_api_key(), self.grok_model.text())
        else:
            self.lbl_grok_status.setText("ลบ API key ที่บันทึกแล้ว")
            self.grok_key.setPlaceholderText("xai-… หรือตั้ง XAI_API_KEY ใน environment")
        self.state.status_message.emit("ลบ Grok API key แล้ว")

    def validate_grok(self) -> None:
        self._apply_grok_settings()
        self.state.config.save()
        self.lbl_grok_status.setText("กำลังตรวจสอบ…")
        self._grok_validate_worker = GrokValidateWorker(self.state)
        self._grok_validate_worker.done.connect(self._on_grok_validated)
        self._grok_validate_worker.start()

    def _on_grok_validated(self, ok: bool, msg: str) -> None:
        self.lbl_grok_status.setText(msg)
        self.lbl_grok_status.setObjectName("statusOk" if ok else "statusError")
        self.lbl_grok_status.style().unpolish(self.lbl_grok_status)
        self.lbl_grok_status.style().polish(self.lbl_grok_status)
        self.state.status_message.emit(msg)

    def analyze_grok(self) -> None:
        self._apply_grok_settings()
        self.state.config.save()
        self.btn_grok_analyze.setEnabled(False)
        self.output.setPlainText(f"กำลังถาม Grok ({self.state.grok.model})…")
        self._grok_worker = GrokWorker(self.state)
        self._grok_worker.finished_ok.connect(self._on_grok_result)
        self._grok_worker.failed.connect(self._on_grok_fail)
        self._grok_worker.start()

    def _on_grok_result(self, result) -> None:
        self.btn_grok_analyze.setEnabled(True)
        if result.error:
            self.output.setPlainText(result.error)
            self.state.status_message.emit("Grok วิเคราะห์ไม่สำเร็จ")
            return
        self.state.last_analysis = result
        self.state.analysis_changed.emit()
        line = result.lines[0]
        self.output.setPlainText(
            "\n".join(
                [
                    f"— Grok ({self.state.grok.model}) —",
                    f"FEN: {result.fen}",
                    f"Best: {result.best_move_san} ({result.best_move_uci})",
                    "",
                    line.explanation_th,
                ]
            )
        )
        self.state.status_message.emit(f"Grok Best: {result.best_move_san}")

    def _on_grok_fail(self, msg: str) -> None:
        self.btn_grok_analyze.setEnabled(True)
        self.output.setPlainText(msg)
        QMessageBox.warning(self, "Grok วิเคราะห์ล้มเหลว", msg)

    def analyze(self) -> None:
        self.save_settings()
        self.output.setPlainText("กำลังวิเคราะห์…")
        self._worker = AnalyzeWorker(self.state)
        self._worker.finished_ok.connect(self._on_result)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_result(self, result) -> None:
        self.state.last_analysis = result
        self.state.analysis_changed.emit()
        if result.error:
            self.output.setPlainText(result.error)
            return
        lines = [
            f"FEN: {result.fen}",
            f"Best: {result.best_move_san} ({result.best_move_uci})",
            f"Eval: {result.evaluation.format_display()}",
            "",
        ]
        for line in result.lines:
            pv = " ".join(line.pv_san[:8])
            lines.append(
                f"#{line.multipv}  {line.move_san}  {line.score.format_display()}  d{line.depth}"
            )
            lines.append(f"    PV: {pv}")
            lines.append(f"    {line.explanation_th}")
            lines.append("")
        self.output.setPlainText("\n".join(lines))
        self.state.status_message.emit(f"Best: {result.best_move_san}")

    def _on_fail(self, msg: str) -> None:
        self.output.setPlainText(msg)
        QMessageBox.warning(self, "วิเคราะห์ล้มเหลว", msg)
