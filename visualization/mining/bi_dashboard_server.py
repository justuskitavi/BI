from __future__ import annotations

import http.server
import socketserver
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
PORT = 8000


class OutputHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(OUTPUTS), **kwargs)


if __name__ == "__main__":
    url = f"http://localhost:{PORT}/html/index.html"
    print(f"Serving BI dashboard at {url}")
    print("Press Ctrl+C to stop the server.")
    webbrowser.open(url)
    with socketserver.TCPServer(("", PORT), OutputHandler) as httpd:
        httpd.serve_forever()
