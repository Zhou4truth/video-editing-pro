from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QMainWindow,
    QMessageBox,
    QMenuBar,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..core.decoder import MediaDecoder
from ..core.project_model import Project, ProjectStore
from ..io.autosave import AutosaveManager
from ..io.exporter import Exporter
from ..io.importers import ImportResult, MediaImporter
from .dialogs import (
    AutosaveEntry,
    CrashRecoveryDialog,
    ProgressDialog,
    SettingsDialog,
    TaskWorker,
    show_codec_error,
)
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
        self.project_path: Optional[Path] = None
        self._active_threads: list[QThread] = []

        self.autosave_dir = Path.home() / ".video_editor_mvp" / "autosave"
        self.autosave_dir.mkdir(parents=True, exist_ok=True)
        self.autosave_manager = AutosaveManager(self.store, self.autosave_dir)
        self.autosave_manager.start()

        self.setWindowTitle("Video Editor MVP")
        self.resize(1440, 900)

        self._build_ui()
        self._create_actions()
        self._create_menus()
        self._connect_signals()
        self._refresh_media_bin()

        self._check_autosave_recovery()

    # ------------------------------------------------------------------ UI setup ---
    def _build_ui(self) -> None:
        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(8, 8, 8, 8)
        central_layout.setSpacing(6)

        self.transport = TransportBar(self)
        fps_options = [23, 24, 25, 29, 30, 48, 50, 60]
        self.transport.set_available_fps(fps_options, self.store.project.settings.fps)
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

        self.timeline.set_zoom_level(self.transport.zoom_slider.value())

    def _create_actions(self) -> None:
        self.new_project_action = QAction("New Project", self)
        self.open_project_action = QAction("Open Project...", self)
        self.save_project_action = QAction("Save Project", self)
        self.save_project_as_action = QAction("Save Project As...", self)
        self.import_media_action = QAction("Import Media...", self)
        self.export_action = QAction("Export...", self)
        self.settings_action = QAction("Settings...", self)
        self.exit_action = QAction("Exit", self)

    def _create_menus(self) -> None:
        menubar: QMenuBar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_project_action)
        file_menu.addAction(self.save_project_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.import_media_action)
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self.settings_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

    def _connect_signals(self) -> None:
        self.viewer.keyframe_lane_toggled.connect(self.timeline.set_keyframe_lane_visible)
        self.transport.zoom_changed.connect(self.timeline.set_zoom_level)
        self.transport.fps_changed.connect(self._on_fps_changed)
        self.transport.play_requested.connect(lambda: self._notify("Playback started"))
        self.transport.pause_requested.connect(lambda: self._notify("Playback paused"))
        self.transport.step_requested.connect(lambda step: self._notify(f"Step {step:+d} frame"))
        self.transport.goto_in_requested.connect(lambda: self._notify("Playhead moved to In point"))
        self.transport.goto_out_requested.connect(lambda: self._notify("Playhead moved to Out point"))

        self.new_project_action.triggered.connect(self._new_project)
        self.open_project_action.triggered.connect(self._open_project)
        self.save_project_action.triggered.connect(self._save_project)
        self.save_project_as_action.triggered.connect(lambda: self._save_project(save_as=True))
        self.import_media_action.triggered.connect(self._import_media)
        self.export_action.triggered.connect(self._export_project)
        self.settings_action.triggered.connect(self._open_settings)
        self.exit_action.triggered.connect(self.close)

        self.media_bin.import_button.clicked.connect(self._import_media)

    # ------------------------------------------------------------- project ops -----
    def _new_project(self) -> None:
        self._apply_project(Project(), project_path=None)
        self._notify("New project created")

    def _open_project(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            "Video Editor Project (*.vegproj);;All Files (*.*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            project = Project.load(path)
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Failed to open project", str(exc))
            return
        self._apply_project(project, project_path=path)
        self._notify(f"Loaded project {path.name}")

    def _save_project(self, save_as: bool = False) -> None:
        target_path = self.project_path
        if save_as or target_path is None:
            path_str, _ = QFileDialog.getSaveFileName(
                self,
                "Save Project",
                "",
                "Video Editor Project (*.vegproj);;All Files (*.*)",
            )
            if not path_str:
                return
            target_path = Path(path_str)
            if target_path.suffix.lower() != ".vegproj":
                target_path = target_path.with_suffix(".vegproj")

        try:
            self.store.project.save(target_path)
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Failed to save project", str(exc))
            return

        self.project_path = target_path
        self.store.project.autosave_token = target_path.stem
        self._notify(f"Project saved to {target_path.name}")

    def _apply_project(self, project: Project, project_path: Optional[Path]) -> None:
        def assign(current: Project) -> None:
            current.settings = project.settings
            current.assets = list(project.assets)
            current.tracks = list(project.tracks)
            current.metadata = dict(project.metadata)
            current.version = project.version
            current.autosave_token = project.autosave_token or project.metadata.get("name", "project")

        self.store.update(assign)
        self.project_path = project_path
        self.transport.set_available_fps(
            [23, 24, 25, 29, 30, 48, 50, 60],
            self.store.project.settings.fps,
        )
        self._refresh_media_bin()

    # -------------------------------------------------------------- autosave -------
    def _check_autosave_recovery(self) -> None:
        entries = [
            AutosaveEntry(path=item, modified_time=item.stat().st_mtime)
            for item in sorted(self.autosave_dir.glob("*.vegproj.autosave"))
        ]
        if not entries:
            return

        dialog = CrashRecoveryDialog(entries, self)
        if dialog.exec() != QDialog.Accepted:
            return

        selected = dialog.selected_path()
        if selected is None:
            return

        if dialog.discard_selected():
            selected.unlink(missing_ok=True)
            self._notify(f"Discarded autosave {selected.name}")
            return

        try:
            project = Project.load(selected)
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(self, "Recovery failed", str(exc))
            return

        self._apply_project(project, project_path=None)
        selected.unlink(missing_ok=True)
        self._notify(f"Recovered autosave {selected.name}")

    # ------------------------------------------------------------ media import -----
    def _import_media(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Media",
            "",
            "Media Files (*.mp4 *.mov *.mkv *.mp3 *.wav *.aac);;All Files (*.*)",
        )
        if not paths:
            return

        path_objects = [Path(path) for path in paths]

        def task(progress_callback, cancel_flag):
            importer = MediaImporter(self.store.project, self.decoder)
            return importer.import_paths(path_objects, progress_callback, cancel_flag)

        self._run_task(
            "Importing Media",
            task,
            on_success=self._on_import_complete,
        )

    def _on_import_complete(self, result: ImportResult) -> None:
        def append_assets(project: Project) -> None:
            for asset in result.assets:
                try:
                    project.add_asset(asset)
                except ValueError:
                    continue

        self.store.update(append_assets)
        self._refresh_media_bin()
        self._notify(f"Imported {len(result.assets)} asset(s)")

    # ------------------------------------------------------------------ export -----
    def _export_project(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Video",
            "",
            "MP4 Video (*.mp4);;All Files (*.*)",
        )
        if not path_str:
            return
        target_path = Path(path_str)
        if target_path.suffix.lower() != ".mp4":
            target_path = target_path.with_suffix(".mp4")

        ffmpeg_path = self.resources_path / "ffmpeg" / "ffmpeg.exe"
        if not ffmpeg_path.exists():
            QMessageBox.critical(
                self,
                "Export error",
                "ffmpeg executable was not found in resources/ffmpeg.\n"
                "Please ensure ffmpeg.exe is bundled with the application.",
            )
            return

        def task(progress_callback, cancel_flag):
            exporter = Exporter(self.store.project, self.decoder, ffmpeg_path)
            return exporter.export(
                output_path=target_path,
                preset="standard_1080p",
                progress_callback=progress_callback,
                cancel_flag=cancel_flag,
            )

        self._run_task(
            "Exporting Project",
            task,
            on_success=lambda _: self._notify(f"Export complete: {target_path.name}"),
        )

    # --------------------------------------------------------------- settings -----
    def _open_settings(self) -> None:
        project = self.store.project
        dialog = SettingsDialog(
            fps=project.settings.fps,
            width=project.settings.width,
            height=project.settings.height,
            autosave_interval=project.settings.autosave_interval_sec,
            ui_scale=project.settings.ui_scale,
            parent=self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        fps, width, height, autosave_interval, ui_scale = dialog.values()

        def apply_settings(current: Project) -> None:
            current.settings.fps = fps
            current.settings.width = width
            current.settings.height = height
            current.settings.autosave_interval_sec = autosave_interval
            current.settings.ui_scale = ui_scale

        self.store.update(apply_settings)
        self.transport.set_available_fps([23, 24, 25, 29, 30, 48, 50, 60], fps)
        self._notify("Settings updated")

    # -------------------------------------------------------------- utilities -----
    def _run_task(
        self,
        title: str,
        task_fn: Callable,
        on_success: Callable[[object], None],
    ) -> None:
        dialog = ProgressDialog(title, self)
        worker = TaskWorker(task_fn)
        thread = QThread(self)
        worker.moveToThread(thread)

        worker.progress.connect(lambda value, message: self._update_progress(dialog, value, message))

        def cleanup() -> None:
            thread.quit()
            thread.wait(2000)
            if thread in self._active_threads:
                self._active_threads.remove(thread)

        worker.finished.connect(lambda result: self._task_success(dialog, cleanup, on_success, result))
        worker.failed.connect(lambda message: self._task_failed(dialog, cleanup, message))
        worker.cancelled.connect(lambda: self._task_cancelled(dialog, cleanup))
        dialog.cancelled.connect(worker.request_cancel)

        thread.started.connect(worker.run)
        self._active_threads.append(thread)
        thread.start()
        dialog.exec()

    def _update_progress(self, dialog: ProgressDialog, value, message: str) -> None:
        effective_value = None if value is None else float(value)
        dialog.update_progress(effective_value, message if message else None)

    def _task_success(self, dialog: ProgressDialog, cleanup: Callable[[], None], on_success: Callable, result: object) -> None:
        cleanup()
        dialog.accept()
        on_success(result)

    def _task_failed(self, dialog: ProgressDialog, cleanup: Callable[[], None], message: str) -> None:
        cleanup()
        dialog.reject()
        lowered = message.lower()
        if "decode" in lowered:
            # Attempt to parse asset path from message
            try:
                path_part = message.split(" for ")[1].split(":")[0].strip()
                path = Path(path_part.strip("'\""))
            except Exception:  # pylint: disable=broad-except
                path = Path("unknown")
            show_codec_error(self, path, message)
        else:
            QMessageBox.critical(self, "Task failed", message)

    def _task_cancelled(self, dialog: ProgressDialog, cleanup: Callable[[], None]) -> None:
        cleanup()
        dialog.reject()
        self._notify("Operation cancelled")

    def _refresh_media_bin(self) -> None:
        self.media_bin.clear_assets()
        for asset in self.store.project.assets:
            self.media_bin.add_asset(asset.id, asset.path)

    def _notify(self, message: str) -> None:
        self.status.showMessage(message, 4000)

    def _on_fps_changed(self, fps: int) -> None:
        def update(project: Project) -> None:
            project.settings.fps = fps

        self.store.update(update)
        self._notify(f"Timeline FPS set to {fps}")

    # ---------------------------------------------------------------- lifecycle ---
    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self.autosave_manager.stop()
        for thread in list(self._active_threads):
            thread.quit()
            thread.wait(1000)
        super().closeEvent(event)
