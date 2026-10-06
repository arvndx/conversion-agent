import asyncio

import pytest
from sqlmodel import Session, select

from app.models import Profile, ProfileSource
from app.scraping import fetch, runner
from app.scraping.fetch import FetchResult, fetch_page, looks_blocked, needs_browser, normalize_url
from app.scraping.audit import website_audit
from app.scraping.parse import parse_html, platform_for_url
from app.scraping.validate import name_parts, validate_identity

PAGE = """<html lang="en"><head><title>Chuck Tegano, CMA | Loans</title>
<meta name="description" content="Chuck helps buyers and refinancers across New Jersey.">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
 {"@type":"Person","name":"Chuck Tegano"},
 {"@type":"LocalBusiness","name":"AnnieMac","openingHours":["Mo-Fr 09:00-17:00"]}]}</script>
<script type="application/ld+json">{ this is not json }</script></head>
<body><h1>Chuck Tegano</h1><p>NMLS # 209374. Call (732) 317-0735 or <a href="mailto:Chuck@Example.com">email me</a>.</p>
<a href="https://www.facebook.com/chuck">fb</a><a href="https://www.linkedin.com/in/chucktegano/">in</a>
<a href="https://www.zillow.com/lender-profile/chucktegano">z</a><a href="tel:7323170735">call</a>
<script>var tracker = 1;</script><style>.x{}</style></body></html>"""


# --- parsing ------------------------------------------------------------------------------------------


def test_parse_reads_text_meta_contacts_and_declared_data():
    page = parse_html(PAGE, "https://x.test")
    assert page.title == "Chuck Tegano, CMA | Loans" and page.language == "en"
    assert page.meta_description.startswith("Chuck helps")
    assert "tracker" not in page.text and "NMLS # 209374" in page.text
    assert page.phones == ["7323170735"] and page.emails == ["chuck@example.com"]
    assert page.json_ld_names == ["Chuck Tegano", "AnnieMac"]  # the malformed block is skipped, not fatal
    assert page.json_ld_hours == ["Mo-Fr 09:00-17:00"]
    assert page.markdown.startswith("# Chuck Tegano")


def test_text_of_neighbouring_elements_is_not_fused_together():
    page = parse_html("<html><body><p>310-345-1513</p><a>jane@site.com</a><span>jane</span><i>closed</i></body></html>", "https://site.test")
    assert page.emails == ["jane@site.com"] and page.phones == ["3103451513"]


def test_parse_finds_platform_links_and_ignores_tel_and_mailto():
    links = parse_html(PAGE).links
    assert links == {
        "facebook": "https://www.facebook.com/chuck",
        "linkedin": "https://www.linkedin.com/in/chucktegano/",
        "zillow": "https://www.zillow.com/lender-profile/chucktegano",
    }


@pytest.mark.parametrize("url,platform", [
    ("https://maps.app.goo.gl/abc", "google_business_profile"),
    ("https://g.page/some-biz", "google_business_profile"),
    ("https://twitter.com/x", "x"), ("https://x.com/x", "x"),
    ("https://www.yelp.com/biz/a-b", "yelp"), ("https://www.realtor.com/realestateagents/1", "realtor_com"),
    ("https://example.com/", None),
])
def test_platform_for_url(url, platform):
    assert platform_for_url(url) == platform


FACEBOOK_WALL = """<html><head><title>Facebook</title></head><body><div>Log in to Facebook</div>
<a href="https://www.facebook.com/login/device-based/regular/login/">Log in</a>
<a href="/r.php">Create new account</a></body></html>"""
LINKEDIN_WALL = "<html><body><h1>Agree &amp; Join LinkedIn</h1><p>By clicking Continue to join or sign in, you agree.</p><a href='/signup'>Join now</a></body></html>"


def test_login_wall_is_detected_but_a_real_page_is_not():
    assert parse_html(FACEBOOK_WALL).login_wall and parse_html(LINKEDIN_WALL).login_wall
    assert not parse_html(PAGE).login_wall
    long_page = "<html><body><a href='/login'>Login</a>" + "Mortgage advice for first time buyers. " * 120 + "</body></html>"
    assert not parse_html(long_page).login_wall  # a long page with a login link is a real page


def test_parse_detects_a_mobile_viewport():
    assert parse_html('<html><head><meta name="viewport" content="width=device-width"></head><body>x</body></html>').has_viewport
    assert not parse_html(PAGE).has_viewport


