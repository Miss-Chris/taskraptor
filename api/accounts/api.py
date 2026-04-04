from django.contrib.auth import authenticate
from ninja import Router, Status

from accounts.bearer import AuthBearer
from accounts.models import User, UserSession
from accounts.schemas import ErrorOut, LoginIn, RegisterIn, TokenOut, UserOut

router = Router(tags=["auth"])


@router.post("/register", response={201: TokenOut, 400: ErrorOut})
def register(request, payload: RegisterIn):
    if User.objects.filter(username=payload.username).exists():
        return Status(400, {"detail": "Username already taken."})

    user = User.objects.create_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )
    session = UserSession.objects.create(user=user)
    return Status(201, {"token": str(session.token)})


@router.post("/login", response={200: TokenOut, 401: ErrorOut})
def login(request, payload: LoginIn):
    user = authenticate(username=payload.username, password=payload.password)
    if user is None:
        return Status(401, {"detail": "Invalid credentials."})

    session = UserSession.objects.create(user=user)
    return Status(200, {"token": str(session.token)})


@router.get("/me", auth=AuthBearer(), response={200: UserOut, 401: ErrorOut})
def me(request):
    return Status(200, request.auth)
