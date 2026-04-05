from ninja.security import HttpBearer


class AuthBearer(HttpBearer):
    def authenticate(self, request, token: str):
        from accounts.models import UserSession

        try:
            session = UserSession.objects.select_related("user").get(token=token)
            if session.is_expired:
                return None
            return session.user
        except (UserSession.DoesNotExist, ValueError):
            return None
