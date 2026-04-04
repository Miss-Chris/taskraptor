from datetime import datetime

from ninja import Schema


class RegisterIn(Schema):
    username: str
    email: str
    password: str


class LoginIn(Schema):
    username: str
    password: str


class TokenOut(Schema):
    token: str


class UserOut(Schema):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    date_joined: datetime


class ErrorOut(Schema):
    detail: str
