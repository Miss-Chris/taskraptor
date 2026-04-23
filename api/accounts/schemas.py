from datetime import datetime
from uuid import UUID

from ninja import Schema


class RegisterIn(Schema):
    email: str
    password: str


class LoginIn(Schema):
    email: str
    password: str


class TokenOut(Schema):
    token: str


class UserOut(Schema):
    id: UUID
    email: str
    first_name: str
    last_name: str
    date_joined: datetime


class ErrorOut(Schema):
    detail: str
