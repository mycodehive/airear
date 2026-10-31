import os
from pathlib import Path


def data_dir() -> Path:
    path = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "AirEar"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return data_dir() / "airear.log"