def test_website_audit_reads_the_five_checks_off_the_page():
    good = parse_html('<html><head><meta name="viewport" content="x"><meta name="description" content="Loans in NJ"></head>'
                      "<body>Open Monday - Friday 9 AM to 5 PM. Call (732) 317-0735.</body></html>")
    assert website_audit(good, load_time_ms=900) == {
        "has_meta_description": True, "mobile_friendly": True, "load_time_ms": 900, "has_contact_info": True, "has_business_hours_listed": True,
    }
    bare = parse_html("<html><body>Hello there</body></html>")
    assert website_audit(bare, load_time_ms=None) == {
        "has_meta_description": False, "mobile_friendly": False, "load_time_ms": None, "has_contact_info": False, "has_business_hours_listed": False,
    }
    assert website_audit(parse_html(PAGE), load_time_ms=None)["has_business_hours_listed"]  # JSON-LD hours count too


# --- identity validation ------------------------------------------------------------------------------


def test_name_parts_ignore_honorifics_credentials_and_team():
    assert name_parts("Dr. Chuck Tegano, CMA") == ("chuck", "tegano")
    assert name_parts("Jeff Tricoli Team") == ("jeff", "tricoli")
    assert name_parts("Jennifer Ballheimer") == ("jennifer", "ballheimer")


def test_full_name_is_required_not_just_one_name():
    only_first = validate_identity(profile_name="Chuck Tegano", page_text="Chuck is a nice name. Visit our team.")
    assert not only_first.validated
    only_last = validate_identity(profile_name="Chuck Tegano", page_text="The Tegano family farm.")
    assert not only_last.validated
    both = validate_identity(profile_name="Chuck Tegano", page_text="Contact Chuck Tegano today.")
    assert both.validated and both.evidence == ["name"] and both.confidence == 60


def test_name_order_middle_names_and_json_ld_count():
    assert validate_identity(profile_name="Chuck Tegano", page_text="Tegano, Chuck - loan officer").validated
    assert validate_identity(profile_name="Chuck Tegano", page_text="Chuck J. Tegano is here").validated
    assert validate_identity(profile_name="Chuck Tegano", page_text="", json_ld_names=["Chuck Tegano"]).validated


def test_phone_alone_does_not_validate_but_adds_confidence():
    no_name = validate_identity(profile_name="Chuck Tegano", page_text="Call (732) 317-0735", profile_phone="(732) 317-0735", page_phones=["7323170735"])
    assert not no_name.validated and no_name.phone_match and "phone or email matches" in no_name.reason
    with_name = validate_identity(profile_name="Chuck Tegano", page_text="Chuck Tegano", profile_phone="(732) 317-0735",
                                  page_phones=["7323170735"], profile_email="C@x.test", page_emails=["c@x.test"])
    assert with_name.validated and with_name.confidence == 100 and with_name.evidence == ["name", "phone", "email"]


# --- fetch ladder -------------------------------------------------------------------------------------

LONG = "<html><body>" + "word " * 300 + "</body></html>"


def test_url_helpers():
    assert normalize_url("example.com/a") == "https://example.com/a"
    assert normalize_url("http://example.com") == "http://example.com"
    assert looks_blocked(403, "") and looks_blocked(429, "") and looks_blocked(200, "Checking... Cloudflare")
    assert not looks_blocked(200, "hello")
    assert needs_browser("https://www.facebook.com/x") and needs_browser("https://maps.app.goo.gl/x")
    assert not needs_browser("https://antonioatoche.com")


@pytest.fixture()
def ladder(monkeypatch):
    """Replace the three fetchers with scripted results and record which ran (and how)."""
    calls = []

    def install(direct=None, proxied=None, browser=None, proxy_browser=None, proxy=False):
        async def _direct(url):
            calls.append("direct")
            return direct

        async def _proxied(url):
            calls.append("proxy-request")
            return proxied

        async def _browser(url, scrolls=0, use_proxy=False):
            calls.append("proxy-browser" if use_proxy else "browser")
            return proxy_browser if use_proxy else browser

        monkeypatch.setattr(fetch, "_direct", _direct)
        monkeypatch.setattr(fetch, "_proxied", _proxied)
        monkeypatch.setattr(fetch, "_browser", _browser)
        monkeypatch.setattr(fetch, "proxy_configured", lambda: proxy)
        monkeypatch.setattr(fetch, "check_public_url", lambda url, resolve=False: None)  # the fake domains don't resolve
        return calls

    return install


def result(**kw):
    return FetchResult("u", **kw)


BLOCKED = dict(html="Cloudflare", status=403, blocked=True)


