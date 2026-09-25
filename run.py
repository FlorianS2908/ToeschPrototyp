"""Local runner: bind the port first, open the browser only after a healthy response."""

import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


def configuration() -> tuple[Path, int]:
    if not (3, 11) <= sys.version_info[:2] < (3, 15):
        raise ValueError("Python 3.11 bis 3.14 erforderlich. Empfohlen: Python 3.12.")
    directory = Path(
        os.environ.get("HOTEL_DATA_DIR", str(Path(__file__).parent / "data"))
    ).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=directory) as handle:
        handle.write(b"write-check")
    port = int(os.environ.get("HOTEL_PORT", "8000"))
    if not 1024 <= port <= 65535:
        raise ValueError("HOTEL_PORT muss zwischen 1024 und 65535 liegen.")
    return directory, port


def open_when_ready(url: str):
    for _ in range(60):
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1) as response:
                if json.load(response).get("app") == "staydesk":
                    webbrowser.open(url)
                    return
        except (OSError, ValueError, urllib.error.URLError):
            time.sleep(0.25)
    print("Browser konnte nicht automatisch geoeffnet werden. Adresse: " + url)


def main() -> int:
    try:
        directory, port = configuration()
        os.environ["HOTEL_DATA_DIR"] = str(directory)
        import uvicorn

        # Holding this socket avoids the port-check/start race, including on Windows.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            if sys.platform == "win32":
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", port))
            listener.listen(128)
            url = f"http://127.0.0.1:{port}"
            print(f"Staydesk startet: {url}\nDaten: {directory}\nBeenden: Strg+C")
            if os.environ.get("HOTEL_NO_BROWSER") != "1":
                threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
            server = uvicorn.Server(uvicorn.Config("app.main:app", log_level="info"))
            server.run(sockets=[listener])
            return 0 if server.started else 1
    except (OSError, ValueError, ImportError) as error:
        print(
            f"Start fehlgeschlagen: {error}\n"
            "Pruefen Sie Abhaengigkeiten, Schreibrechte und ob der Port bereits belegt ist.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
