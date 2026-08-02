"""PyInstaller entry shim -- the real application lives in src/yt_dlp_gui/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from yt_dlp_gui.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