def test_ladder_uses_a_plain_request_when_it_works(ladder):
    calls = ladder(direct=result(html=LONG, status=200))
    assert asyncio.run(fetch_page("https://site.test")).via == "direct" and calls == ["direct"]


def test_blocked_site_is_rendered_in_the_browser_through_the_proxy(ladder):
    calls = ladder(direct=result(**BLOCKED), proxy_browser=result(html=LONG, status=200, via="proxy-browser"), proxy=True)
    assert asyncio.run(fetch_page("https://site.test")).via == "proxy-browser" and calls == ["direct", "proxy-browser"]


def test_timeout_also_goes_through_the_proxy(ladder):
    calls = ladder(direct=result(error="timeout", blocked=True), proxy_browser=result(html=LONG, status=200, via="proxy-browser"), proxy=True)
    asyncio.run(fetch_page("https://site.test"))
    assert calls == ["direct", "proxy-browser"]


def test_empty_js_shell_is_rendered_directly_not_through_the_proxy(ladder):
    calls = ladder(direct=result(html="<html><body><div id=root></div></body></html>", status=200),
                   browser=result(html=LONG, status=200, via="browser"), proxy=True)
    assert asyncio.run(fetch_page("https://spa.test")).via == "browser" and calls == ["direct", "browser"]


def test_social_and_maps_go_straight_to_the_browser(ladder):
    calls = ladder(browser=result(html=LONG, status=200, via="browser"), proxy=True)
    asyncio.run(fetch_page("https://www.facebook.com/someone"))
    assert calls == ["browser"]


def test_a_refused_direct_browser_retries_through_the_proxy(ladder):
    calls = ladder(browser=result(**BLOCKED, via="browser"), proxy_browser=result(html=LONG, status=200, via="proxy-browser"), proxy=True)
    assert asyncio.run(fetch_page("https://www.linkedin.com/in/x")).via == "proxy-browser"
    assert calls == ["browser", "proxy-browser"]


BLANK = "<html><head></head><body></body></html>"


def test_a_blank_render_goes_on_to_the_proxied_render(ladder):
    # a bot check that renders as an empty page is not a result: the Oxylabs render is still to be tried
    calls = ladder(browser=result(html=BLANK, status=200, via="browser"), proxied=result(html=LONG, status=200, via="proxy"), proxy=True)
    assert asyncio.run(fetch_page("https://www.zillow.com/profile/someone")).via == "proxy"
    assert calls == ["browser", "proxy-request"]


def test_a_blank_render_without_proxy_settings_is_reported_as_it_is(ladder):
    calls = ladder(browser=result(html=BLANK, status=200, via="browser"), proxy=False)
    assert asyncio.run(fetch_page("https://www.zillow.com/profile/someone")).via == "browser" and calls == ["browser"]


def test_last_resort_is_a_proxied_request_with_the_render_header(ladder):
    calls = ladder(direct=result(**BLOCKED), proxy_browser=result(error="TimeoutError: navigation", via="proxy-browser"),
                   proxied=result(html=LONG, status=200, via="proxy"), proxy=True)
    assert asyncio.run(fetch_page("https://site.test")).via == "proxy"
    assert calls == ["direct", "proxy-browser", "proxy-request"]


def test_without_proxy_settings_the_proxy_steps_are_skipped(ladder):
    calls = ladder(direct=result(**BLOCKED), browser=result(html=LONG, status=200, via="browser"), proxy=False)
    assert asyncio.run(fetch_page("https://site.test")).via == "browser" and calls == ["direct", "browser"]


def test_everything_blocked_reports_the_failure(ladder):
    ladder(direct=result(**BLOCKED), browser=result(html="Just a moment... Cloudflare", status=403, via="browser", blocked=True), proxy=False)
    final = asyncio.run(fetch_page("https://walled.test"))
    assert final.blocked and not final.ok


# --- Oxylabs settings ---------------------------------------------------------------------------------


def test_oxylab_settings_build_the_proxy_urls(monkeypatch):
    for key, value in dict(OXYLAB_USER="cust@x:ame", OXYLAB_PASSWORD="p@ss/w", OXYLAB_HOST="pr.oxylabs.io", OXYLAB_PORT="7777").items():
        monkeypatch.setenv(key, value)
    assert fetch.proxy_configured()
    assert fetch.proxy_url() == "http://cust%40x%3Aame:p%40ss%2Fw@pr.oxylabs.io:7777"  # credentials are URL-escaped
    assert fetch.browser_proxy() == {"server": "http://pr.oxylabs.io:7777", "username": "cust@x:ame", "password": "p@ss/w"}


