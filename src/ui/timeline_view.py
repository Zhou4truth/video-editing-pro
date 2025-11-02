from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)


class TimelineView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Timeline", self)
        title.setStyleSheet("font-weight: bold;")
        header.addWidget(title)
        header.addStretch(1)
        self.zoom_label = QLabel("Zoom: 100%", self)
        header.addWidget(self.zoom_label)
        layout.addLayout(header)

        self.track_area = QListWidget(self)
        self.track_area.addItem("V1  |--- Clip A ---|       |-- Clip B --|")
        self.track_area.addItem("A1  |--- Voice ----|")
        self.track_area.addItem("A2        |--- Music -------------|")
        self.track_area.setSelectionMode(QListWidget.NoSelection)
        layout.addWidget(self.track_area, 1)

        self.keyframe_lane = QListWidget(self)
        self.keyframe_lane.addItem("00:00:00 Linear")
        self.keyframe_lane.addItem("00:00:02 Linear")
        self.keyframe_lane.addItem("00:00:04 Linear")
        self.keyframe_lane.setVisible(False)
        layout.addWidget(self.keyframe_lane)

        playhead_line = QFrame(self)
        playhead_line.setFrameShape(QFrame.HLine)
        playhead_line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(playhead_line)

    def set_keyframe_lane_visible(self, visible: bool) -> None:
        self.keyframe_lane.setVisible(visible)

    def set_zoom_level(self, value: int) -> None:
        clamped = max(10, min(400, value))
        self.zoom_label.setText(f"Zoom: {clamped}%")
