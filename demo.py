"""Start each presentation with a fresh, isolated data directory; retain older runs."""
import os
import tempfile
from pathlib import Path

from run import main


def configure_demo() -> Path:
    root = Path(__file__).resolve().parent / ".demo"
    root.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="session-", dir=root))
    os.environ["HOTEL_DATA_DIR"] = str(directory)
    return directory


if __name__ == "__main__":
    configure_demo()
    raise SystemExit(main())
