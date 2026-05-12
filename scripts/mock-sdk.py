#!/usr/bin/env python3
"""Mock Replicated SDK server for testing custom metrics."""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler


class MockSDKHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[MOCK SDK] {self.client_address[0]} - {format % args}")

    def do_PATCH(self):
        if self.path == "/api/v1/app/custom-metrics":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                print(f"\n✅ Received metrics payload:\n{json.dumps(data, indent=2)}\n")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except json.JSONDecodeError as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Invalid JSON: {e}".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Mock Replicated SDK running")
        else:
            self.send_response(404)
            self.end_headers()


def main():
    port = 3000
    server = HTTPServer(("127.0.0.1", port), MockSDKHandler)
    print(f"Mock Replicated SDK listening on http://127.0.0.1:{port}")
    print("PATCH /api/v1/app/custom-metrics to test metrics")
    print("Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down mock server")
        sys.exit(0)


if __name__ == "__main__":
    main()
