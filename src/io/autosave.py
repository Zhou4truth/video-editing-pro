"""Autosave management."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from ..core.project_model import Project, ProjectStore


class AutosaveManager:
    def __init__(self, store: ProjectStore, directory: Path) -> None:
        self.store = store
        self.directory = directory
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            interval = max(self.store.project.settings.autosave_interval_sec, 10)
            time.sleep(interval)
            project = self.store.project
            project.autosave(self.directory)
