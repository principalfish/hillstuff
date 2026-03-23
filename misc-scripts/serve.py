"""
Serves peaks_map.html and lists/serves local CSVs.

Usage:
    python serve.py        # serves on http://localhost:8000
    python serve.py 9000   # custom port
"""

import glob
import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/csvs":
            csvs = sorted(os.path.basename(f) for f in glob.glob(os.path.join(SCRIPT_DIR, "*.csv")))
            body = json.dumps(csvs).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, format: str, *args: object) -> None:
        pass  # suppress request noise


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"Serving at http://localhost:{port}/peaks_map.html")
    HTTPServer(("", port), Handler).serve_forever()
