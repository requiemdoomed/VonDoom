"""Run with python server.py, then open the printed loopback URL."""

import argparse
import hmac
import json
import mimetypes
import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from locksystem import DigitalLock

ROOT = Path(__file__).resolve().parent
PUBLIC = {"/assets/vondoom-emblem.svg": "assets/vondoom-emblem.svg", "/": "index.html", "/index.html": "index.html",
          "/assets/style.css": "assets/style.css", "/assets/app.js": "assets/app.js",
          "/assets/architecture.svg": "assets/architecture.svg",
          "/assets/gates.svg": "assets/gates.svg",
          "/assets/demo-locked.svg": "assets/demo-locked.svg",
          "/assets/demo-unlocked.svg": "assets/demo-unlocked.svg"}


class LocalServer(ThreadingHTTPServer):
    # A stalled client should not create an unlimited number of worker threads.
    daemon_threads = False

    def __init__(self, address, handler):
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON fields are not accepted.")
        result[key] = value
    return result


def make_server(port=8765, database=None):
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("Port must be an integer from 0 to 65535.")
    lock = DigitalLock(database or ROOT / "data" / "lock.sqlite3")
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        server_version = "VonDoom/2.1"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass  # Keep submitted credentials out of console logs.

        def handle(self):
            try:
                super().handle()
            except (ConnectionError, TimeoutError):
                pass
            except sqlite3.Error:
                with lock.mutex:
                    lock.open_until = 0
                try:
                    self.reply(503, {"error": "Storage is unavailable. The controller has locked."})
                except (ConnectionError, TimeoutError):
                    pass

        def reply(self, code, payload, content_type="application/json"):
            body = json.dumps(payload).encode() if content_type == "application/json" else payload
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def allowed_host(self):
            return (len(self.headers.get_all("Host", [])) == 1
                    and self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"})

        def do_GET(self):
            if not self.allowed_host():
                return self.reply(403, {"error": "Loopback host required."})
            path = urlsplit(self.path).path
            if path == "/api/session":
                return self.reply(200, {"token": token, **lock.status()})
            if path == "/api/status":
                return self.reply(200, lock.status())
            if path in PUBLIC:
                file = ROOT / PUBLIC[path]
                return self.reply(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            self.reply(404, {"error": "Not found."})

        def do_POST(self):
            for name in ("Origin", "X-Lock-Token", "Content-Length", "Content-Type"):
                if len(self.headers.get_all(name, [])) != 1:
                    return self.reply(400, {"error": "Required request headers must occur exactly once."})
            if self.headers.get("Transfer-Encoding"):
                return self.reply(400, {"error": "Transfer encoding is not supported."})
            origin = self.headers.get("Origin")
            if (not self.allowed_host() or origin != "http://" + self.headers.get("Host", "")
                    or not hmac.compare_digest(self.headers.get("X-Lock-Token", "").encode("utf-8"), token.encode("ascii"))):
                return self.reply(403, {"error": "Use this server's local web page."})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.reply(415, {"error": "JSON required."})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1024:
                    return self.reply(413, {"error": "Request size must be 1 to 1024 bytes."})
                body = self.rfile.read(size)
                if len(body) != size:
                    raise ValueError("Incomplete request body.")
                data = json.loads(body, object_pairs_hook=unique_fields)
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object.")
                path = urlsplit(self.path).path
                fields = {"/api/setup": {"pin"}, "/api/unlock": {"pin"},
                          "/api/lock": set(), "/api/change-pin": {"current", "new"},
                          "/api/protected": set()}
                if path not in fields:
                    return self.reply(404, {"error": "Not found."})
                if set(data) != fields[path]:
                    raise ValueError("The request has missing or unexpected fields.")
                if path == "/api/setup":
                    result = lock.setup(data.get("pin"))
                elif path == "/api/unlock":
                    result = lock.unlock(data.get("pin"))
                elif path == "/api/lock":
                    result = lock.lock()
                elif path == "/api/change-pin":
                    result = lock.change_pin(data.get("current"), data.get("new"))
                elif path == "/api/protected":
                    result = lock.protected_content()
                else:
                    return self.reply(404, {"error": "Not found."})
                self.reply(200, result)
            except (ValueError, UnicodeError) as exc:
                self.reply(400, {"error": str(exc)})
            except PermissionError as exc:
                self.reply(403, {"error": str(exc)})

    try:
        server = LocalServer(("127.0.0.1", port), Handler)
    except OSError:
        lock.close()
        raise
    server.lock = lock
    return server


def start_background(port=8765, database=None):
    server = make_server(port, database)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def stop_background(server):
    server.shutdown()
    server.server_close()
    server.lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VonDoom: Digital Lock System by Swayam Shakya")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        app = make_server(args.port)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Could not start: {exc}\nCheck the database, stop any other controller, or try a different --port.\n")
    print(f"VonDoom: Digital Lock System — http://127.0.0.1:{app.server_port} (Ctrl+C to stop)")
    try:
        app.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.server_close()
        app.lock.close()
