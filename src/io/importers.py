"""Import helpers for media assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional
import itertools

import numpy as np

from ..core.project_model import Asset, Project
from ..core.decoder import MediaDecoder
from ..core.audio.waveform import compute_waveform, save_waveform


VIDEO_EXT = {".mp4", ".mov", ".mkv"}
AUDIO_EXT = {".mp3", ".wav", ".aac"}


@dataclass
class ImportResult:
    assets: List[Asset]
    thumbnails: List[np.ndarray]


class MediaImporter:
    def __init__(self, project: Project, decoder: MediaDecoder) -> None:
        self.project = project
        self.decoder = decoder
        self._id_counter = itertools.count(1)

    def import_paths(
        self,
        paths: Iterable[Path],
        progress_callback: Optional[Callable[[Optional[float], str], None]] = None,
        cancel_flag: Optional[Callable[[], bool]] = None,
    ) -> ImportResult:
        assets: List[Asset] = []
        thumbnails: List[np.ndarray] = []

        path_list = list(paths)
        total = len(path_list) or 1
        existing_ids = {asset.id for asset in self.project.assets}

        for index, path in enumerate(path_list):
            if cancel_flag and cancel_flag():
                break

            if progress_callback:
                progress_callback(
                    (index / total),
                    f"Importing {path.name}",
                )

            asset_type = self._asset_type(path)
            if asset_type is None:
                continue
            asset_id = self._generate_id(asset_type, existing_ids)
            existing_ids.add(asset_id)
            asset = Asset(id=asset_id, path=str(path), type=asset_type, metadata={})
            assets.append(asset)

            try:
                thumbnail = self._create_thumbnail(asset)
            except Exception as exc:  # pylint: disable=broad-except
                raise RuntimeError(f"Failed to decode thumbnail for {path}: {exc}") from exc
            thumbnails.append(thumbnail)

            if asset_type == "audio":
                try:
                    self._generate_waveform(asset)
                except Exception as exc:  # pylint: disable=broad-except
                    raise RuntimeError(f"Failed to create waveform for {path}: {exc}") from exc

        if progress_callback:
            progress_callback(1.0, "Import complete")

        return ImportResult(assets=assets, thumbnails=thumbnails)

    def _asset_type(self, path: Path) -> str | None:
        suffix = path.suffix.lower()
        if suffix in VIDEO_EXT:
            return "video"
        if suffix in AUDIO_EXT:
            return "audio"
        return None

    def _generate_id(self, asset_type: str, existing_ids: set[str]) -> str:
        prefix = "v" if asset_type == "video" else "a"
        while True:
            candidate = f"{prefix}{next(self._id_counter)}"
            if candidate not in existing_ids:
                return candidate

    def _create_thumbnail(self, asset: Asset) -> np.ndarray:
        if asset.type == "audio":
            return np.zeros((180, 320, 3), dtype=np.uint8)
        frame = self.decoder.video_frame_at(asset.id, Path(asset.path), 0.0)
        return frame.image

    def _generate_waveform(self, asset: Asset) -> None:
        try:
            audio = self.decoder.audio_segment(asset.id, Path(asset.path), 0.0, None)
            waveform = compute_waveform(audio.samples)
            asset_path = Path(asset.path)
            if asset_path.suffix:
                target = asset_path.with_suffix(asset_path.suffix + ".waveform")
            else:
                target = asset_path.with_name(asset_path.name + ".waveform")
            if not target.parent.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
            save_waveform(target, waveform)
        except Exception:
            pass
