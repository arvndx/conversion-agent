"""The widget's look per site (one site per domain), kept on the site row (conv_domains: primary_color, accent_color).

The chat API reads the colours when the widget loads its config. The dashboard reads and writes the whole look.
A domain must be one of the customer's sites; the caller checks that (see dashboard/server.py).
"""

import json
import re

import psycopg
from psycopg.types.json import Jsonb

DEFAULT_STYLE = {"font_size": 14, "font_family": "Arial", "primary": "#7a2e1d", "accent": "#a2432b",
                 "text": "#1f1a17", "placement": "right"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def get_style(conn: psycopg.Connection, resource_id: str, domain: str) -> dict:
    """The colours of the site (conv_domains). resource_id is the professional id."""
    row = conn.execute("SELECT primary_color, accent_color FROM conv_domains WHERE professional_id = %s AND domain = %s",
                       (resource_id, domain)).fetchone()
    if row is None:
        return dict(DEFAULT_STYLE)
    return {**DEFAULT_STYLE, "primary": row[0], "accent": row[1]}


def get_theme(conn: psycopg.Connection, resource_type: str, resource_id: str, domain: str) -> dict:
    style = get_style(conn, resource_id, domain)
    return {"primary": style["primary"], "accent": style["accent"]}


def set_style(conn: psycopg.Connection, resource_id: str, domain: str, style: dict) -> dict:
    if not all(HEX.match(style[c]) for c in ("primary", "accent", "text")):
        raise ValueError("colours must be #RRGGBB")
    done = conn.execute("UPDATE conv_domains SET primary_color = %s, accent_color = %s WHERE professional_id = %s AND domain = %s",
                        (style["primary"], style["accent"], resource_id, domain)).rowcount
    if done == 0:
        raise LookupError("no such site")
    return {**DEFAULT_STYLE, **style}


def reset_style(conn: psycopg.Connection, resource_id: str, domain: str) -> dict:
    done = conn.execute("UPDATE conv_domains SET primary_color = %s, accent_color = %s WHERE professional_id = %s AND domain = %s",
                        (DEFAULT_STYLE["primary"], DEFAULT_STYLE["accent"], resource_id, domain)).rowcount
    if done == 0:
        raise LookupError("no such site")
    return dict(DEFAULT_STYLE)
