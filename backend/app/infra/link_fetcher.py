from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
import socket
from typing import Any, Callable
from urllib import error, parse, request


DEFAULT_FETCH_USER_AGENT = "SematrixLinkFetcher/1.0"
_ALLOWED_SCHEMES = frozenset({"http", "https"})
_ALLOWED_PORTS = frozenset({80, 443})
_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})


class LinkFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class LinkFetchResponse:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str | None
    body: bytes
    redirect_count: int


class NoRedirectHandler(request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):  # type: ignore[override]
        return fp

    def http_error_302(self, req, fp, code, msg, headers):  # type: ignore[override]
        return fp

    def http_error_303(self, req, fp, code, msg, headers):  # type: ignore[override]
        return fp

    def http_error_307(self, req, fp, code, msg, headers):  # type: ignore[override]
        return fp

    def http_error_308(self, req, fp, code, msg, headers):  # type: ignore[override]
        return fp


class SafeLinkFetcher:
    def __init__(
        self,
        *,
        timeout_sec: int,
        max_response_bytes: int,
        max_redirects: int,
        resolver: Callable[[str, int], list[str]] | None = None,
        open_url: Callable[..., Any] | None = None,
    ) -> None:
        self._timeout_sec = timeout_sec
        self._max_response_bytes = max_response_bytes
        self._max_redirects = max_redirects
        self._resolver = resolver or self._resolve_public_ip_addresses
        self._open_url = open_url or request.build_opener(NoRedirectHandler()).open

    def fetch(self, *, url: str) -> LinkFetchResponse:
        requested_url = url
        current_url = url
        redirect_count = 0

        while True:
            validated_url, hostname, port = self._validate_url(current_url)
            self._ensure_public_ip_addresses(self._resolver(hostname, port), hostname=hostname)

            http_request = request.Request(
                validated_url,
                headers={"User-Agent": DEFAULT_FETCH_USER_AGENT},
                method="GET",
            )

            try:
                response = self._open_url(http_request, timeout=self._timeout_sec)
            except error.HTTPError as exc:
                response = exc
            except error.URLError as exc:
                raise LinkFetchError(f"Link fetch failed for {validated_url}: {exc.reason}") from exc

            try:
                status_code = getattr(response, "status", None)
                if not isinstance(status_code, int):
                    raise LinkFetchError(f"Link fetch response missing HTTP status for {validated_url}")

                if status_code in _REDIRECT_STATUS_CODES:
                    location = response.headers.get("Location")
                    if not isinstance(location, str) or not location.strip():
                        raise LinkFetchError(f"Redirect response missing Location header for {validated_url}")
                    if redirect_count >= self._max_redirects:
                        raise LinkFetchError(f"Redirect limit exceeded for {requested_url}")

                    current_url = parse.urljoin(validated_url, location)
                    redirect_count += 1
                    continue

                body = self._read_limited_body(response=response, url=validated_url)
                return LinkFetchResponse(
                    requested_url=requested_url,
                    final_url=validated_url,
                    status_code=status_code,
                    content_type=response.headers.get("Content-Type"),
                    body=body,
                    redirect_count=redirect_count,
                )
            finally:
                response.close()

    def _validate_url(self, url: str) -> tuple[str, str, int]:
        parsed_url = parse.urlsplit(url)
        if parsed_url.scheme not in _ALLOWED_SCHEMES:
            raise LinkFetchError(f"Unsupported link scheme: {parsed_url.scheme or '(missing)'}")

        hostname = parsed_url.hostname
        if not isinstance(hostname, str) or not hostname:
            raise LinkFetchError(f"Link URL must include a hostname: {url}")

        normalized_hostname = hostname.rstrip(".").lower()
        if normalized_hostname == "localhost" or normalized_hostname.endswith(".localhost"):
            raise LinkFetchError(f"Blocked local hostname: {hostname}")

        port = parsed_url.port or (80 if parsed_url.scheme == "http" else 443)
        if port not in _ALLOWED_PORTS:
            raise LinkFetchError(f"Unsupported link port: {port}")

        sanitized_url = parse.urlunsplit(parsed_url._replace(fragment=""))
        return sanitized_url, normalized_hostname, port

    def _resolve_public_ip_addresses(self, hostname: str, port: int) -> list[str]:
        try:
            address_infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise LinkFetchError(f"DNS resolution failed for {hostname}: {exc}") from exc

        addresses: list[str] = []
        for _, _, _, _, sockaddr in address_infos:
            ip_value = str(sockaddr[0])
            if ip_value not in addresses:
                addresses.append(ip_value)

        return self._ensure_public_ip_addresses(addresses, hostname=hostname)

    def _ensure_public_ip_addresses(self, addresses: list[str], *, hostname: str) -> list[str]:
        if not addresses:
            raise LinkFetchError(f"DNS resolution returned no usable addresses for {hostname}")

        validated_addresses: list[str] = []
        for ip_value in addresses:
            parsed_ip = ip_address(ip_value)
            if self._is_blocked_ip(parsed_ip):
                raise LinkFetchError(f"Blocked non-public link address: {ip_value}")
            if ip_value not in validated_addresses:
                validated_addresses.append(ip_value)

        return validated_addresses

    def _is_blocked_ip(self, parsed_ip) -> bool:
        return (
            not parsed_ip.is_global
            or parsed_ip.is_loopback
            or parsed_ip.is_link_local
            or parsed_ip.is_multicast
            or parsed_ip.is_private
            or parsed_ip.is_reserved
            or parsed_ip.is_unspecified
        )

    def _read_limited_body(self, *, response: Any, url: str) -> bytes:
        content_length = response.headers.get("Content-Length")
        if isinstance(content_length, str):
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = None
            else:
                if declared_size > self._max_response_bytes:
                    raise LinkFetchError(f"Link response exceeded size limit for {url}")

        total_size = 0
        chunks: list[bytes] = []
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > self._max_response_bytes:
                raise LinkFetchError(f"Link response exceeded size limit for {url}")
            chunks.append(chunk)

        return b"".join(chunks)