@pytest.mark.parametrize("missing", ["OXYLAB_USER", "OXYLAB_PASSWORD", "OXYLAB_HOST", "OXYLAB_PORT"])
def test_all_four_oxylab_settings_are_required(monkeypatch, missing):
    for key in ("OXYLAB_USER", "OXYLAB_PASSWORD", "OXYLAB_HOST", "OXYLAB_PORT"):
        monkeypatch.setenv(key, "x")
    monkeypatch.delenv(missing)
    assert not fetch.proxy_configured() and fetch.proxy_url() is None and fetch.browser_proxy() is None


def test_proxied_request_sends_the_render_header_and_skips_tls_verification(monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen["client"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, headers=None):
            seen["headers"] = headers
            return type("R", (), {"status_code": 200, "text": LONG})()

    monkeypatch.setattr(fetch.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(fetch, "proxy_url", lambda: "http://u:p@h:1")
    out = asyncio.run(fetch._proxied("https://x.test"))
    assert out.via == "proxy" and out.ok
    assert seen["headers"]["X-Oxylabs-Render"] == "html" and seen["client"]["proxy"] == "http://u:p@h:1"
    assert seen["client"]["verify"] is False  # through the proxy only

    asyncio.run(fetch._direct("https://x.test"))
    assert seen["client"]["verify"] is True and "X-Oxylabs-Render" not in seen["headers"]


# --- parallel runner (database) -----------------------------------------------------------------------


def _profile_and_sources(session, urls):
    profile = Profile(name="Chuck Tegano", category="Mortgage Loan Officer", location="Edison, NJ",
                      email="chuck@demo.test", phone_number="(732) 317-0735")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    sources = [ProfileSource(profile_id=profile.id, url=u, status="confirmed") for u in urls]
    session.add_all(sources)
    session.commit()
    for s in sources:
        session.refresh(s)
    return profile, [s.id for s in sources]


def test_runner_scrapes_in_parallel_and_withholds_unvalidated_pages(session, monkeypatch):
    pages = {
        "https://a.test": FetchResult("a", html=PAGE, status=200),                                         # about him
        "https://b.test": FetchResult("b", html="<html><body>" + "Somebody Else. " * 80 + "</body></html>", status=200),
        "https://c.test": FetchResult("c", html="Cloudflare", status=403, blocked=True, error=None),
    }

    in_flight, peak = [0], [0]

    async def slow_fetch(url, scrolls=0):
        in_flight[0] += 1
        peak[0] = max(peak[0], in_flight[0])
        await asyncio.sleep(0.2)  # long enough for the other fetches to start while this one is open
        in_flight[0] -= 1
        return pages[url]

    monkeypatch.setattr(runner, "fetch_page", slow_fetch)
    extracted_for = []

    def extractor(markdown, **kwargs):
        extracted_for.append(kwargs["url"])
        return {"name": "Chuck Tegano", "license": ["NMLS # 209374"]}

    profile, ids = _profile_and_sources(session, list(pages))
    out = runner.scrape_sources(profile.id, ids, person={"name": profile.name, "phone": profile.phone_number, "email": profile.email},
                                extractor=extractor)
    assert peak[0] == 3  # all three pages were being fetched at the same time, not one after another

    by_url = {s["url"]: s for s in out}
    assert by_url["https://a.test"]["status"] == "done" and "license" in by_url["https://a.test"]["fields_found"]
    assert by_url["https://b.test"]["status"] == "needs_identity" and by_url["https://b.test"]["fields_found"] == []
    assert by_url["https://c.test"]["status"] == "blocked"
    assert extracted_for == ["https://a.test"]  # nothing is extracted from a page that is not about him

    # the agent confirms page b really is theirs: extraction now runs on the stored text, no re-fetch
    session.expire_all()
    b = next(s for s in session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id)) if s.url == "https://b.test")
    runner.extract_confirmed(b.id, extractor=extractor)
    session.expire_all()
    b = session.get(ProfileSource, b.id)
    assert b.status == "done" and b.name_validated and b.extracted["_validation"]["confirmed_by_user"]


