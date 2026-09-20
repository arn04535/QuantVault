"""Local dashboard visualization layer over the Ledger core."""

from __future__ import annotations

import json
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from quantvault.ledger import Ledger
from quantvault.reports import (
    render_experiment_html,
    render_ledger_html,
    render_strategy_html,
)


def start_dashboard(
    ledger: Ledger,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
) -> HTTPServer:
    handler = partial(_DashboardHandler, ledger=ledger)
    server = HTTPServer((host, port), handler)
    return server


class _DashboardHandler(BaseHTTPRequestHandler):
    ledger: Ledger

    def __init__(self, *args: Any, ledger: Ledger, **kwargs: Any) -> None:
        self.ledger = ledger
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path in {"/", "/index.html"}:
                self._html(render_ledger_html(self.ledger))
                return
            if path.startswith("/experiment/"):
                exp_id = path.split("/experiment/", 1)[1].strip("/")
                self._html(render_experiment_html(self.ledger, exp_id))
                return
            if path.startswith("/strategy/"):
                strategy = path.split("/strategy/", 1)[1].strip("/")
                self._html(render_strategy_html(self.ledger, unquote(strategy)))
                return
            if path == "/api/experiments":
                self._json([e.to_dict() for e in self.ledger.list()])
                return
            if path.startswith("/api/experiments/"):
                exp_id = path.split("/api/experiments/", 1)[1].strip("/")
                exp = self.ledger.require(exp_id)
                self._json(exp.to_dict())
                return
            if path == "/api/compare":
                qs = parse_qs(parsed.query)
                left = (qs.get("left") or [None])[0]
                right = (qs.get("right") or [None])[0]
                if not left or not right:
                    self._error(400, "left and right query params required")
                    return
                self._json(self.ledger.compare(left, right))
                return
            self._error(404, "not found")
        except KeyError as exc:
            self._error(404, str(exc))
        except Exception as exc:  # noqa: BLE001
            self._error(500, f"{type(exc).__name__}: {exc}")

    def _html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: Any) -> None:
        data = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, code: int, message: str) -> None:
        data = message.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
