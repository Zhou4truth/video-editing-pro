from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QSplitter, QStatusBar, QVBoxLayout, QWidget

from ..core.decoder import MediaDecoder
from ..core.project_model import ProjectStore
from .inspector import InspectorPanel
from .media_bin import MediaBinPanel
from .timeline_view import TimelineView
from .transport import TransportBar
from .viewer import ViewerPanel


class MainWindow(QMainWindow):
    """
    Main application window composing the editing layout.
    """

    def __init__(
        self,
        store: ProjectStore,
        decoder: MediaDecoder,
        resources_path: Path,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.store = store
        self.decoder = decoder
        self.resources_path = resources_path

        self.setWindowTitle("Video Editor MVP")
        self.resize(1440, 900)

        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(8, 8, 8, 8)
        central_layout.setSpacing(6)

        self.transport = TransportBar(self)
        fps_options = [23, 24, 25, 29, 30, 48, 50, 60]
        current_fps = self.store.project.settings.fps
        self.transport.set_available_fps(fps_options, current_fps)
        central_layout.addWidget(self.transport)

        body_splitter = QSplitter(Qt.Horizontal, self)
        body_splitter.setChildrenCollapsible(False)

        self.media_bin = MediaBinPanel(self)
        self.viewer = ViewerPanel(self)
        self.inspector = InspectorPanel(self)

        body_splitter.addWidget(self.media_bin)
        body_splitter.addWidget(self.viewer)
        body_splitter.addWidget(self.inspector)
        body_splitter.setStretchFactor(0, 1)
        body_splitter.setStretchFactor(1, 3)
        body_splitter.setStretchFactor(2, 2)

        central_layout.addWidget(body_splitter, 1)

        self.timeline = TimelineView(self)
        central_layout.addWidget(self.timeline)

        self.setCentralWidget(central)

        self.status = QStatusBar(self)
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

        self.viewer.keyframe_lane_toggled.connect(self.timeline.set_keyframe_lane_visible)
        self.transport.zoom_changed.connect(self.timeline.set_zoom_level)
        self.transport.fps_changed.connect(self._on_fps_changed)
        self.transport.play_requested.connect(lambda: self._notify("Playback started"))
        self.transport.pause_requested.connect(lambda: self._notify("Playback paused"))
        self.transport.step_requested.connect(lambda step: self._notify(f"Step {step:+d} frame"))
        self.transport.goto_in_requested.connect(lambda: self._notify("Playhead moved to In point"))
        self.transport.goto_out_requested.connect(lambda: self._notify("Playhead moved to Out point"))

        # Initialize timeline zoom label with current slider value
        self.timeline.set_zoom_level(self.transport.zoom_slider.value())

    def _notify(self, message: str) -> None:
        self.status.showMessage(message, 2000)

    def _on_fps_changed(self, fps: int) -> None:
        def update(project):
            project.settings.fps = fps

        self.store.update(update)
        self._notify(f"Timeline FPS set to {fps}")
