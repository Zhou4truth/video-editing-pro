Video Editor MVP
================

This repository hosts the MVP implementation of a Windows-focused, Python + Qt
desktop video editor. The goal is to provide a lightweight editing workflow
including timeline edits, mosaic/blur effects with keyframes, audio ducking, and
ffmpeg-based export, packaged for end users with a Windows installer.

Repository Layout
-----------------
- `src/` – Application sources (core engine, UI, IO layers).
- `resources/` – Static assets bundled with the build (styles, ffmpeg binaries).
- `tools/` – Build scripts for PyInstaller + Inno Setup.
- `tests/` – Unit tests covering critical behaviours.
- `samples/` – Demo project assets to verify the export pipeline.

Getting Started
---------------
For a fresh checkout:
1. Create and activate a Python 3.11 virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Launch the app for development via `python -m src.app`.

The README will evolve with detailed setup and usage notes as implementation
progresses through the roadmap.
