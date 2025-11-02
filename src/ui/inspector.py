from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)


class InspectorPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Inspector", self)
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        clip_group = QGroupBox("Clip Properties", self)
        clip_form = QFormLayout(clip_group)
        clip_form.setContentsMargins(8, 8, 8, 8)
        self.start_spin = self._seconds_spin()
        self.in_spin = self._seconds_spin()
        self.out_spin = self._seconds_spin()
        clip_form.addRow("Start (s)", self.start_spin)
        clip_form.addRow("In (s)", self.in_spin)
        clip_form.addRow("Out (s)", self.out_spin)

        self.muted_checkbox = QCheckBox("Muted", clip_group)
        self.locked_checkbox = QCheckBox("Locked", clip_group)
        clip_form.addRow(self.muted_checkbox)
        clip_form.addRow(self.locked_checkbox)
        layout.addWidget(clip_group)

        effect_group = QGroupBox("Effect Parameters", self)
        effect_form = QFormLayout(effect_group)
        effect_form.setContentsMargins(8, 8, 8, 8)
        self.effect_combo = QComboBox(effect_group)
        self.effect_combo.addItems(["None", "Mosaic", "Blur"])
        self.blocks_spin = self._int_spin(4, 256, 24)
        self.radius_spin = self._int_spin(3, 101, 11, step=2)
        effect_form.addRow("Effect", self.effect_combo)
        effect_form.addRow("Blocks", self.blocks_spin)
        effect_form.addRow("Radius", self.radius_spin)
        layout.addWidget(effect_group)

        keyframe_group = QGroupBox("Keyframes", self)
        keyframe_layout = QVBoxLayout(keyframe_group)
        keyframe_layout.setContentsMargins(8, 8, 8, 8)
        self.keyframe_list = QListWidget(keyframe_group)
        self.keyframe_list.addItem("00:00:00 (x=0.30, y=0.30)")
        self.keyframe_list.addItem("00:00:02 (x=0.45, y=0.32)")
        self.keyframe_list.addItem("00:00:04 (x=0.60, y=0.38)")
        keyframe_layout.addWidget(self.keyframe_list)

        self.easing_combo = QComboBox(keyframe_group)
        self.easing_combo.addItems(["Linear"])
        keyframe_layout.addWidget(self.easing_combo)
        layout.addWidget(keyframe_group, 1)

    def _seconds_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setRange(0.0, 10_000.0)
        spin.setDecimals(3)
        spin.setSingleStep(0.033)
        return spin

    def _int_spin(self, minimum: int, maximum: int, value: int, step: int = 1) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setDecimals(0)
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setValue(value)
        return spin
