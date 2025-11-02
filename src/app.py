from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .core.project_model import Project, ProjectStore
from .core.decoder import MediaDecoder
from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    project = Project()
    store = ProjectStore(project)
    decoder = MediaDecoder()
    window = MainWindow(store, decoder, resources_path=Path(__file__).resolve().parent.parent / "resources")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
