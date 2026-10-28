"""One business website per test business, for the live widget test.

Each business has its own port, which is also its domain (localhost:<port>), so its own site key works there.
The page loads the widget with a plain script tag: no demo mode and no page tracking (real sites keep it off).

Run one per business from the app folder (the port is the business's port):
    BUSINESS_PORT=8101 .venv/bin/uvicorn sites.business_pages:app --host :: --port 8101
"""

import os
from html import escape
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from shared.test_businesses import BUSINESSES, resource_id_for

PORT = int(os.environ.get("BUSINESS_PORT", "0"))
BUSINESS = next((b for b in BUSINESSES if b["port"] == PORT), None)
WIDGET = Path(__file__).resolve().parent / "widget" / "widget.js"

PAGE_TEXT = {
    "mortgage_broker": {
        "headline": "Mortgages from independent brokers who compare lenders for you",
        "services": ["Find a broker near you", "Get pre-approved before you house hunt", "Visit our office"],
        "about": "We shop the market so you do not have to. Tell us about your home purchase or refinance and we match you with a broker.",
    },
    "mortgage_lender": {
        "headline": "Home loans from a lender you can talk to",
        "services": ["Subscribe to rate alerts", "Start a pre-application", "Visit a branch"],
        "about": "Purchase, refinance and first-time buyer loans, with a loan officer who explains each step.",
    },
    "health_insurance_agency": {
        "headline": "Health plans, explained in plain language",
        "services": ["Book a coverage consultation", "Compare plans side by side", "Get help with COBRA or a job change"],
        "about": "Individual, family and employer health plans. We help you choose, enrol and keep your coverage.",
    },
    "commercial_real_estate_agency": {
        "headline": "Commercial property for buyers, tenants and investors",
        "services": ["View available listings", "Book a market consultation", "List your commercial property"],
        "about": "Office, retail, industrial and investment property, with market reports and investment analysis from our brokers.",
    },
}

app = FastAPI(title=f"Test business page on port {PORT}")


def _page(business: dict) -> str:
    text = PAGE_TEXT[business["slug"]]
    services = "".join(f"<li>{escape(item)}</li>" for item in text["services"])
    hours = business["hours"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(business['name'])}</title>
  <link rel="icon" href="data:,">
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f7f7f5; }}
    header {{ background: #1f3a5f; color: #fff; padding: 22px 28px; }}
    header h1 {{ margin: 0; font-size: 22px; }}
    main {{ max-width: 860px; margin: 0 auto; padding: 28px; }}
    h2 {{ font-size: 26px; margin: 0 0 12px; }}
    .card {{ background: #fff; border: 1px solid #e3e6ea; border-radius: 8px; padding: 18px; margin: 16px 0; }}
    li {{ margin: 6px 0; }}
    footer {{ color: #5b6672; font-size: 13px; padding: 24px 28px; text-align: center; }}
  </style>
</head>
<body>
  <header><h1>{escape(business['name'])}</h1></header>
  <main>
    <h2>{escape(text['headline'])}</h2>
    <p>{escape(text['about'])}</p>
    <div class="card"><strong>What we can help with</strong><ul>{services}</ul></div>
    <div class="card"><strong>Opening hours</strong><br>Monday to Friday {escape(hours['mon_fri'])}<br>Saturday and Sunday {escape(hours['sat_sun'])}</div>
    <div class="card"><strong>Visit us</strong><br>{escape(business['address'])}<br>{escape(business['phone'])} · {escape(business['email'])}</div>
  </main>
  <footer>{escape(business['name'])}. Test page for the Conversion Agent, not a live website.</footer>
  <script src="/widget.js" data-site-key="{business['site_key']}" async></script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    if BUSINESS is None:
        raise HTTPException(status_code=404, detail="no test business on this port")
    return _page(BUSINESS)


@app.get("/widget.js")
def widget() -> FileResponse:
    return FileResponse(WIDGET, media_type="application/javascript")


@app.get("/health")
def health() -> dict:
    return {"port": PORT, "business": BUSINESS["name"] if BUSINESS else None, "resource_id": resource_id_for(BUSINESS) if BUSINESS else None}
