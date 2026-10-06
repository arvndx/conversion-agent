"""Fetch a page the way the existing website-analytics jobs do, but live and in-process.

Oxylabs is used as a proxy (the same four settings as the v2-gamification job:
OXYLAB_USER, OXYLAB_PASSWORD, OXYLAB_HOST, OXYLAB_PORT). The ladder:

1. A plain request with a rotating User-Agent. Sites that need JavaScript (maps, social, directories)
   skip straight to the browser.
2. If the site blocks us (403/429, or Cloudflare / "Robot Check" style text) or the request times out,
   render the page in headless Chromium **through the Oxylabs proxy**. Pages that are not blocked are
   rendered directly, as the job does.
3. If the browser returns nothing, retry a plain request **through the proxy with the
   `X-Oxylabs-Render: html` header**, which asks Oxylabs to render the page.

Differences from the jobs, on purpose: TLS verification stays on for direct requests (it is only
relaxed through the proxy, which re-signs certificates), every request has a timeout, and the browser
is always closed. Without proxy settings the proxy steps are skipped and the browser runs direct.
"""

import asyncio
import os
import random
import re
import time
from dataclasses import dataclass

from urllib.parse import quote

import httpx
from dotenv import load_dotenv

from app.scraping.safety import check_public_url

load_dotenv()  # so the OXYLAB_* settings in backend/.env reach the CLI as well as the server

# Same three desktop/mobile agents the job rotates through.
USER_AGENTS = [
    "Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.83 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",
]

# Text that means "this is a bot wall, not the page" (same list as the job).
BLOCK_WORDS = ("Cloudflare", "Robot Check", "Please Enable Cookies", "Your browser must allow cookies")

# JavaScript-heavy or login-gated sites: a plain GET returns an empty shell, so go straight to the browser.
BROWSER_FIRST = (
    "google.com/maps", "maps.app.goo", "g.page", "search.google.com", "business.google.com",
    "facebook.com", "linkedin.com", "instagram.com", "twitter.com", "x.com/",
    "yelp.com", "zillow.com", "realtor.com", "homes.com", "lendingtree.com",
)

TIMEOUT_SECONDS = float(os.environ.get("SCRAPE_TIMEOUT_SECONDS", "45"))
RENDER_HEADER = {"X-Oxylabs-Render": "html"}  # asks Oxylabs to render the page, as the job does
MIN_USEFUL_TEXT = 200  # a body shorter than this (after stripping tags) is treated as an empty JS shell


def _oxylab() -> tuple[str, str, str, str] | None:
    user, password = os.environ.get("OXYLAB_USER"), os.environ.get("OXYLAB_PASSWORD")
    host, port = os.environ.get("OXYLAB_HOST"), os.environ.get("OXYLAB_PORT")
    return (user, password, host, port) if all((user, password, host, port)) else None


def proxy_configured() -> bool:
    return _oxylab() is not None


def proxy_url() -> str | None:
    """`http://user:password@host:port`, for plain requests. None when Oxylabs is not configured."""
    settings = _oxylab()
    if settings is None:
        return None
    user, password, host, port = (quote(v, safe="") if i < 2 else v for i, v in enumerate(settings))
    return f"http://{user}:{password}@{host}:{port}"


def browser_proxy() -> dict | None:
    """The proxy in the shape Playwright wants (credentials separate from the server address)."""
    settings = _oxylab()
    if settings is None:
        return None
    user, password, host, port = settings
    return {"server": f"http://{host}:{port}", "username": user, "password": password}


@dataclass
class FetchResult:
    url: str
    html: str | None = None
    status: int | None = None
    via: str = "direct"  # direct | proxy | browser
    blocked: bool = False
    error: str | None = None
    elapsed_ms: int | None = None  # how long the request took (plain requests only; a browser render is not a fair timing)

    @property
    def ok(self) -> bool:
        return bool(self.html) and not self.blocked and not self.error


def normalize_url(url: str) -> str:
    url = url.strip()
    return url if re.match(r"^https?://", url, re.I) else f"https://{url}"


def needs_browser(url: str) -> bool:
    return any(host in url.lower() for host in BROWSER_FIRST)


