"""
Codelysis Local REST API Server (Standard Library http.server).
Serves Graph-RAG Impact Analysis & Error Prediction over HTTP JSON API with CORS enabled.
"""
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys
import os

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from main import run_pipeline_data

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("server")

PORT = int(os.environ.get("PORT", 8000))


class CodelysisHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/health" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            resp = {"status": "ok", "service": "Codelysis Graph-RAG Engine", "version": "2.0"}
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/analyze":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)

            try:
                payload = json.loads(post_data.decode("utf-8")) if post_data else {}
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON payload: {e}"}).encode("utf-8"))
                return

            repo_path = payload.get("repo_path")
            github_slug = payload.get("github_url") or payload.get("github_slug")
            pr_number = payload.get("pr_number")
            commit_sha = payload.get("commit_sha")
            k = int(payload.get("k", 2))
            diff_text = payload.get("diff_text")
            model_name = payload.get("model_name", "gemini-2.5-flash")

            try:
                result = run_pipeline_data(
                    repo_path=repo_path,
                    github_slug=github_slug,
                    pr_number=pr_number,
                    commit_sha=commit_sha,
                    k=k,
                    diff_text=diff_text,
                    model_name=model_name
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                logger.error(f"Analysis failed: {e}", exc_info=True)
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run_server():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, CodelysisHandler)
    logger.info(f"Codelysis Graph-RAG Server listening on http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()

