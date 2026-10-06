import re
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import auth
from app.db import engine
from app.main import app
from app.models import AuthSession, Category, CategoryService, Claim, MockEmail, OtpCode, Profile


@pytest.fixture()
def client(seeded_db, mutates_db):
    with TestClient(app) as c:
        yield c


def taxonomy(client):
    return client.get("/api/taxonomy").json()["verticals"]


def pick(client, category_name, n=2):
    for v in taxonomy(client):
        for c in v["categories"]:
            if c["name"] == category_name:
                return v["key"], c["id"], [s["key"] for s in c["services"]][:n]
    raise AssertionError(category_name)


def code_from_mailbox(client, email):
    mails = client.get("/api/mailbox", params={"email": email}).json()
    body = client.get(f"/api/mailbox/{mails[0]['id']}", params={"email": email}).json()["body_html"]
    return re.search(r"letter-spacing:6px;'>(\d{6})<", body).group(1)


def demo_profile(name="Chuck Tegano"):
    """A demo professional, found by the stable synthetic email (the name can change when claimed)."""
    email = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-") + "@demo.clearrank.test"
    with Session(engine) as s:
        p = s.exec(select(Profile).where(Profile.email == email)).one()
        s.expunge(p)
        return p


def card(client, profile, **over):
    vertical, category_id, services = pick(client, profile.category)
    body = {"profile_id": profile.id, "name": profile.name, "email": profile.email, "phone_number": profile.phone_number,
            "vertical": vertical, "category_id": category_id, "services": services}
    body.update(over)
    return body


# --- taxonomy -----------------------------------------------------------------------------------------


def test_taxonomy_cascades_vertical_to_category_to_services(client):
    verticals = {v["name"]: v for v in taxonomy(client)}
    assert {c["name"] for c in verticals["Mortgage"]["categories"]} == {"Mortgage Loan Officer", "Mortgage Lender"}
    insurance = verticals["Insurance"]["categories"][0]
    assert insurance["name"] == "Insurance Agent" and len(insurance["services"]) == 6


def test_category_rules_endpoint_returns_the_score_split(client):
    _, category_id, _ = pick(client, "Insurance Agent")
    rules = client.get(f"/api/taxonomy/categories/{category_id}").json()
    assert (rules["common_max"], rules["pro_max"]) == (600, 850)
    assert rules["rules"]["claim"]["edit_one_of"] == ["phone_number", "email"]
    assert [s["key"] for s in rules["sections"]][-1] == "web_analytics"


# --- option 1: claim from a search result -------------------------------------------------------------


def test_claim_only_takes_effect_after_the_otp(client):
    chuck = demo_profile()
    started = client.post("/api/claims/start", json=card(client, chuck, name="Charles Tegano"))
    assert started.status_code == 200 and started.json()["mailbox_url"] == f"/mailbox/{chuck.email}"
    with Session(engine) as s:  # nothing changed yet
        stored = s.get(Profile, chuck.id)
        assert stored.name == "Chuck Tegano" and stored.lifecycle_state == "unclaimed"

    code = code_from_mailbox(client, chuck.email)
    verified = client.post("/api/claims/verify", json={"claim_id": started.json()["claim_id"], "code": code})
    assert verified.status_code == 200 and verified.json()["next"] == f"/onboarding/{chuck.id}"
    assert auth.SESSION_COOKIE in verified.cookies
    assert client.get("/api/auth/me").json()["onboarding_completed"] is False  # just claimed: onboarding comes next

    with Session(engine) as s:
        claimed = s.get(Profile, chuck.id)
        assert claimed.name == "Charles Tegano" and claimed.lifecycle_state == "claimed" and claimed.claimed_at
        assert claimed.services and claimed.vertical == "Mortgage"
        assert claimed.search_rank_score >= 0
        claim = s.exec(select(Claim).where(Claim.id == started.json()["claim_id"])).one()
        assert claim.status == "verified" and claim.profile_id == chuck.id


