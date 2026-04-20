from pydantic import BaseModel

class NewFileIngestionTask(BaseModel):
    user_id: str
    file_id: str
    storage_key: str

