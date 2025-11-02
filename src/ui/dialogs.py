from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileIconProvider,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)


class ProgressDialog(QDialog):
    cancelled = Signal()

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Starting...", self)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        button_box = QDialogButtonBox(self)
        self.cancel_button = button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.cancel_button.clicked.connect(self._handle_cancel)
        layout.addWidget(button_box)

    def update_progress(self, value: Optional[float], message: str | None = None) -> None:
        if message:
            self.status_label.setText(message)
        if value is None:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(max(0.0, min(value, 1.0)) * 100))

    def _handle_cancel(self) -> None:
        self.cancelled.emit()
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Cancelling...")


class TaskWorker(QObject):
    progress = Signal(object, str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, task_fn, *args, **kwargs) -> None:
        super().__init__()
        self._task_fn = task_fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    def _is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        try:
            result = self._task_fn(
                progress_callback=self._progress_proxy,
                cancel_flag=self._is_cancelled,
                *self._args,
                **self._kwargs,
            )
            if self._cancelled:
                self.cancelled.emit()
            else:
                self.finished.emit(result)
        except Exception as exc:  # pylint: disable=broad-except
            self.failed.emit(str(exc))

    def _progress_proxy(self, value: Optional[float], message: str | None = None) -> None:
        self.progress.emit(value, message or "")


class SettingsDialog(QDialog):
    def __init__(
        self,
        fps: int,
        width: int,
        height: int,
        autosave_interval: int,
        ui_scale: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        form = QFormLayout(self)

        self.fps_spin = QSpinBox(self)
        self.fps_spin.setRange(15, 240)
        self.fps_spin.setValue(fps)
        form.addRow("Frames per second", self.fps_spin)

        self.width_spin = QSpinBox(self)
        self.width_spin.setRange(320, 7680)
        self.width_spin.setValue(width)
        form.addRow("Resolution width", self.width_spin)

        self.height_spin = QSpinBox(self)
        self.height_spin.setRange(240, 4320)
        self.height_spin.setValue(height)
        form.addRow("Resolution height", self.height_spin)

        self.autosave_spin = QSpinBox(self)
        self.autosave_spin.setRange(10, 3600)
        self.autosave_spin.setValue(autosave_interval)
        form.addRow("Autosave interval (s)", self.autosave_spin)

        self.ui_scale_spin = QDoubleSpinBox(self)
        self.ui_scale_spin.setRange(0.5, 2.5)
        self.ui_scale_spin.setSingleStep(0.1)
        self.ui_scale_spin.setValue(ui_scale)
        form.addRow("UI scale", self.ui_scale_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> tuple[int, int, int, int, float]:
        return (
            int(self.fps_spin.value()),
            int(self.width_spin.value()),
            int(self.height_spin.value()),
            int(self.autosave_spin.value()),
            float(self.ui_scale_spin.value()),
        )


@dataclass
class AutosaveEntry:
    path: Path
    modified_time: float


class CrashRecoveryDialog(QDialog):
    def __init__(self, entries: Iterable[AutosaveEntry], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recover Autosave")
        self.setModal(True)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Autosave files from the previous session were found:", self))

        self.list_widget = QListWidget(self)
        icon_provider = QFileIconProvider()
        for entry in entries:
            item = QListWidgetItem(icon_provider.icon(QFileIconProvider.File), entry.path.name)
            item.setData(Qt.UserRole, entry.path)
            time_label = datetime.fromtimestamp(entry.modified_time).strftime("%Y-%m-%d %H:%M:%S")
            item.setToolTip(f"{entry.path}\nModified: {time_label}")
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(self)
        self.open_button = buttons.addButton("Open", QDialogButtonBox.AcceptRole)
        self.discard_button = buttons.addButton("Discard", QDialogButtonBox.DestructiveRole)
        self.cancel_button = buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.open_button.clicked.connect(self.accept)
        self.discard_button.clicked.connect(self._discard_and_accept)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self._discard_selected = False

    def selected_path(self) -> Optional[Path]:
        item = self.list_widget.currentItem()
        if not item:
            return None
        return Path(item.data(Qt.UserRole))

    def discard_selected(self) -> bool:
        return self._discard_selected

    def _discard_and_accept(self) -> None:
        self._discard_selected = True
        self.accept()


def show_codec_error(parent: QWidget, asset_path: Path, message: str) -> None:
    QMessageBox.critical(
        parent,
        "Codec Error",
        f"Could not decode '{asset_path}'.\n\n{message}\n\n"
        "Please ensure the necessary codecs are installed or convert the media to a supported format.",
    )
