"""Loads track configs from tracks/*.json. A track = persona + the fields to collect."""
import json
from pathlib import Path

TRACKS_DIR = Path(__file__).resolve().parent.parent / "tracks"


def load_tracks() -> dict[str, dict]:
    tracks = {}
    for path in sorted(TRACKS_DIR.glob("*.json")):
        track = json.loads(path.read_text(encoding="utf-8"))
        tracks[path.stem] = track
    return tracks
