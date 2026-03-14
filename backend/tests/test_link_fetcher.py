from email.message import Message
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def _load_link_fetcher_module():
    import importlib.util
    import sys

    module_name = "test_link_fetcher_runtime"
    module_path = BACKEND_APP / "infra" / "link_fetcher.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load link_fetcher module")

    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, *, status: int, headers: dict[str, str] | None = None, body: bytes = b"") -> None:
        message = Message()
        for key, value in (headers or {}).items():
            message[key] = value

        self.status = status
        self.headers = message
        self._body = body
        self.closed = False

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            amount = len(self._body)
        chunk = self._body[:amount]
        self._body = self._body[amount:]
        return chunk

    def close(self) -> None:
        self.closed = True


def test_link_fetcher_source_declares_ssrf_guards_and_no_redirect_opener() -> None:
    fetcher_source = (BACKEND_APP / "infra" / "link_fetcher.py").read_text(encoding="utf-8")

    assert "class SafeLinkFetcher:" in fetcher_source
    assert 'request.build_opener(NoRedirectHandler()).open' in fetcher_source
    assert 'if parsed_url.scheme not in _ALLOWED_SCHEMES:' in fetcher_source
    assert 'if port not in _ALLOWED_PORTS:' in fetcher_source
    assert 'socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)' in fetcher_source
    assert 'if redirect_count >= self._max_redirects:' in fetcher_source
    assert 'response.headers.get("Content-Length")' in fetcher_source
    assert 'if total_size > self._max_response_bytes:' in fetcher_source


def test_link_fetcher_rejects_invalid_scheme_and_port() -> None:
    link_fetcher = _load_link_fetcher_module()
    fetcher = link_fetcher.SafeLinkFetcher(
        timeout_sec=10,
        max_response_bytes=1024,
        max_redirects=2,
        resolver=lambda hostname, port: ["93.184.216.34"],
        open_url=lambda req, timeout: FakeResponse(status=200, body=b"ok"),
    )

    try:
        fetcher.fetch(url="ftp://example.com/file.txt")
    except link_fetcher.LinkFetchError as exc:
        assert "Unsupported link scheme" in str(exc)
    else:
        raise AssertionError("Expected invalid scheme to be rejected")

    try:
        fetcher.fetch(url="https://example.com:8443/file.txt")
    except link_fetcher.LinkFetchError as exc:
        assert "Unsupported link port" in str(exc)
    else:
        raise AssertionError("Expected invalid port to be rejected")


def test_link_fetcher_rejects_non_public_dns_results_before_request() -> None:
    link_fetcher = _load_link_fetcher_module()

    open_calls: list[tuple[str, int]] = []

    def fake_open(req, timeout):
        open_calls.append((req.full_url, timeout))
        return FakeResponse(status=200, body=b"ok")

    fetcher = link_fetcher.SafeLinkFetcher(
        timeout_sec=10,
        max_response_bytes=1024,
        max_redirects=2,
        resolver=lambda hostname, port: ["127.0.0.1"],
        open_url=fake_open,
    )

    try:
        fetcher.fetch(url="http://example.com/private")
    except link_fetcher.LinkFetchError as exc:
        assert "Blocked non-public link address" in str(exc)
    else:
        raise AssertionError("Expected private DNS resolution to be rejected")

    assert open_calls == []


def test_link_fetcher_revalidates_every_redirect_and_passes_timeout() -> None:
    link_fetcher = _load_link_fetcher_module()

    resolved_hosts: list[tuple[str, int]] = []
    opened_requests: list[tuple[str, int]] = []
    responses = {
        "http://example.com/start": FakeResponse(
            status=302,
            headers={"Location": "https://cdn.example.com/final"},
        ),
        "https://cdn.example.com/final": FakeResponse(
            status=200,
            headers={"Content-Type": "text/plain"},
            body=b"done",
        ),
    }

    def fake_resolver(hostname: str, port: int) -> list[str]:
        resolved_hosts.append((hostname, port))
        return ["93.184.216.34"]

    def fake_open(req, timeout):
        opened_requests.append((req.full_url, timeout))
        return responses[req.full_url]

    fetcher = link_fetcher.SafeLinkFetcher(
        timeout_sec=12,
        max_response_bytes=1024,
        max_redirects=2,
        resolver=fake_resolver,
        open_url=fake_open,
    )

    result = fetcher.fetch(url="http://example.com/start")

    assert resolved_hosts == [("example.com", 80), ("cdn.example.com", 443)]
    assert opened_requests == [
        ("http://example.com/start", 12),
        ("https://cdn.example.com/final", 12),
    ]
    assert result.final_url == "https://cdn.example.com/final"
    assert result.redirect_count == 1
    assert result.status_code == 200
    assert result.content_type == "text/plain"
    assert result.body == b"done"


def test_link_fetcher_aborts_when_declared_or_streamed_body_exceeds_limit() -> None:
    link_fetcher = _load_link_fetcher_module()

    fetcher = link_fetcher.SafeLinkFetcher(
        timeout_sec=10,
        max_response_bytes=4,
        max_redirects=1,
        resolver=lambda hostname, port: ["93.184.216.34"],
        open_url=lambda req, timeout: FakeResponse(
            status=200,
            headers={"Content-Length": "5"},
            body=b"hello",
        ),
    )

    try:
        fetcher.fetch(url="https://example.com/oversized")
    except link_fetcher.LinkFetchError as exc:
        assert "size limit" in str(exc)
    else:
        raise AssertionError("Expected oversized declared response to be rejected")

    stream_limited_fetcher = link_fetcher.SafeLinkFetcher(
        timeout_sec=10,
        max_response_bytes=4,
        max_redirects=1,
        resolver=lambda hostname, port: ["93.184.216.34"],
        open_url=lambda req, timeout: FakeResponse(status=200, body=b"hello"),
    )

    try:
        stream_limited_fetcher.fetch(url="https://example.com/streamed-oversized")
    except link_fetcher.LinkFetchError as exc:
        assert "size limit" in str(exc)
    else:
        raise AssertionError("Expected oversized streamed response to be rejected")
