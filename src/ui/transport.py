from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QToolButton,
    QWidget,
)


class TransportBar(QWidget):
    play_requested = Signal()
    pause_requested = Signal()
    step_requested = Signal(int)
    goto_in_requested = Signal()
    goto_out_requested = Signal()
    zoom_changed = Signal(int)
    fps_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.play_button = QToolButton(self)
        self.play_button.setText("Play")
        self.play_button.clicked.connect(self.play_requested.emit)
        layout.addWidget(self.play_button)

        self.pause_button = QToolButton(self)
        self.pause_button.setText("Pause")
        self.pause_button.clicked.connect(self.pause_requested.emit)
        layout.addWidget(self.pause_button)

        self.step_back_button = QToolButton(self)
        self.step_back_button.setText("Step -1")
        self.step_back_button.clicked.connect(lambda: self.step_requested.emit(-1))
        layout.addWidget(self.step_back_button)

        self.step_forward_button = QToolButton(self)
        self.step_forward_button.setText("Step +1")
        self.step_forward_button.clicked.connect(lambda: self.step_requested.emit(1))
        layout.addWidget(self.step_forward_button)

        self.goto_in_button = QToolButton(self)
        self.goto_in_button.setText("Go In")
        self.goto_in_button.clicked.connect(self.goto_in_requested.emit)
        layout.addWidget(self.goto_in_button)

        self.goto_out_button = QToolButton(self)
        self.goto_out_button.setText("Go Out")
        self.goto_out_button.clicked.connect(self.goto_out_requested.emit)
        layout.addWidget(self.goto_out_button)

        layout.addItem(QSpacerItem(12, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

        zoom_label = QLabel("Timeline Zoom", self)
        layout.addWidget(zoom_label)

        self.zoom_slider = QSlider(Qt.Horizontal, self)
        self.zoom_slider.setRange(10, 400)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.zoom_changed.emit)
        layout.addWidget(self.zoom_slider)

        layout.addStretch(1)

        fps_label = QLabel("FPS", self)
        layout.addWidget(fps_label)

        self.fps_combo = QComboBox(self)
        self.fps_combo.currentIndexChanged.connect(self._on_fps_changed)
        layout.addWidget(self.fps_combo)

    def set_available_fps(self, fps_values: Iterable[int], current: int) -> None:
        self.fps_combo.blockSignals(True)
        self.fps_combo.clear()
        for value in fps_values:
            self.fps_combo.addItem(f"{value}", value)
        index = self.fps_combo.findData(current)
        if index == -1 and self.fps_combo.count() > 0:
            index = 0
        if index >= 0:
            self.fps_combo.setCurrentIndex(index)
        self.fps_combo.blockSignals(False)
        if index >= 0:
            self._emit_current_fps()

    def _on_fps_changed(self, _: int) -> None:
        self._emit_current_fps()

    def _emit_current_fps(self) -> None:
        data = self.fps_combo.currentData()
        if isinstance(data, int):
            self.fps_changed.emit(data)
