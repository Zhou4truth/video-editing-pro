from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class ViewerCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self._safe_guides = True
        self._mosaic_roi = (0.3, 0.3, 0.4, 0.3)  # normalized x, y, w, h
        self._keyframe_lane_visible = False

    def set_keyframe_lane_visible(self, visible: bool) -> None:
        self._keyframe_lane_visible = visible
        self.update()

    def set_mosaic_roi(self, roi: tuple[float, float, float, float]) -> None:
        self._mosaic_roi = roi
        self.update()

    def set_safe_guides_enabled(self, enabled: bool) -> None:
        self._safe_guides = enabled
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(20, 20, 20))

        if self._safe_guides:
            self._draw_safe_guides(painter)
        self._draw_mosaic_overlay(painter)

        if self._keyframe_lane_visible:
            hint = "Keyframe lane visible"
        else:
            hint = "Keyframe lane hidden"
        painter.setPen(QColor(230, 230, 230))
        painter.drawText(self.rect().adjusted(8, 8, -8, -8), Qt.AlignTop | Qt.AlignLeft, hint)

    def _draw_safe_guides(self, painter: QPainter) -> None:
        rect = self.rect()
        margin_x = rect.width() * 0.1
        margin_y = rect.height() * 0.1
        safe_rect = QRect(
            int(rect.left() + margin_x),
            int(rect.top() + margin_y),
            int(rect.width() - 2 * margin_x),
            int(rect.height() - 2 * margin_y),
        )
        title_rect = QRect(
            int(rect.left() + margin_x * 0.6),
            int(rect.top() + margin_y * 0.6),
            int(rect.width() - 1.2 * margin_x),
            int(rect.height() - 1.2 * margin_y),
        )

        painter.setPen(QPen(QColor(120, 180, 255), 1, Qt.DashLine))
        painter.drawRect(safe_rect)
        painter.setPen(QPen(QColor(255, 200, 0), 1, Qt.DotLine))
        painter.drawRect(title_rect)

    def _draw_mosaic_overlay(self, painter: QPainter) -> None:
        rect = self.rect()
        x_norm, y_norm, w_norm, h_norm = self._mosaic_roi
        x = int(rect.left() + x_norm * rect.width())
        y = int(rect.top() + y_norm * rect.height())
        w = int(w_norm * rect.width())
        h = int(h_norm * rect.height())
        overlay_rect = QRect(x, y, w, h)

        painter.setPen(QPen(QColor(240, 240, 240), 2, Qt.DashLine))
        painter.drawRect(overlay_rect)

        handle_size = 10
        for point in self._handle_positions(overlay_rect):
            painter.fillRect(point.x() - handle_size // 2, point.y() - handle_size // 2, handle_size, handle_size, QColor(240, 240, 240))

    def _handle_positions(self, rect: QRect) -> list[QPoint]:
        points = [
            rect.topLeft(),
            rect.topRight(),
            rect.bottomLeft(),
            rect.bottomRight(),
            QPoint(rect.center().x(), rect.top()),
            QPoint(rect.center().x(), rect.bottom()),
            QPoint(rect.left(), rect.center().y()),
            QPoint(rect.right(), rect.center().y()),
        ]
        return points


class ViewerPanel(QWidget):
    keyframe_lane_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        label = QLabel("Viewer", self)
        label.setStyleSheet("font-weight: bold;")
        header.addWidget(label)
        header.addStretch(1)

        self.keyframe_toggle = QToolButton(self)
        self.keyframe_toggle.setText("Keyframe Lane")
        self.keyframe_toggle.setCheckable(True)
        self.keyframe_toggle.toggled.connect(self._on_keyframe_toggle)
        header.addWidget(self.keyframe_toggle)

        layout.addLayout(header)

        self.canvas = ViewerCanvas(self)
        layout.addWidget(self.canvas, 1)

        self.keyframe_list = QListWidget(self)
        self.keyframe_list.addItem("00:00:00 - Position (0.30, 0.30)")
        self.keyframe_list.addItem("00:00:02 - Position (0.45, 0.32)")
        self.keyframe_list.addItem("00:00:04 - Position (0.60, 0.38)")
        self.keyframe_list.setVisible(False)
        layout.addWidget(self.keyframe_list)

    def _on_keyframe_toggle(self, checked: bool) -> None:
        self.canvas.set_keyframe_lane_visible(checked)
        self.keyframe_list.setVisible(checked)
        self.keyframe_lane_toggled.emit(checked)
