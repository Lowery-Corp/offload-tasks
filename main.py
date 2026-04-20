from fastapi import FastAPI
from contextlib import asynccontextmanager

from starlette.middleware.cors import CORSMiddleware
from middleware.request_id import RequestIDMiddleware
from httpxC.http_client import http_client

from api.v1.api import api_router
# from app.tasks.file_tasks import process_document

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await http_client.aclose()

app = FastAPI(
    title="Offload Tasks API",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


# @app.post("/documents/{document_id}/process")
# async def queue_document_processing(document_id: int) -> dict[str, str]:
#     task = process_document.delay(document_id)
#     return {
#         "task_id": task.id,
#         "status": "queued",
#     }