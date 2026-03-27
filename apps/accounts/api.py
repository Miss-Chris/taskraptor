from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest
from django.middleware.csrf import get_token
from ninja import Router, Schema
from ninja.security import django_auth

from .models import User

router = Router()


class RegisterIn(Schema):
    email: str
    password: str


class LoginIn(Schema):
    email: str
    password: str


class UserOut(Schema):
    id: int
    email: str


@router.get("/csrf")
def csrf_view(request: HttpRequest):
    return {"csrfToken": get_token(request)}


@router.post("/register", response={201: UserOut, 400: dict})
def register_view(request: HttpRequest, data: RegisterIn):
    if User.objects.filter(email=data.email).exists():
        return 400, {"detail": "An account with this email already exists"}
    user = User.objects.create_user(email=data.email, password=data.password)
    login(request, user)
    return 201, user


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
