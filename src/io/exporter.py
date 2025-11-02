"""Timeline export pipeline using ffmpeg."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Dict, Optional

import cv2
import numpy as np
import soundfile as sf

from ..core.audio.mixer import AudioClipBuffer, mix_to_bus
from ..core.compositor import Compositor
from ..core.decoder import MediaDecoder
from ..core.project_model import Project


EXPORT_PRESETS = {
    "draft_720p": {
        "width": 1280,
        "height": 720,
        "crf": 28,
        "preset": "veryfast",
        "audio_bitrate": "128k",
    },
    "standard_1080p": {
        "width": 1920,
        "height": 1080,
        "crf": 23,
        "preset": "fast",
        "audio_bitrate": "192k",
    },
}


class Exporter:
    def __init__(self, project: Project, decoder: MediaDecoder, ffmpeg_path: Path) -> None:
        self.project = project
        self.decoder = decoder
        self.ffmpeg_path = ffmpeg_path

    def export(
        self,
        output_path: Path,
        preset: str,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_flag: Optional[Callable[[], bool]] = None,
    ) -> Path:
        if preset not in EXPORT_PRESETS:
            raise ValueError(f"Unknown preset {preset}")

        preset_opts = EXPORT_PRESETS[preset]
        fps = self.project.settings.fps
        duration = self.project.total_length_seconds()
        total_frames = max(int(np.ceil(duration * fps)), 1)

        compositor = Compositor(self.project, self.decoder)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            frame_dir = temp_dir_path / "frames"
            frame_dir.mkdir(parents=True, exist_ok=True)
            audio_path = temp_dir_path / "mix.wav"

            for index in range(total_frames):
                if cancel_flag and cancel_flag():
                    raise RuntimeError("Export cancelled")
                seconds = index / fps
                frame = compositor.render_frame(seconds)
                resized = cv2.resize(frame, (preset_opts["width"], preset_opts["height"]))
                frame_file = frame_dir / f"frame_{index:05d}.png"
                cv2.imwrite(str(frame_file), resized)
                if progress_callback:
                    progress_callback(index / total_frames)

            bus = self._render_audio_bus()
            sf.write(str(audio_path), bus, samplerate=48_000)

            frame_pattern = frame_dir / "frame_%05d.png"
            command = self._build_ffmpeg_command(frame_pattern, audio_path, output_path, fps, preset_opts)
            process = subprocess.run(command, capture_output=True, text=True)
            if process.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {process.stderr}")

        if progress_callback:
            progress_callback(1.0)
        return output_path

    def _build_ffmpeg_command(
        self,
        frame_pattern: Path,
        audio_path: Path,
        output_path: Path,
        fps: int,
        options: Dict,
    ):
        return [
            str(self.ffmpeg_path),
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frame_pattern),
            "-i",
            str(audio_path),
            "-c:v",
            "libx264",
            "-preset",
            options["preset"],
            "-crf",
            str(options["crf"]),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            options["audio_bitrate"],
            str(output_path),
        ]

    def _render_audio_bus(self) -> np.ndarray:
        sample_rate = 48_000
        buffers = []

        for track in self.project.tracks:
            if track.type != "audio" or track.muted:
                continue
            for clip in track.clips:
                asset = next((a for a in self.project.assets if a.id == clip.asset), None)
                if asset is None:
                    continue
                try:
                    audio_buffer = self.decoder.audio_segment(
                        asset.id, Path(asset.path), clip.in_point, clip.duration()
                    )
                except Exception:
                    continue
                adjusted = AudioClipBuffer(
                    clip=clip,
                    samples=audio_buffer.samples,
                    sample_rate=audio_buffer.rate,
                    start_time=clip.start,
                )
                buffers.append(adjusted)

        if not buffers:
            return np.zeros((1, 2), dtype=np.float32)
        return mix_to_bus(buffers, sample_rate)
