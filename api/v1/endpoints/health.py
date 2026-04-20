from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}