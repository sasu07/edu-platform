import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["System"])
def healthcheck():
    return {"status": "ok"}


@router.get("/config/public", tags=["System"])
def public_config():
    """Config public (fără auth) pentru frontend.
    `exam_date` = data BAC, configurabilă din env (EXAM_DATE, format YYYY-MM-DD).
    Dacă nu e setată, countdown-ul se ascunde în frontend."""
    exam_date = os.getenv("EXAM_DATE") or None
    return {"exam_date": exam_date}
