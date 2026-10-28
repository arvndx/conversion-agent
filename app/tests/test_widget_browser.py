"""A browser test of the widget, with the installed Google Chrome, on the lender test page (booking on): a visitor clicks a quick
question, fills the request form, and the request is saved as a row of conv_handover. Nothing here calls a model: the click and the
form need none, and "hi" is a fixed reply.

It needs the lender page (8103) and the chat API (8000) to be running:
    uvicorn sites.business_pages:app --host :: --port 8103
    uvicorn api.chat_api:app --port 8000
Run from the app folder: uv run pytest tests/test_widget_browser.py
"""

import os
import uuid

import psycopg
import pytest

from pipeline.load_chat import DATABASE_URL, redis_client, session_key

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGE = "http://localhost:8103/"


def _servers_up() -> bool:
    import urllib.request

    for url in ("http://localhost:8000/health", PAGE):
        try:
            urllib.request.urlopen(url, timeout=2)
        except Exception:
            return False
    return True


pytestmark = pytest.mark.skipif(
    not (os.path.exists(CHROME) and _servers_up()),
    reason="needs Google Chrome, the lender test page (8103) and the chat API on 8000",
)


@pytest.fixture()
def widget():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        calls = []
        page.on("request", lambda r: calls.append((r.method, r.url.split("localhost:8000")[-1])) if "localhost:8000" in r.url else None)
        page.goto(PAGE)
        page.locator("button.launch").click()
        page.wait_for_selector(".panel.open")
        page.locator(".consent button.alt").click()   # decline page tracking: not part of these tests
        yield {"page": page, "errors": errors, "calls": calls}
        session = page.evaluate("() => Object.keys(localStorage).filter(k => k.startsWith('ca_session_')).map(k => localStorage[k])[0]")
        browser.close()
    if session:
        r = redis_client()
        with psycopg.connect(DATABASE_URL) as c:
            for table in ("conv_handover", "conv_session"):
                c.execute(f"delete from {table} where session_id = %s", (session,))
            c.execute("delete from conv_activity where activity_id = %s", (session,))
            c.commit()
        r.delete(session_key(session))
        r.srem("session_updates", session)
        r.srem("open_sessions", session)


def test_a_quick_question_opens_the_form_and_a_good_form_is_saved(widget):
    page, tag = widget["page"], "".join(c for c in uuid.uuid4().hex if c.isalpha())[:6].title()
    page.locator(".chip", has_text="Book Consultation").click()
    page.wait_for_selector(".fcard")
    assert page.locator(".fcard h4").inner_text() == "Schedule a Loan Consultation"
    assert "Step 1 of 2" in page.locator(".fstep").inner_text()
    assert page.locator(".ffield label").all_inner_texts() == ["Your name *", "Phone number", "Email"]   # who first
    assert [c[1] for c in widget["calls"] if c[0] == "POST"] == ["/chat/message"]
    box = page.locator(".fcard").bounding_box()
    panel = page.locator(".msgs").bounding_box()
    assert box["y"] >= panel["y"] - 1 and box["y"] + box["height"] <= panel["y"] + panel["height"] + 1   # the whole card is in view

    page.locator(".fgo").click()   # empty: the form says what is missing and goes no further
    assert [e for e in page.locator(".ferr").all_inner_texts() if e] and "Step 1 of 2" in page.locator(".fstep").inner_text()
    phone = page.locator("input[data-key=phone]")
    phone.press_sequentially("call 512-555-0199 now")   # letters cannot be typed into a phone number
    assert phone.input_value().replace(" ", "") == "512-555-0199"
    page.locator("input[data-key=name]").fill(f"Browser {tag}")
    page.locator("input[data-key=email]").fill("not-an-email")
    page.locator(".fgo").click()
    assert "valid email" in " ".join(page.locator(".ferr").all_inner_texts())
    page.locator("input[data-key=email]").fill("")
    page.locator(".fgo", has_text="Next").click()
    assert "Step 2 of 2" in page.locator(".fstep").inner_text()
    assert page.locator(".ffield label").all_inner_texts() == ["Your request *"]
    page.locator(".fback").click()   # back keeps what was typed
    assert page.locator("input[data-key=name]").input_value() == f"Browser {tag}"
    page.locator(".fgo", has_text="Next").click()
    page.locator(".fgo", has_text="Send").click()   # the request is empty
    assert "required" in " ".join(page.locator(".ferr").all_inner_texts())
    page.locator("textarea[data-key=question]").fill("A consultation next week")
    page.locator(".fgo", has_text="Send").click()
    page.wait_for_selector(".bubble.bot:has-text('conveyed')")
    assert "as soon as possible" in page.locator(".bubble.bot").last.inner_text()

    session = page.evaluate("() => Object.keys(localStorage).filter(k => k.startsWith('ca_session_')).map(k => localStorage[k])[0]")
    with psycopg.connect(DATABASE_URL) as c:
        row = c.execute("select name, phone, email, action_key, request_type from conv_handover where session_id = %s", (session,)).fetchall()
    assert row == [(f"Browser {tag}", "5125550199", None, "schedule_loan_consultation", "appointment booking")]
    assert widget["errors"] == []


@pytest.mark.parametrize("chip, on_page_two", [("Book Consultation", False), ("Book Consultation", True), ("Get My Rate", False)])
def test_cancel_is_on_every_page_and_nothing_is_sent(widget, chip, on_page_two):
    page = widget["page"]
    page.locator(".chip", has_text=chip).click()
    page.wait_for_selector(".fcard")
    if on_page_two:
        page.locator("input[data-key=name]").fill("Cancel Test")
        page.locator("input[data-key=email]").fill("c@x.com")
        page.locator(".fgo", has_text="Next").click()
    page.locator(".fcancel").click()
    page.wait_for_selector(".fdone:has-text('cancelled')")
    assert page.locator(".ffield").count() == 0 and "nothing was sent" in page.locator(".bubble.bot").last.inner_text()
    assert not any(c[1] == "/chat/form" for c in widget["calls"]) and widget["errors"] == []
    session = page.evaluate("() => Object.keys(localStorage).filter(k => k.startsWith('ca_session_')).map(k => localStorage[k])[0]")
    with psycopg.connect(DATABASE_URL) as c:
        assert c.execute("select count(*) from conv_handover where session_id = %s", (session,)).fetchone()[0] == 0


def test_a_greeting_gets_a_fixed_reply_and_a_link_question_gets_its_link(widget):
    page = widget["page"]
    page.locator("input").fill("hi")
    page.locator("button.send").click()
    page.wait_for_selector(".bubble.bot:has-text('Demo Loan Officer')")
    assert [c[1] for c in widget["calls"] if c[0] == "POST"] == ["/chat/message"] and widget["errors"] == []
    page.locator(".chip", has_text="Track My Loan").click()
    page.wait_for_selector(".bubble.bot:has-text('Here is the link')")
