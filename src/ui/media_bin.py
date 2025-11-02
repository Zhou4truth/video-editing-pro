from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MediaBinPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("Media Bin", self)
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("Search assets...")
        layout.addWidget(self.filter_edit)

        self.asset_list = QListWidget(self)
        layout.addWidget(self.asset_list, 1)

        button_row = QHBoxLayout()
        self.import_button = QPushButton("Import", self)
        self.remove_button = QPushButton("Remove", self)
        self.reveal_button = QPushButton("Reveal", self)
        button_row.addWidget(self.import_button)
        button_row.addWidget(self.remove_button)
        button_row.addWidget(self.reveal_button)
        layout.addLayout(button_row)

    def add_asset(self, asset_id: str, path: str) -> None:
        self.asset_list.addItem(f"{asset_id}: {path}")

    def clear_assets(self) -> None:
        self.asset_list.clear()
