from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.category_config import get_config
from app.db import get_session
from app.models import Category, CategoryService, Vertical

router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])


@router.get("")
def get_taxonomy(session: Session = Depends(get_session)):
    """Verticals -> categories -> services, for the claim card's cascading dropdowns."""
    services = session.exec(select(CategoryService).order_by(CategoryService.sort_order)).all()
    categories = session.exec(select(Category).where(Category.is_active == True).order_by(Category.name)).all()  # noqa: E712
    return {
        "verticals": [
            {
                "key": v.key,
                "name": v.name,
                "categories": [
                    {
                        "id": c.id,
                        "key": c.key,
                        "name": c.name,
                        "services": [{"key": s.key, "name": s.name} for s in services if s.category_id == c.id],
                    }
                    for c in categories
                    if c.vertical_id == v.id
                ],
            }
            for v in session.exec(select(Vertical).order_by(Vertical.name)).all()
        ]
    }


@router.get("/categories/{category_id}")
def get_category(category_id: int, session: Session = Depends(get_session)):
    """One category's rules: what the claim requires, what Profile Completion counts, which URLs it
    tracks and its score split. Loaded when an agent signs in so the flow adapts to the category."""
    if session.get(Category, category_id) is None:
        raise HTTPException(status_code=404, detail="Category not found")
    config = get_config(category_id)
    return {
        "id": config.id,
        "key": config.key,
        "name": config.name,
        "vertical": config.vertical,
        "mandatory_fields": config.mandatory_fields,
        "basic_fields": config.basic_fields,
        "url_slots": config.url_slots,
        "services": config.services,
        "rules": config.rules,
        "sections": [
            {"key": s.key, "label": s.label, "max_points": s.max_points, "is_pro_only": s.is_pro_only}
            for s in config.ordered_sections
        ],
        "common_max": config.common_max,
        "pro_max": config.pro_max,
    }
