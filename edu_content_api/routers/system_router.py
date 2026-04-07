from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["System"])
def healthcheck():
    return {"status": "ok"}
