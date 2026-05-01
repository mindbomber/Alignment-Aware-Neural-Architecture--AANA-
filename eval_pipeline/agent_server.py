"""No-dependency local HTTP bridge for AANA agent checks."""

import argparse
import json
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval_pipeline import agent_api


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def json_bytes(payload):
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def route_request(method, target, body=b"", gallery_path=agent_api.DEFAULT_GALLERY):
    parsed = urlparse(target)
    query = parse_qs(parsed.query)

    if method == "GET" and parsed.path == "/health":
        return 200, {
            "status": "ok",
            "service": "aana-agent-bridge",
            "agent_check_version": agent_api.AGENT_EVENT_VERSION,
        }

    if method == "GET" and parsed.path == "/policy-presets":
        return 200, {"policy_presets": agent_api.list_policy_presets()}

    if method == "POST" and parsed.path == "/agent-check":
        try:
            event = json.loads(body.decode("utf-8") if body else "{}")
            if not isinstance(event, dict):
                raise ValueError("Request body must be a JSON object.")
            adapter_id = query.get("adapter_id", [None])[0]
            return 200, agent_api.check_event(event, gallery_path=gallery_path, adapter_id=adapter_id)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            return 400, {"error": str(exc)}

    return 404, {
        "error": "Unknown route.",
        "routes": ["GET /health", "GET /policy-presets", "POST /agent-check"],
    }


class AanaAgentHandler(BaseHTTPRequestHandler):
    gallery_path = agent_api.DEFAULT_GALLERY

    def do_GET(self):
        self.respond(*route_request("GET", self.path, gallery_path=self.gallery_path))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length)
        self.respond(*route_request("POST", self.path, body=body, gallery_path=self.gallery_path))

    def log_message(self, format, *args):
        sys.stderr.write("aana_server: " + format % args + "\n")

    def respond(self, status, payload):
        data = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_handler(gallery_path):
    class ConfiguredAanaAgentHandler(AanaAgentHandler):
        pass

    ConfiguredAanaAgentHandler.gallery_path = gallery_path
    return ConfiguredAanaAgentHandler


def run_server(host=DEFAULT_HOST, port=DEFAULT_PORT, gallery_path=agent_api.DEFAULT_GALLERY):
    server = ThreadingHTTPServer((host, port), make_handler(gallery_path))
    print(f"AANA agent bridge listening on http://{host}:{port}")
    print("Routes: GET /health, GET /policy-presets, POST /agent-check")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AANA agent bridge.")
    finally:
        server.server_close()


def build_parser():
    parser = argparse.ArgumentParser(description="Run the local AANA agent HTTP bridge.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind.")
    parser.add_argument("--gallery", default=str(agent_api.DEFAULT_GALLERY), help="Adapter gallery JSON path.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    run_server(args.host, args.port, args.gallery)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
