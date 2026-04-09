from datetime import timedelta

from django.contrib.auth import authenticate
from django.conf import settings
from django.utils import timezone
from ninja import Router, Status

from accounts.bearer import AuthBearer
from accounts.models import User, UserSession
from accounts.schemas import ErrorOut, LoginIn, RegisterIn, TokenOut, UserOut

router = Router(tags=["auth"])


def _default_session_expiry():
    return timezone.now() + timedelta(days=settings.USER_SESSION_TTL_DAYS)


@router.post("/register", response={201: TokenOut, 400: ErrorOut})
def register(request, payload: RegisterIn):
    email = User.objects.normalize_email(payload.email)
    if User.objects.filter(email=email).exists():
        return Status(400, {"detail": "Email already registered."})

    user = User.objects.create_user(
        email=email,
        password=payload.password,
    )
    session = UserSession.objects.create(
        user=user,
        expires_at=_default_session_expiry(),
    )
    return Status(201, {"token": str(session.token)})


@router.post("/login", response={200: TokenOut, 401: ErrorOut})
def login(request, payload: LoginIn):
    email = User.objects.normalize_email(payload.email)
    user = authenticate(username=email, password=payload.password)
    if user is None:
        return Status(401, {"detail": "Invalid credentials."})

    session = UserSession.objects.create(
        user=user,
        expires_at=_default_session_expiry(),
    )
    return Status(200, {"token": str(session.token)})


@router.get("/me", auth=AuthBearer(), response={200: UserOut, 401: ErrorOut})
def me(request):
    return Status(200, request.auth)
