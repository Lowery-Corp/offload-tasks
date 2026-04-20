from fastapi import APIRouter

from api.v1.endpoints import health, file_ingestion

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(file_ingestion.router, prefix="/ingestion", tags=["ingestion"])