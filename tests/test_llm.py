"""LLM backends (decision 0027): Ollama on localhost only, deterministic fake.

No real model: a tiny HTTP server on 127.0.0.1 stands in for Ollama.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from palimp.llm import FakeBackend, NonLocalURLError, OllamaBackend, Request, check_local_url


def test_fake_backend_is_deterministic() -> None:
    facts = {"evidence": [{"id": "E1", "locator": "policy x description", "claim": "for crm"}]}
    request = Request(task="rule", system="s", prompt="p", facts=facts)
    backend = FakeBackend()
    assert backend.generate(request) == backend.generate(request)
    assert backend.generate(request) == "policy x description: for crm [E1]."
    assert len(backend.requests) == 3


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.5:11434",
        "http://192.168.1.10:11434",
        "http://example.com:11434",
        "http://localhost.example.com:11434",
        "http://127.0.0.1.nip.io:11434",
        "ftp://localhost:11434",
        "http://user:secret@localhost:11434",
        "localhost:11434",
    ],
)
def test_non_local_url_is_refused(url: str) -> None:
    with pytest.raises(NonLocalURLError):
        OllamaBackend("any-model", url)


@pytest.mark.parametrize(
    "url", ["http://localhost:11434", "http://127.0.0.1:11434", "http://[::1]:11434"]
)
def test_local_url_is_accepted(url: str) -> None:
    assert check_local_url(url) == url


class FakeOllama(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server naming
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append(body)  # type: ignore[attr-defined]
        if type(self).redirect:  # type: ignore[attr-defined]
            self.send_response(307)
            self.send_header("Location", "http://example.com/api/generate")
            self.end_headers()
            return
        payload = json.dumps({"response": "Hello [E1]."}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object) -> None:
        pass


@pytest.mark.parametrize("redirect", [False, True])
def test_ollama_backend_talks_to_localhost_only(redirect: bool) -> None:
    handler = type("Handler", (FakeOllama,), {"seen": [], "redirect": redirect})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        backend = OllamaBackend("tiny", f"http://127.0.0.1:{server.server_port}", timeout=5)
        request = Request(task="rule", system="s", prompt="p", facts={})
        if redirect:
            with pytest.raises(Exception, match="redirect refused"):
                backend.generate(request)
        else:
            assert backend.generate(request) == "Hello [E1]."
        assert handler.seen[0]["model"] == "tiny"
        assert handler.seen[0]["stream"] is False
        assert handler.seen[0]["options"]["temperature"] == 0
        assert handler.seen[0]["think"] is False
    finally:
        server.shutdown()