def looks_blocked(status: int | None, body: str) -> bool:
    return status in (403, 429) or any(word in body for word in BLOCK_WORDS)


def _headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "http://google.com",
    }


def _text_length(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", html)).split())


async def _get(url: str, *, proxy: str | None, via: str, extra_headers: dict | None = None) -> FetchResult:
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            proxy=proxy,
            verify=proxy is None,  # the proxy re-signs TLS, so verification is off only through it
        ) as client:
            response = await client.get(url, headers={**_headers(), **(extra_headers or {})})
    except httpx.TimeoutException:
        return FetchResult(url, via=via, error="timeout", blocked=True)  # a timeout is retried through the proxy
    except httpx.HTTPError as exc:
        return FetchResult(url, via=via, error=f"{type(exc).__name__}: {exc}")

    body = response.text
    if response.status_code == 404:
        return FetchResult(url, status=404, via=via, error="not found")
    return FetchResult(url, html=body, status=response.status_code, via=via, blocked=looks_blocked(response.status_code, body),
                       elapsed_ms=round((time.monotonic() - started) * 1000))


async def _direct(url: str) -> FetchResult:
    return await _get(url, proxy=None, via="direct")


async def _proxied(url: str) -> FetchResult:
    return await _get(url, proxy=proxy_url(), via="proxy", extra_headers=RENDER_HEADER)


async def _browser(url: str, *, use_proxy: bool = False) -> FetchResult:
    """Render the page in headless Chromium, through the Oxylabs proxy when `use_proxy` is set."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return FetchResult(url, via="browser", error="playwright is not installed")

    context_args = {"ignore_https_errors": True, "user_agent": random.choice(USER_AGENTS[1:]), "locale": "en-US"}
    proxy = browser_proxy() if use_proxy else None
    if proxy:
        context_args["proxy"] = proxy

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(**context_args)
                page = await context.new_page()
                response = await page.goto(url, timeout=TIMEOUT_SECONDS * 1000, wait_until="domcontentloaded")
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:  # noqa: BLE001 — some pages never go idle; use what has rendered
                    pass
                html = await page.content()
                status = response.status if response else None
            finally:
                await browser.close()
    except Exception as exc:  # noqa: BLE001 — navigation errors, proxy failures, timeouts
        return FetchResult(url, via="browser", error=f"{type(exc).__name__}: {str(exc)[:200]}")

    return FetchResult(url, html=html, status=status, via="proxy-browser" if proxy else "browser", blocked=looks_blocked(status, html))


async def fetch_page(url: str) -> FetchResult:
    """Fetch `url` with the ladder described at the top. Returns the first usable result, or the last
    attempt (with `blocked` / `error` set) when none worked."""
    url = normalize_url(url)
    refusal = await asyncio.to_thread(check_public_url, url, resolve=True)
    if refusal:  # never fetch internal addresses, whoever supplied the URL
        return FetchResult(url, error=f"not fetched: {refusal}")
    last: FetchResult | None = None
    blocked = False

    if not needs_browser(url):
        last = await _direct(url)
        if last.ok and _text_length(last.html) >= MIN_USEFUL_TEXT:
            return last
        # Blocked or timed out: known to need the proxy. An empty shell that is not blocked just needs
        # JavaScript, which the browser provides.
        blocked = last.blocked or last.error == "timeout"

    # Browser render. Through the proxy straight away only when the site is known to block us.
    rendered = await _browser(url, use_proxy=blocked and proxy_configured())
    if rendered.ok and (_text_length(rendered.html) >= MIN_USEFUL_TEXT or not proxy_configured()):
        return rendered
    if proxy_configured() and rendered.via == "browser" and (rendered.blocked or rendered.error):
        # The direct browser was refused: try again through the proxy.
        rendered = await _browser(url, use_proxy=True)
        if rendered.ok and _text_length(rendered.html) >= MIN_USEFUL_TEXT:
            return rendered

    if proxy_configured():  # nothing usable from the browser: a plain request through the proxy, rendered by Oxylabs
        proxied = await _proxied(url)
        if proxied.ok and _text_length(proxied.html) >= MIN_USEFUL_TEXT:
            return proxied
        last = proxied

    return rendered if rendered.html or last is None else last
