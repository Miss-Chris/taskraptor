from ninja.security import HttpBearer


class AuthBearer(HttpBearer):
    def authenticate(self, request, token: str):
        from accounts.models import UserSession

        try:
            session = UserSession.objects.select_related("user").get(token=token)
            return session.user
        except (UserSession.DoesNotExist, ValueError):
            return None
