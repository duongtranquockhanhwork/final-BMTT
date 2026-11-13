"""
app.py - HTTP routing for the classroom digital-signature demo.

Pure Python standard library (http.server). Static pages are served from web/,
and a small JSON API drives the student chat and the teacher dashboard.
"""

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .state import STORE
from .qr import qr_svg

WEB = Path(__file__).resolve().parent.parent / "web"

PAGES = {"/": "join.html", "/join": "join.html", "/chat": "chat.html", "/admin": "admin.html"}
CTYPE = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml"}


def require_admin(req):
    tok = req.get("token")
    return bool(tok) and tok in STORE.admin_tokens


class Handler(BaseHTTPRequestHandler):
    # -------------------------------------------------------------- helpers
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, code, obj):
        self._send(code, json.dumps(obj), "application/json; charset=utf-8")

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    # -------------------------------------------------------------- GET
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in PAGES:
            return self._send(200, (WEB / PAGES[path]).read_bytes(), CTYPE[".html"])
        if path.startswith("/assets/"):
            f = (WEB / "assets" / Path(path).name)
            if f.is_file() and f.resolve().parent == (WEB / "assets").resolve():
                return self._send(200, f.read_bytes(), CTYPE.get(f.suffix, "text/plain"))
            return self._send(404, b"not found", "text/plain")
        if path == "/qr":
            svg = qr_svg(STORE.base_url)
            if svg is None:
                return self._send(404, b"segno not installed", "text/plain")
            return self._send(200, svg, CTYPE[".svg"])
        if path == "/api/info":
            return self._json(200, {"base_url": STORE.base_url, "has_qr": qr_svg(STORE.base_url) is not None})
        return self._send(404, b"not found", "text/plain")

    # -------------------------------------------------------------- POST
    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            req = self._body()
        except Exception:
            return self._json(400, {"error": "bad request"})
        try:
            return self._route(path, req)
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:  # never crash the server on a bad action
            return self._json(500, {"error": str(e)})

    def _route(self, path, req):
        # ---- student ----
        if path == "/api/join":
            u = STORE.add_user(req.get("name"), req.get("device_id"))
            return self._json(200, {"token": u["token"], "uid": u["uid"], "name": u["name"], "color": u["color"]})
        if path == "/api/state":
            snap = STORE.student_snapshot(req.get("token"))
            return self._json(200, snap) if snap else self._json(401, {"error": "session expired"})
        if path == "/api/send":
            STORE.send(req.get("token"), req.get("to"), req.get("text"))
            return self._json(200, {"ok": True})

        # ---- admin ----
        if path == "/api/admin/login":
            if str(req.get("passcode")) == STORE.admin_passcode:
                token = secrets.token_hex(12)
                STORE.admin_tokens.add(token)       # add, never replace existing sessions
                return self._json(200, {"token": token})
            return self._json(401, {"error": "wrong passcode"})
        if path.startswith("/api/admin/"):
            if not require_admin(req):
                return self._json(401, {"error": "admin only"})
            if path == "/api/admin/state":
                return self._json(200, STORE.admin_snapshot())
            if path == "/api/admin/hold":
                STORE.set_hold(req.get("on"))
                return self._json(200, {"ok": True, "hold_mode": STORE.hold_mode})
            if path == "/api/admin/attack":
                m = STORE.attack(req.get("message_id"), req.get("new_text"), req.get("mode"))
                return self._json(200, {"ok": True, "message_id": m["id"], "valid": m["valid"]})
            if path == "/api/admin/reset":
                STORE.reset()
                return self._json(200, {"ok": True})
        return self._json(404, {"error": "not found"})

    def log_message(self, *a):
        pass  # keep the console clean for the live demo


def serve(host, port, base_url):
    STORE.base_url = base_url
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd
