import uuid
from pydantic import BaseModel, ConfigDict



class FileChunkCreate(BaseModel):
    file_id: str
    chunk_index: int
    chunk_text: str
    embedding: list[float]
    token_count: int
    embedding_status: str = "competed"


class FileChunkUpdate(BaseModel):
    file_id: int | None = None
    chunk_index: int | None = None
    chunk_text: str | None = None
    embedding: list[float] | None = None
    token_count: int | None = None
    embedding_status: str | None = None


class FileChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_id: uuid.UUID
    chunk_index: int
    chunk_text: str
    embedding: list[float]
    token_count: int
    embedding_status: str
