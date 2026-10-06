"""Which URLs we are willing to fetch.

URLs come from users, from the model (search results) and from scraped pages, so none of them is
trusted. Only public http(s) addresses are fetched: no localhost, private ranges, link-local or cloud
metadata addresses. The host is resolved and every address it maps to must be public, which also stops
a public name that points at an internal address. Set SCRAPE_ALLOW_PRIVATE=true to lift this for local
testing (the CLI against a local page, for example).
"""

import ipaddress
import os
import re
import socket
from urllib.parse import urlparse

MAX_URL_LENGTH = 2000
_BLOCKED_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".corp")


def _allow_private() -> bool:
    return os.environ.get("SCRAPE_ALLOW_PRIVATE", "").lower() in ("1", "true", "yes")


def normalize(url: str) -> str:
    url = (url or "").strip()
    return url if re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I) else f"https://{url}"


def _is_public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return ip.is_global  # excludes private, loopback, link-local, multicast, reserved and unspecified


def check_public_url(url: str, *, resolve: bool = False) -> str | None:
    """None if `url` may be fetched, otherwise a short reason. With `resolve`, also look the host up."""
    if not url or len(url) > MAX_URL_LENGTH:
        return "that is not a usable web address"
    parsed = urlparse(normalize(url))
    if parsed.scheme not in ("http", "https"):
        return "only http and https addresses are allowed"
    host = (parsed.hostname or "").lower()
    if parsed.username or parsed.password:
        return "addresses with embedded credentials are not allowed"
    if _allow_private():
        return None if host else "that is not a usable web address"
    if host == "localhost" or host.endswith(_BLOCKED_SUFFIXES):
        return "internal addresses are not allowed"
    if not host or "." not in host and ":" not in host:
        return "that is not a usable web address"
    try:
        ipaddress.ip_address(host)
        return None if _is_public_ip(host) else "internal addresses are not allowed"
    except ValueError:
        pass  # a name, not an IP literal
    if resolve:
        try:
            addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
        except socket.gaierror:
            return "that address does not resolve"
        if not addresses or not all(_is_public_ip(a) for a in addresses):
            return "internal addresses are not allowed"
    return None
