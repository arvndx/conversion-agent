"""Per-category rules, loaded from the taxonomy tables and cached in memory.

Scoring, suggestions and the agent all need a profile's category rules (which score sections exist and
which are Pro-locked, which fields make up Profile Completion, which URL slots feed Connections and
Listings). Those functions take a bare profile object, so rather than thread a DB session through
them, the (small, rarely changing) taxonomy is read once and cached. Call `invalidate()` after the
taxonomy is reseeded.
"""

from dataclasses import dataclass, field
from threading import Lock

from sqlmodel import Session, select

from app.constants import SCORE_SECTIONS
from app.db import engine
from app.models import Category, CategoryScoreSection, CategoryService, Vertical

# Native scale of each section's formula in app/scoring.py. A section's earned points are the
# formula's result scaled by max_points / native, so a category can change a section's maximum
# without touching the formula.
NATIVE_SECTION_MAX = {
    "reviews": 300,
    "profile_completion": 100,
    "connections": 100,
    "web_analytics": 250,
    "listings": 100,
}


@dataclass(frozen=True)
class SectionConfig:
    key: str
    label: str
    max_points: int
    is_pro_only: bool
    sort_order: int


@dataclass(frozen=True)
class CategoryConfig:
    id: int | None
    key: str
    name: str
    vertical: str
    sections: dict[str, SectionConfig]
    mandatory_fields: list[str] = field(default_factory=list)
    basic_fields: list[dict] = field(default_factory=list)  # [{"key", "label", "weight"}]
    url_slots: list[dict] = field(default_factory=list)  # [{"platform", "label", "kind"}]
    services: list[dict] = field(default_factory=list)  # [{"key", "name"}]
    rules: dict = field(default_factory=dict)

    @property
    def ordered_sections(self) -> list[SectionConfig]:
        return sorted(self.sections.values(), key=lambda s: s.sort_order)

    @property
    def common_max(self) -> int:
        return sum(s.max_points for s in self.sections.values() if not s.is_pro_only)

    @property
    def pro_max(self) -> int:
        return sum(s.max_points for s in self.sections.values())

    @property
    def completion_field_keys(self) -> list[str]:
        return [f["key"] for f in self.basic_fields]

    def slots(self, kind: str) -> list[dict]:
        return [s for s in self.url_slots if s["kind"] == kind]


# What a profile with no category row (legacy data) is scored as: the standard split, no category fields.
_STANDARD = [
    ("reviews", "Reviews & Replies", 300, False),
    ("profile_completion", "Profile Completion", 100, False),
    ("connections", "Connections", 100, False),
    ("web_analytics", "Website Health", 250, True),
    ("listings", "Listings", 100, True),
]

_FALLBACK = CategoryConfig(
    id=None,
    key="default",
    name="Default",
    vertical="",
    sections={k: SectionConfig(k, label, mx, pro, i) for i, (k, label, mx, pro) in enumerate(_STANDARD)},
    basic_fields=[
        {"key": k, "label": k.replace("_", " ").capitalize(), "weight": 1}
        for k in ("phone_number", "license_number", "website_url", "bio", "service_area", "year_started")
    ],
    url_slots=[],
)

_lock = Lock()
_by_id: dict[int, CategoryConfig] = {}
_by_name: dict[str, CategoryConfig] = {}
_loaded = False


def invalidate() -> None:
    global _loaded
    with _lock:
        _by_id.clear()
        _by_name.clear()
        _loaded = False


def _load() -> None:
    global _loaded
    with _lock:
        if _loaded:
            return
        with Session(engine) as session:
            verticals = {v.id: v.name for v in session.exec(select(Vertical)).all()}
            sections = session.exec(select(CategoryScoreSection)).all()
            services = session.exec(select(CategoryService).order_by(CategoryService.sort_order)).all()
            for category in session.exec(select(Category)).all():
                cat_sections = {
                    s.section: SectionConfig(s.section, s.label, s.max_points, s.is_pro_only, s.sort_order)
                    for s in sections
                    if s.category_id == category.id and s.section in SCORE_SECTIONS
                }
                config = CategoryConfig(
                    id=category.id,
                    key=category.key,
                    name=category.name,
                    vertical=verticals.get(category.vertical_id, ""),
                    sections=cat_sections,
                    mandatory_fields=list(category.mandatory_fields),
                    basic_fields=list(category.basic_fields),
                    url_slots=list(category.url_slots),
                    services=[{"key": s.key, "name": s.name} for s in services if s.category_id == category.id],
                    rules=dict(category.rules),
                )
                _by_id[category.id] = config
                _by_name[category.name] = config
        _loaded = True


def get_config(category_id: int | None = None, category_name: str | None = None) -> CategoryConfig:
    """The rules for a category, falling back to the standard split for unknown/legacy categories."""
    _load()
    if category_id is not None and category_id in _by_id:
        return _by_id[category_id]
    if category_name and category_name in _by_name:
        return _by_name[category_name]
    return _FALLBACK


def config_for(profile) -> CategoryConfig:
    return get_config(getattr(profile, "category_id", None), getattr(profile, "category", None))


def all_configs() -> list[CategoryConfig]:
    _load()
    return list(_by_id.values())
