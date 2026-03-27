from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest
from ninja import Router, Schema
from ninja.security import django_auth

router = Router()


class LoginIn(Schema):
    email: str
    password: str


class UserOut(Schema):
    id: int
    email: str


@router.post("/login", response={200: UserOut, 401: dict})
def login_view(request: HttpRequest, data: LoginIn):
    user = authenticate(request, username=data.email, password=data.password)
    if user is None:
        return 401, {"detail": "Invalid email or password"}
    login(request, user)
    return 200, user


@router.post("/logout", auth=django_auth)
def logout_view(request: HttpRequest):
    logout(request)
    return {"ok": True}


@router.get("/me", auth=django_auth, response=UserOut)
def me(request: HttpRequest):
    return request.user
