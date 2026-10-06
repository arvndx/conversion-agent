"""Try the scraper on one URL from the terminal (live fetch, no database).

    cd backend && python -m app.scraping.cli https://example.com --name "Jane Doe" --phone "(555) 123-4567"
    python -m app.scraping.cli <url> --name "..." --extract     # also run the Claude extraction
"""

import argparse
import asyncio
import json

from app.scraping.fetch import fetch_page, proxy_configured
from app.scraping.parse import parse_html, platform_for_url
from app.scraping.validate import validate_identity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--name", required=True)
    parser.add_argument("--phone")
    parser.add_argument("--email")
    parser.add_argument("--extract", action="store_true", help="also run the Claude extraction (uses the API)")
    args = parser.parse_args()

    print(f"Oxylabs proxy configured: {proxy_configured()}")
    result = asyncio.run(fetch_page(args.url))
    print(f"fetched via={result.via} status={result.status} ok={result.ok} blocked={result.blocked} error={result.error}")
    if not result.html:
        return

    page = parse_html(result.html, args.url)
    validation = validate_identity(
        profile_name=args.name, page_text=page.text, json_ld_names=page.json_ld_names,
        profile_phone=args.phone, profile_email=args.email, page_phones=page.phones, page_emails=page.emails,
    )
    print(json.dumps({
        "platform": platform_for_url(args.url), "title": page.title, "meta_description": page.meta_description,
        "text_chars": len(page.text), "phones": page.phones[:5], "emails": page.emails[:5],
        "links": page.links, "json_ld_names": page.json_ld_names[:3], "json_ld_hours": page.json_ld_hours,
        "validation": validation.as_dict(),
    }, indent=2))

    if args.extract and validation.validated:
        from agent.extraction import extract_fields

        print(json.dumps(extract_fields(page.markdown, url=args.url, platform=platform_for_url(args.url)), indent=2))
    elif args.extract:
        print("skipped extraction: name not validated on this page")


if __name__ == "__main__":
    main()
