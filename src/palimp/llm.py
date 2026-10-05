"""LLM backends for the optional prose writer (decision 0027).

The LLM writes, it never judges: it gets facts already established by the
deterministic code and returns text, which `palimp.prose` validates sentence
by sentence. Two backends:

- `OllamaBackend`: a local Ollama server over HTTP. Only loopback URLs are
  accepted (principle 1, zero network egress): the host must be `localhost`
  or a loopback address and must resolve to loopback addresses only.
  Proxies from the environment are ignored and redirects are refused, so a
  request can never leave the machine.
- `FakeBackend`: deterministic, for tests. By default it writes one sentence
  per evidence item from the item's own text; tests pass a function to
  return any text they want to check the validation against.
"""

import ipaddress
import json
import socket
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_TIMEOUT = 120.0


class Request(BaseModel):
    """What the writer asks: a system prompt, a user prompt and the facts behind them."""

    task: str  # "rule" or "summary"
    system: str
    prompt: str
    facts: dict[str, Any]


class Backend(Protocol):
    name: str

    def generate(self, request: Request) -> str: ...


class NonLocalURLError(ValueError):
    """The LLM URL does not point to this machine."""


def check_local_url(url: str) -> str:
    """Return the URL if it can only reach this machine, else raise NonLocalURLError."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise NonLocalURLError(f"{url}: only http or https to localhost is allowed")
    host = parts.hostname
    if not host:
        raise NonLocalURLError(f"{url}: no host")
    if parts.username or parts.password:
        raise NonLocalURLError(f"{url}: credentials in the URL are not allowed")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_loopback:
            raise NonLocalURLError(f"{url}: {host} is not a loopback address")
        return url
    if host.lower() != "localhost":
        raise NonLocalURLError(f"{url}: only localhost or a loopback address is allowed")
    # The hosts file decides what localhost means: every address must be loopback.
    try:
        infos = socket.getaddrinfo(host, parts.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        raise NonLocalURLError(f"{url}: localhost does not resolve") from error
    for info in infos:
        address = info[4][0].split("%", 1)[0]
        if not ipaddress.ip_address(address).is_loopback:
            raise NonLocalURLError(f"{url}: localhost resolves to {address}, not loopback")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise urllib.error.HTTPError(newurl, code, "redirect refused (local LLM only)", headers, fp)


def _opener() -> urllib.request.OpenerDirector:
    # An empty ProxyHandler ignores HTTP_PROXY and friends: no request through a proxy.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


class OllamaBackend:
    """A local Ollama server, `POST /api/generate`, temperature 0 and a fixed seed."""

    name = "ollama"

    def __init__(
        self, model: str, url: str = DEFAULT_OLLAMA_URL, timeout: float = DEFAULT_TIMEOUT
    ) -> None:
        self.url = check_local_url(url).rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, request: Request) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "system": request.system,
                "prompt": request.prompt,
                "stream": False,
                "options": {"temperature": 0, "seed": 0},
            }
        ).encode("utf-8")
        http = urllib.request.Request(
            f"{self.url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _opener().open(http, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload.get("response", ""))


def _default_fake(request: Request) -> str:
    """One sentence per evidence item, made of the item's own text, citing it."""
    if request.task == "summary":
        return " ".join(f"{f['text']} [{f['id']}]." for f in request.facts["facts"])
    sentences = []
    for item in request.facts["evidence"]:
        claim = item["claim"].rstrip(".")
        sentences.append(f"{item['locator']}: {claim} [{item['id']}].")
    return " ".join(sentences)


class FakeBackend:
    """Deterministic backend for tests: no model, no network."""

    name = "fake"

    def __init__(self, respond: Callable[[Request], str] | None = None) -> None:
        self.respond = respond or _default_fake
        self.requests: list[Request] = []

    def generate(self, request: Request) -> str:
        self.requests.append(request)
        return self.respond(request)
