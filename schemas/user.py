from pydantic import BaseModel, EmailStr, field_validator

class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    def normalize_email(cls, email: EmailStr) -> str:
        return email.strip().lower()

class UserToken(BaseModel):
    token: str

class AuthorizedUser(BaseModel):
    id: str
    username: str
    is_admin: bool
    email: EmailStr