"""The Python side of the static in-browser build (ADR 007).

The page runs this module inside Pyodide, in a Web Worker. The worker writes the files the
student picks into Pyodide's in-memory file system, calls one function here with their
paths, and gets back JSON. Nothing here touches the network or imports the CLI (Typer is
not installed in the browser).
"""

from descargo.web.api import (
    access_request,
    audit,
    choices,
    discard,
    inspect,
    pdf,
    workdir,
)

__all__ = ["access_request", "audit", "choices", "discard", "inspect", "pdf", "workdir"]
