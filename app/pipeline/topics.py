"""Topics: the chat's question types, for each site. They start as the category's topics (its conversion triggers) and
grow as the chat meets questions the list does not have. A new topic is learned from a chat's label, matched against
the site's topics first, and added to conv_site.topics when it is new.

conv_site.topics is a list of {"id", "label", "source", "added_at"}; source is "category" or "learned". A new label is
kept on its chats first and joins the list once 5 chats in 3 days name it (maybe_promote).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from psycopg.types.json import Jsonb
from rapidfuzz import fuzz

SHARED = Path(__file__).resolve().parent.parent / "shared"
OTHER = "other_questions"
MAX_LEARNED = 40          # more than this many learned topics for one site: the rest count as "other questions"
FUZZY_MATCH = 85          # a label this similar to a known topic is that topic
PROMOTE_SESSIONS = 5     # a new topic joins the site's list after this many chats in PROMOTE_DAYS days
PROMOTE_DAYS = 3

# Plain labels for the topics the dashboard shows. Any other id shows as its words, for example "pet policy".
TOPIC_LABELS = {
    "menu": "View the menu", "opening_hours": "Opening hours", "booking": "Book a table", "ordering": "Online ordering",
    "location_directions": "Directions", "parking": "Parking", "dietary": "Vegetarian dishes", "dish": "Dish questions",
    OTHER: "Other questions",
}


def label_for(topic_id: str) -> str:
    return TOPIC_LABELS.get(topic_id, topic_id.replace("_", " ").capitalize())


def normalize_label(text) -> str | None:
    """A label in plain words, lower case, at most four words. None when nothing is left."""
    if not isinstance(text, str):
        return None
    words = re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split()[:4]
    return " ".join(words) or None


def category_topics(slug: str) -> list[dict]:
    """The category's topics as the site's first topics. From the category bundle, or the sample file for a category
    that has no bundle yet (the restaurant)."""
    from shared.category_bundle import build_category_bundle

    try:
        topics = build_category_bundle(slug)["topics"]
    except FileNotFoundError:
        topics = json.loads((SHARED / "samples" / f"{slug}_category.json").read_text(encoding="utf-8"))["topics"]
    return [{"id": t["id"], "label": label_for(t["id"]), "source": "category"} for t in topics]


def _label_from_id(topic_id: str) -> str:
    words = topic_id.replace("_", " ")
    return words[0].upper() + words[1:]


def resolve_topic(cur, site_id, label: str) -> str:
    """The id of the topic this label means for the site. Matches the site's topics and the topics chats have named in
    the last PROMOTE_DAYS days (not yet confirmed). Otherwise the label becomes a new candidate id. A candidate joins the
    site's list only when maybe_promote confirms it. Locks the site row while it works."""
    name = normalize_label(label)
    if name is None:
        return OTHER
    cur.execute("select topics from conv_site where site_id = %s for update", (site_id,))
    topics = cur.fetchone()[0] or []
    as_id = name.replace(" ", "_")[:40]
    known = [(t["id"], t["label"]) for t in topics]
    cur.execute(
        "select distinct topic from conv_session where site_id = %s and topic is not null "
        "and started_at >= now() - make_interval(days => %s)",
        (site_id, PROMOTE_DAYS),
    )
    known += [(row[0], _label_from_id(row[0])) for row in cur.fetchall()]
    for topic_id, topic_label in known:
        if topic_id == as_id or topic_label.lower() == name:
            return topic_id
    best = None
    for topic_id, topic_label in known:
        score = fuzz.token_sort_ratio(name, topic_label.lower())
        if score >= FUZZY_MATCH and (best is None or score > best[0]):
            best = (score, topic_id)
    if best:
        return best[1]
    if sum(1 for t in topics if t["source"] == "learned") >= MAX_LEARNED:
        return OTHER
    return as_id


def maybe_promote(cur, site_id, topic_id: str) -> bool:
    """Add a learned topic to the site's list once at least PROMOTE_SESSIONS chats named it in the last PROMOTE_DAYS
    days. Returns True when it was added in this call. Category topics are already on the list."""
    cur.execute("select topics from conv_site where site_id = %s for update", (site_id,))
    topics = cur.fetchone()[0] or []
    if any(t["id"] == topic_id for t in topics):
        return False
    cur.execute(
        "select count(*) from conv_session where site_id = %s and topic = %s "
        "and started_at >= now() - make_interval(days => %s)",
        (site_id, topic_id, PROMOTE_DAYS),
    )
    if cur.fetchone()[0] < PROMOTE_SESSIONS:
        return False
    if sum(1 for t in topics if t["source"] == "learned") >= MAX_LEARNED:
        return False
    topics.append({"id": topic_id, "label": _label_from_id(topic_id), "source": "learned",
                   "added_at": datetime.now(timezone.utc).date().isoformat()})
    cur.execute("update conv_site set topics = %s where site_id = %s", (Jsonb(topics), site_id))
    return True
