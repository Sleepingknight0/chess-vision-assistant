"""Position editor page."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.widgets.fen_editor import FenEditor
from gui.widgets.position_editor import PositionEditorWidget

if TYPE_CHECKING:
    from gui.app_state import AppState


class PositionPage(QWidget):
    def __init__(self, state: AppState, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.state = state

        title = QLabel("Position Editor")
        title.setObjectName("titleLabel")
        hint = QLabel(
            "Set the starting position in 3 ways: standard / place pieces / paste FEN — "
            "use when detection is wrong or you start from a non-standard position"
        )
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)

        self.editor = PositionEditorWidget()
        self.editor.set_fen(state.board_state.fen())
        self.editor.position_changed.connect(self._on_pos)

        self.fen_editor = FenEditor()
        self.fen_editor.set_fen(state.board_state.fen())
        self.fen_editor.fen_applied.connect(self._on_fen)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self.fen_editor)
        layout.addWidget(self.editor, 1)

        state.board_changed.connect(self._sync_from_state)

    def _on_pos(self, fen: str) -> None:
        self.state.board_state.set_fen(fen)
        self.state.start_fen = fen
        self.fen_editor.set_fen(fen)
        self.state.detection.reset(self.state.board_state.board)
        self.state.board_changed.emit()

    def _on_fen(self, fen: str) -> None:
        self.state.board_state.set_fen(fen)
        self.state.start_fen = fen
        self.editor.set_fen(fen)
        self.state.detection.reset(self.state.board_state.board)
        self.state.board_changed.emit()
        self.state.status_message.emit("FEN applied")

    def _sync_from_state(self) -> None:
        fen = self.state.board_state.fen()
        # Avoid feedback loops if same
        if self.editor.fen().split()[0] != fen.split()[0]:
            self.editor.set_fen(fen)
        self.fen_editor.set_fen(fen)
