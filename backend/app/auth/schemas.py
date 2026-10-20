from pydantic import BaseModel


class RegisterIn(BaseModel):
    email: str
    name: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class AccessTokenOut(BaseModel):
    """The refresh token is not part of the body; it is set as an httpOnly cookie."""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    email: str
    name: str
