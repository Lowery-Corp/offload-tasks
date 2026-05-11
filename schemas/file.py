from pydantic import BaseModel

class NewFileIngestionTask(BaseModel):
    user_id: str
    file_id: str
    storage_key: str

class UserFile(BaseModel):
    file_id: str

