from datetime import timedelta

from django.contrib.auth import authenticate
from django.conf import settings
from django.utils import timezone
from ninja import Router, Status

from accounts.bearer import AuthBearer
from accounts.models import User, UserSession
from accounts.schemas import (
    ErrorOut,
    LoginIn,
    RegisterIn,
    TokenOut,
    UserOut,
    UserSettingsOut,
    UserSettingsPatchIn,
    UserTimezoneIn,
)
from accounts.services import seed_default_user_data
from agent.models import get_or_create_system_model
from taskraptor.timezones import is_valid_timezone

router = Router(tags=["auth"])


def _default_session_expiry():
    return timezone.now() + timedelta(days=settings.USER_SESSION_TTL_DAYS)


@router.post("/register", response={201: TokenOut, 400: ErrorOut, 403: ErrorOut})
def register(request, payload: RegisterIn):
    if not settings.ALLOW_PUBLIC_REGISTRATION:
        return Status(403, {"detail": "Public registration is disabled."})

    email = User.objects.normalize_email(payload.email)
    if User.objects.filter(email=email).exists():
        return Status(400, {"detail": "Email already registered."})

    user = User.objects.create_user(
        email=email,
        password=payload.password,
    )
    get_or_create_system_model(user)
    seed_default_user_data(user)
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


@router.patch(
    "/me/timezone",
    auth=AuthBearer(),
    response={200: UserOut, 400: ErrorOut, 401: ErrorOut},
)
def update_timezone(request, payload: UserTimezoneIn):
    timezone_name = payload.timezone.strip()
    if not is_valid_timezone(timezone_name):
        return Status(400, {"detail": "Invalid IANA timezone."})

    user = request.auth
    user.timezone = timezone_name
    user.save(update_fields=["timezone"])
    return Status(200, user)


@router.get(
    "/settings",
    auth=AuthBearer(),
    response={200: UserSettingsOut, 401: ErrorOut},
)
def get_settings(request):
    user = request.auth
    return Status(200, user)


@router.patch(
    "/settings",
    auth=AuthBearer(),
    response={200: UserSettingsOut, 400: ErrorOut, 401: ErrorOut},
)
def update_settings(request, payload: UserSettingsPatchIn):
    user = request.auth
    update_fields = []

    if payload.timezone is not None:
        timezone_name = payload.timezone.strip()
        if not is_valid_timezone(timezone_name):
            return Status(400, {"detail": "Invalid IANA timezone."})
        user.timezone = timezone_name
        update_fields.append("timezone")

    if payload.prompt_instructions is not None:
        user.prompt_instructions = payload.prompt_instructions
        update_fields.append("prompt_instructions")

    if update_fields:
        user.save(update_fields=update_fields)

    return Status(200, user)