def test_cannot_edit_both_phone_and_email(client):
    antonio = demo_profile("Antonio Atoche")
    both = client.post("/api/claims/start", json=card(client, antonio, email="new@example.test", phone_number="(555) 000-1234"))
    assert both.status_code == 400 and "not both" in both.json()["detail"]
    only_phone = client.post("/api/claims/start", json=card(client, antonio, phone_number="(555) 000-1234"))
    assert only_phone.status_code == 200
    only_email = client.post("/api/claims/start", json=card(client, antonio, email="antonio.new@example.test"))
    assert only_email.status_code == 200
    # the code for an edited email goes to the edited address's own mailbox
    assert client.get("/api/mailbox", params={"email": "antonio.new@example.test"}).json()


def test_mandatory_values_and_cascade_are_enforced(client):
    ryan = demo_profile("Ryan Davis")
    for override, fragment in [
        ({"name": ""}, "Full name"), ({"email": "nope"}, "valid email"), ({"phone_number": "123"}, "phone"),
        ({"services": []}, "service"), ({"vertical": "real_estate"}, "does not belong"),
        ({"services": ["fha_home_loan"]}, "does not belong"), ({"category_id": None}, "category"),
    ]:
        r = client.post("/api/claims/start", json=card(client, ryan, **override))
        assert r.status_code == 400 and fragment.lower() in r.json()["detail"].lower(), override


def test_wrong_codes_are_counted_and_lock_out(client):
    david = demo_profile("David Worley")
    claim_id = client.post("/api/claims/start", json=card(client, david)).json()["claim_id"]
    for left in (4, 3, 2, 1, 0):
        r = client.post("/api/claims/verify", json={"claim_id": claim_id, "code": "000000"})
        assert r.status_code == 400 and f"{left} attempt" in r.json()["detail"]
    locked = client.post("/api/claims/verify", json={"claim_id": claim_id, "code": code_from_mailbox(client, david.email)})
    assert locked.status_code == 429


def test_expired_code_is_rejected(client):
    jennifer = demo_profile("Jennifer Ballheimer")
    claim_id = client.post("/api/claims/start", json=card(client, jennifer)).json()["claim_id"]
    code = code_from_mailbox(client, jennifer.email)
    with Session(engine) as s:
        otp = s.exec(select(OtpCode).where(OtpCode.claim_id == claim_id)).one()
        otp.expires_at = datetime.utcnow() - timedelta(minutes=1)
        s.add(otp)
        s.commit()
    r = client.post("/api/claims/verify", json={"claim_id": claim_id, "code": code})
    assert r.status_code == 400 and "expired" in r.json()["detail"]


def test_code_is_single_use_and_stored_hashed(client):
    melissa = demo_profile("Melissa Tippey")
    claim_id = client.post("/api/claims/start", json=card(client, melissa)).json()["claim_id"]
    code = code_from_mailbox(client, melissa.email)
    with Session(engine) as s:
        assert code not in s.exec(select(OtpCode).where(OtpCode.claim_id == claim_id)).one().code_hash
    assert client.post("/api/claims/verify", json={"claim_id": claim_id, "code": code}).status_code == 200
    again = client.post("/api/claims/verify", json={"claim_id": claim_id, "code": code})
    assert again.status_code == 404  # the claim is no longer pending


def test_claimed_profile_cannot_be_claimed_again(client):
    chuck = demo_profile()  # claimed in the first test of this module
    r = client.post("/api/claims/start", json=card(client, chuck))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_claimed"


# --- option 2: a profile that is not in the database ---------------------------------------------------


