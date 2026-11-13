from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread

import pytest


@pytest.fixture
def model_server():
    @contextmanager
    def serve(respond):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                status, payload = respond(body)
                self.send_response(status); self.end_headers()
                self.wfile.write(payload if isinstance(payload, bytes) else json.dumps(payload).encode())
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}', requests
        finally:
            server.shutdown(); thread.join(timeout=5); server.server_close()
    return serve
