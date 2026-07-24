"""Shared application state for GUI pages."""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Signal

from board_detection.color_mapping import TeamMapping, default_team_mapping
from board_detection.orientation import BoardOrientation
from capture.base import CaptureRegion
from chess_core.board_state import BoardState
from chess_engine.analysis_types import AnalysisResult
from chess_engine.grok_engine import DEFAULT_GROK_MODEL, GrokEngine
from chess_engine.stockfish_engine import StockfishEngine
from move_detection.service import MoveDetectionService
from overlay.overlay_window import OverlayWindow
from profiles.manager import ProfileManager
from profiles.models import Profile
from storage.config_store import ConfigStore
from vision.perspective import PerspectiveCalibration, default_corners
from vision.templates import TemplateLibrary


class AppState(QObject):
    board_changed = Signal()
    analysis_changed = Signal()
    capture_changed = Signal()
    profile_changed = Signal()
    status_message = Signal(str)
    detection_message = Signal(str)
    move_detected = Signal(object)  # MoveHypothesis
    drift_warning = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.config = ConfigStore()
        self.profiles = ProfileManager()
        self.profile: Profile = self.profiles.ensure_default()
        self.board_state = BoardState.standard()
        self.start_fen = self.board_state.fen()
        self.team = default_team_mapping(self.profile.user_is_white)
        self.team.white_label = self.profile.team_labels.get("white", "Light Cherry")
        self.team.black_label = self.profile.team_labels.get("black", "Dark Cherry")
        self.orientation = BoardOrientation(
            rotation_deg=self.profile.orientation_deg,
            my_pieces_at_bottom=self.profile.my_pieces_at_bottom,
            user_is_white=self.profile.user_is_white,
        )
        self.region: Optional[CaptureRegion] = (
            CaptureRegion.from_list(self.profile.region) if self.profile.region else None
        )
        self.monitor_id = self.profile.monitor_id
        if self.profile.corners:
            self.calibration = PerspectiveCalibration.from_list(
                self.profile.corners, self.profile.warped_size
            )
        else:
            self.calibration = PerspectiveCalibration(
                corners=default_corners(800, 800), warped_size=self.profile.warped_size
            )
        self.last_roi_bgr: Optional[np.ndarray] = None
        self.last_warped_bgr: Optional[np.ndarray] = None
        self.last_analysis: Optional[AnalysisResult] = None
        self.last_detection_confidence: float = 1.0
        self.capture_active = False
        self.capture_paused = False
        self.auto_analyze_on_user_turn = True
        self.auto_recalibrate = bool(self.config.get("auto_recalibrate", False))
        self.board_screenshots: list[tuple[str, Optional[np.ndarray]]] = []  # fen, optional img
        self.save_move_screenshots = bool(self.config.get("save_move_screenshots", False))

        engine_path = self.profile.engine.path or self.config.get("stockfish_path", "")
        self.engine = StockfishEngine(engine_path)
        self.grok = GrokEngine(
            api_key=self.config.get_grok_api_key(),
            model=str(self.config.get("grok_model", "") or DEFAULT_GROK_MODEL),
        )

        self.detection = MoveDetectionService()
        self.detection.configure(
            self.orientation,
            confidence_threshold=self.profile.thresholds.confidence,
            debounce_ms=self.profile.thresholds.debounce_ms,
        )
        self.detection.reset(self.board_state.board)

        self.templates = TemplateLibrary()
        self.overlay = OverlayWindow()
        ov = self.profile.overlay
        self.overlay.set_style(ov.arrow_opacity, ov.arrow_thickness)

    def refresh_detection_config(self) -> None:
        self.detection.configure(
            self.orientation,
            confidence_threshold=self.profile.thresholds.confidence,
            debounce_ms=self.profile.thresholds.debounce_ms,
        )
        self.detection.auto_recalibrate = self.auto_recalibrate

    def apply_profile(self, profile: Profile) -> None:
        self.profile = profile
        self.team = TeamMapping(
            white_label=profile.team_labels.get("white", "Light Cherry"),
            black_label=profile.team_labels.get("black", "Dark Cherry"),
            user_is_white=profile.user_is_white,
        )
        self.orientation = BoardOrientation(
            rotation_deg=profile.orientation_deg,
            my_pieces_at_bottom=profile.my_pieces_at_bottom,
            user_is_white=profile.user_is_white,
        )
        self.region = CaptureRegion.from_list(profile.region)
        self.monitor_id = profile.monitor_id
        if profile.corners:
            self.calibration = PerspectiveCalibration.from_list(
                profile.corners, profile.warped_size
            )
        if profile.engine.path:
            self.engine.set_path(profile.engine.path)
        self.refresh_detection_config()
        self.detection.reset(self.board_state.board)
        ov = profile.overlay
        self.overlay.set_style(ov.arrow_opacity, ov.arrow_thickness)
        self.profile_changed.emit()

    def sync_profile_from_state(self) -> None:
        p = self.profile
        p.monitor_id = self.monitor_id
        if self.region:
            p.region = self.region.to_list()
        p.corners = self.calibration.as_list()
        p.orientation_deg = self.orientation.rotation_deg
        p.my_pieces_at_bottom = self.orientation.my_pieces_at_bottom
        p.user_is_white = self.orientation.user_is_white
        p.team_labels = {
            "white": self.team.white_label,
            "black": self.team.black_label,
        }
        p.engine.path = self.engine.path
        p.warped_size = self.calibration.warped_size
        # Never persist overlay as enabled — prevents stuck overlay after crash
        p.overlay.enabled = False
        p.overlay.arrow_opacity = self.overlay._opacity
        p.overlay.arrow_thickness = self.overlay._thickness

    def save_profile(self) -> None:
        self.sync_profile_from_state()
        self.profiles.save(self.profile)
        self.config.set("active_profile", self.profile.name)
        self.config.set("stockfish_path", self.engine.path)
        self.config.set("auto_recalibrate", self.auto_recalibrate)
        self.config.set("save_move_screenshots", self.save_move_screenshots)
        self.config.save()
        self.status_message.emit(f"Saved Profile: {self.profile.name}")

    def update_overlay_geometry(self) -> None:
        if self.region is None:
            return
        from vision.grid import BoardGrid

        grid = BoardGrid(size=self.calibration.warped_size, orientation=self.orientation)
        self.overlay.set_board_geometry(self.region, self.calibration, grid)

    def push_analysis_to_overlay(self) -> None:
        a = self.last_analysis
        if not a or not a.ok:
            self.overlay.clear()
            return
        arrows = []
        for i, line in enumerate(a.lines):
            if len(line.move_uci) >= 4:
                arrows.append((line.move_uci[0:2], line.move_uci[2:4], i))
        self.overlay.set_arrows(
            arrows,
            label=f"Best: {a.best_move_san}",
            evaluation=a.evaluation.format_display(),
        )
        self.update_overlay_geometry()
