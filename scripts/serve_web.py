"""Serve the built site (``build/web/``) with the headers ADR 007 asks of a host.

Usage: ``uv run python scripts/serve_web.py [--port 8040] [--dir build/web]``

Listens on 127.0.0.1 unless ``--host`` says otherwise; put Tailscale Serve or Funnel (or any
reverse proxy) in front of it. It sends a Content-Security-Policy that lets the page and its
worker load only files from this site, keeps no access log, and does not list folders.
"""

import argparse
import functools
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from os import PathLike
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent

#: Same policy as the page's <meta> tag; as a header it also covers the worker, which the
#: meta tag cannot. 'wasm-unsafe-eval' lets Pyodide compile WebAssembly.
CSP: Final = "; ".join(
    [
        "default-src 'none'",
        "script-src 'self' 'wasm-unsafe-eval'",
        "worker-src 'self'",
        "connect-src 'self'",
        "style-src 'self'",
        "img-src 'self'",
        "form-action 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
    ]
)
HEADERS: Final = {
    "Content-Security-Policy": CSP,
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    "Cache-Control": "no-cache",
}


class Handler(SimpleHTTPRequestHandler):
    server_version = "DraftWitness"
    sys_version = ""
    extensions_map = {  # noqa: RUF012 - the base class declares it as a plain dict
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".wasm": "application/wasm",
        ".json": "application/json",
        ".whl": "application/zip",
        ".zip": "application/zip",
        "": "text/plain",
    }

    def end_headers(self) -> None:
        for name, value in HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def list_directory(self, path: str | PathLike[str]) -> None:
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        """Keep no access log: who opened the page, and when, is nobody's business."""


class Server(ThreadingHTTPServer):
    def handle_error(self, request: object, client_address: tuple[str, int]) -> None:
        """Ignore visitors who close the tab mid-download; report anything else.

        The base class prints a traceback with the client's address for every request that
        fails, so each closed tab would leave an access-log line after all.
        """
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)  # type: ignore[arg-type]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8040)
    parser.add_argument("--dir", type=Path, default=ROOT / "build" / "web")
    args = parser.parse_args()
    if not (args.dir / "index.html").is_file():
        raise SystemExit(f"{args.dir} has no index.html: run scripts/build_web.py first")
    handler = functools.partial(Handler, directory=str(args.dir))
    with Server((args.host, args.port), handler) as server:
        print(f"Serving {args.dir} on http://{args.host}:{args.port}/ (Ctrl+C to stop)")
        server.serve_forever()


if __name__ == "__main__":
    main()