def test_new_profile_is_created_only_on_verify_and_duplicates_are_refused(client):
    vertical, category_id, services = pick(client, "Real Estate Agent")
    body = {"name": "Nina Newagent", "email": "nina@example.test", "phone_number": "(555) 010-2030",
            "vertical": vertical, "category_id": category_id, "services": services}
    started = client.post("/api/claims/start", json=body)
    assert started.status_code == 200 and started.json()["method"] == "new_profile"
    with Session(engine) as s:
        assert s.exec(select(Profile).where(Profile.email == "nina@example.test")).first() is None

    verified = client.post("/api/claims/verify", json={"claim_id": started.json()["claim_id"], "code": code_from_mailbox(client, "nina@example.test")})
    assert verified.status_code == 200
    with Session(engine) as s:
        nina = s.get(Profile, verified.json()["profile_id"])
        assert nina.lifecycle_state == "claimed" and nina.category == "Real Estate Agent" and nina.services == services

    dup = client.post("/api/claims/start", json=body)
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "already_claimed"
    existing = client.post("/api/claims/start", json={**body, "email": demo_profile("Jeff Tricoli Team").email})
    assert existing.status_code == 409 and existing.json()["detail"]["code"] == "profile_exists"


# --- sign in, sessions and access --------------------------------------------------------------------


def test_login_with_email_otp_then_me_and_logout(client):
    email = "nina@example.test"
    assert client.get("/api/auth/me").json() == {"authenticated": False}
    assert client.post("/api/auth/otp/request", json={"email": email}).json()["sent"]
    bad = client.post("/api/auth/otp/verify", json={"email": email, "code": "111111"})
    assert bad.status_code == 400
    ok = client.post("/api/auth/otp/verify", json={"email": email, "code": code_from_mailbox(client, email)})
    assert ok.status_code == 200
    me = client.get("/api/auth/me").json()
    assert me["authenticated"] and me["email"] == email and me["category"] == "Real Estate Agent"
    assert me["onboarding_completed"] is False and ok.json()["onboarding_completed"] is False  # claimed a moment ago: onboarding is next
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json() == {"authenticated": False}


def test_a_seeded_account_signs_in_as_already_onboarded(client):
    with Session(engine) as s:
        seeded = s.exec(select(Profile).where(Profile.lifecycle_state == "pro")).first()
    signed_in = client.post("/api/auth/demo-login", json={"profile_id": seeded.id}).json()
    assert signed_in["onboarding_completed"] is True and client.get("/api/auth/me").json()["onboarding_completed"] is True


def test_login_request_does_not_reveal_whether_an_account_exists(client):
    unknown = client.post("/api/auth/otp/request", json={"email": "nobody@example.test"})
    known = client.post("/api/auth/otp/request", json={"email": "nina@example.test"})
    assert unknown.status_code == known.status_code == 200 and unknown.json().keys() == known.json().keys()
    assert client.get("/api/mailbox", params={"email": "nobody@example.test"}).json() == []


def test_owner_routes_need_a_session_for_that_profile(client):
    with Session(engine) as s:
        claimed = s.exec(select(Profile).where(Profile.lifecycle_state == "claimed", Profile.email.like("%@example.test"))).first()
        other = s.exec(select(Profile).where(Profile.lifecycle_state == "claimed", Profile.id != claimed.id)).first()
        pid, oid = claimed.id, other.id
    routes = [f"/api/dashboard/{pid}", f"/api/profiles/{pid}/manage", f"/api/profiles/{pid}/pricing", f"/api/agent/conversations/{pid}"]
    for url in routes:
        assert client.get(url).status_code == 401, url
    assert client.get(f"/api/profiles/{pid}").status_code == 200  # the public page stays public

    assert client.post("/api/auth/demo-login", json={"profile_id": pid}).status_code == 200
    for url in routes:
        assert client.get(url).status_code == 200, url
    assert client.get(f"/api/dashboard/{oid}").status_code == 403  # signed in, but as someone else


def test_unclaimed_profiles_stay_public(client):
    with Session(engine) as s:
        unclaimed = s.exec(select(Profile).where(Profile.lifecycle_state == "unclaimed")).first().id
    assert client.get(f"/api/agent/conversations/{unclaimed}").status_code == 200


def test_sessions_expire_and_are_stored_hashed(client):
    client.post("/api/auth/demo-login", json={"profile_id": demo_profile("Chuck Tegano").id})
    token = client.cookies.get(auth.SESSION_COOKIE)
    with Session(engine) as s:
        rows = s.exec(select(AuthSession)).all()
        assert token not in [r.token_hash for r in rows]
        for r in rows:
            r.expires_at = datetime.utcnow() - timedelta(seconds=1)
            s.add(r)
        s.commit()
    assert client.get("/api/auth/me").json() == {"authenticated": False}