def test_sign_in_screen_is_blocked_not_put_to_the_user_as_an_identity_question(session, monkeypatch):
    pages = {
        "https://www.facebook.com/chuck": FetchResult("f", html=FACEBOOK_WALL, status=200),
        "https://www.linkedin.com/in/chuck": FetchResult("l", html=LINKEDIN_WALL, status=200),
        # a small ordinary website that merely lacks the name is still the user's call
        "https://small.test": FetchResult("s", html="<html><body><a href='/login'>Login</a>Welcome to our site</body></html>", status=200),
    }

    async def fake(url, scrolls=0):
        return pages[url]

    monkeypatch.setattr(runner, "fetch_page", fake)
    profile, ids = _profile_and_sources(session, list(pages))
    out = {s["url"]: s for s in runner.scrape_sources(profile.id, ids, person={"name": "Chuck Tegano"})}
    assert out["https://www.facebook.com/chuck"]["status"] == "blocked"
    assert out["https://www.linkedin.com/in/chuck"]["status"] == "blocked"
    assert out["https://small.test"]["status"] == "needs_identity"


def test_a_blank_page_is_blocked_not_put_to_the_user_as_an_identity_question(session, monkeypatch):
    async def fake(url, scrolls=0):
        return FetchResult("z", html="<html><head></head><body></body></html>", status=200, via="proxy-browser")

    monkeypatch.setattr(runner, "fetch_page", fake)
    profile, ids = _profile_and_sources(session, ["https://www.zillow.com/profile/antonio"])
    (out,) = runner.scrape_sources(profile.id, ids, person={"name": "Antonio Atoche"})
    assert out["status"] == "blocked" and "empty" in out["error"]


def test_never_read_platforms_are_not_fetched_even_if_asked(session, monkeypatch):
    called = []

    async def fake(url, scrolls=0):
        called.append(url)
        return FetchResult("l", html="<html><body>Chuck Tegano</body></html>", status=200)

    monkeypatch.setattr(runner, "fetch_page", fake)
    profile, ids = _profile_and_sources(session, ["https://www.linkedin.com/in/chuck", "https://instagram.com/chuck", "https://x.com/chuck", "https://www.youtube.com/@chuck"])
    out = runner.scrape_sources(profile.id, ids, person={"name": "Chuck Tegano"})
    assert called == [] and {o["status"] for o in out} == {"blocked"} and "not read" in out[0]["error"]


def test_a_website_page_records_an_audit_but_a_social_page_does_not(session, monkeypatch):
    pages = {
        "https://site.test": FetchResult("s", html=PAGE, status=200, via="direct", elapsed_ms=850),
        "https://slow.test": FetchResult("p", html=PAGE, status=200, via="proxy-browser"),  # a browser render: no honest timing
        "https://www.facebook.com/chuck": FetchResult("f", html=PAGE, status=200, via="browser"),
    }

    async def fake(url, scrolls=0):
        return pages[url]

    monkeypatch.setattr(runner, "fetch_page", fake)
    profile, ids = _profile_and_sources(session, list(pages))
    runner.scrape_sources(profile.id, ids, person={"name": "Chuck Tegano"})
    session.expire_all()
    extracted = {s.url: s.extracted for s in session.exec(select(ProfileSource).where(ProfileSource.profile_id == profile.id))}
    assert extracted["https://site.test"]["_audit"]["load_time_ms"] == 850
    assert extracted["https://slow.test"]["_audit"]["load_time_ms"] is None  # unknown, never counted as fast
    assert "_audit" not in extracted["https://www.facebook.com/chuck"]


def test_runner_scrapes_only_confirmed_sources_of_that_profile(session, monkeypatch):
    fetched = []

    async def fake(url, scrolls=0):
        fetched.append(url)
        return FetchResult(url, html=PAGE, status=200)

    monkeypatch.setattr(runner, "fetch_page", fake)
    profile, ids = _profile_and_sources(session, ["https://ok.test", "https://denied.test"])
    session.get(ProfileSource, ids[1]).status = "denied"
    proposed = ProfileSource(profile_id=profile.id, url="https://undecided.test", status="proposed")
    session.add(proposed)
    session.commit()
    session.refresh(proposed)
    runner.scrape_sources(profile.id, ids + [proposed.id, 10**9], person={"name": "Chuck Tegano"})
    assert fetched == ["https://ok.test"]  # not the denied one, not the undecided one, not a missing id


def test_internal_addresses_are_never_fetched(monkeypatch):
    called = []

    async def boom(*a, **k):
        called.append(1)

    monkeypatch.setattr(fetch, "_direct", boom)
    monkeypatch.setattr(fetch, "_browser", boom)
    for url in ["http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data", "http://10.0.0.7", "http://localhost:8000/api", "https://internal.local"]:
        out = asyncio.run(fetch_page(url))
        assert not out.ok and "not fetched" in out.error, url
    assert called == []