def test_mailbox_pages_are_per_person(client):
    chuck = demo_profile("Chuck Tegano")
    mine = client.get("/api/mailbox", params={"email": chuck.email}).json()
    assert mine and all(m["to_email"] == chuck.email for m in mine)  # his claim code is in his mailbox
    other = demo_profile("Jonathan Sweat")
    theirs = client.get("/api/mailbox", params={"email": other.email}).json()
    assert all(m["to_email"] == other.email for m in theirs)
    # one person's email is not readable through another person's mailbox
    assert client.get(f"/api/mailbox/{mine[0]['id']}", params={"email": other.email}).status_code == 404
    assert client.get(f"/api/mailbox/{mine[0]['id']}", params={"email": chuck.email.upper()}).status_code == 200


def test_mock_emails_escape_user_text(client):
    with Session(engine) as s:
        p = s.exec(select(Profile).where(Profile.lifecycle_state == "claimed")).first()
        p.name = "<script>alert(1)</script>"
        s.add(p)
        s.commit()
        pid, email = p.id, p.email
    client.post("/api/auth/demo-login", json={"profile_id": pid})
    from agent.nudges import run_nudges

    with Session(engine) as s:
        run_nudges(s, profile_id=pid, force=True)
    mails = client.get("/api/mailbox", params={"email": email}).json()
    for m in mails:
        body = client.get(f"/api/mailbox/{m['id']}", params={"email": email}).json()["body_html"]
        assert "<script>" not in body


# --- search ------------------------------------------------------------------------------------------


def test_keyword_search_finds_people_by_name_company_and_title(client):
    by_name = client.get("/api/search", params={"keyword": "tegano"}).json()
    assert any("Tegano" in r["name"] for r in by_name["results"])
    by_company = client.get("/api/search", params={"keyword": "annie"}).json()
    assert any(r["business_name"] and "AnnieMac" in r["business_name"] for r in by_company["results"])
    by_title = client.get("/api/search", params={"keyword": "branch manager"}).json()
    assert any(r["name"] == "Jonathan Sweat" for r in by_title["results"])
    assert client.get("/api/search", params={"keyword": "zzzz-nothing"}).json()["count"] == 0
    assert client.get("/api/search", params={"keyword": "50%"}).json()["count"] == 0  # % is literal, not a wildcard


def test_location_filter_is_a_contains_match_and_results_flag_claimable(client):
    austin = client.get("/api/search", params={"location": "Austin"}).json()["results"]
    assert austin and all("Austin" in r["location"] for r in austin)
    ryan = client.get("/api/search", params={"keyword": "Ryan Davis"}).json()["results"][0]
    assert ryan["can_claim"] and ryan["vertical"] == "Insurance"
    insurance = client.get("/api/search", params={"category": "Insurance Agent", "service": "Life insurance"}).json()
    assert insurance["count"] > 0


def test_search_filters_list_categories_locations_and_services(client):
    filters = client.get("/api/search/filters").json()
    assert {"Dentist", "Insurance Agent", "Mortgage Lender", "Mortgage Loan Officer", "Real Estate Agent"} <= set(filters["categories"])
    assert "Roanoke, VA" in filters["locations"] and "" not in filters["locations"]
    assert "FHA home loan" in filters["services"] and "Life insurance" in filters["services"]


def test_one_keyword_box_also_finds_a_city_or_a_category(client):
    by_city = client.get("/api/search", params={"keyword": "gardena"}).json()
    assert by_city["count"] >= 1 and all("Gardena" in r["location"] for r in by_city["results"])
    by_category = client.get("/api/search", params={"keyword": "insurance agent"}).json()
    assert by_category["count"] >= 1 and all(r["category"] == "Insurance Agent" for r in by_category["results"])
