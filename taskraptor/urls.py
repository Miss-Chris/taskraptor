from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import connections
from django.http import FileResponse, HttpResponse, JsonResponse
from django.urls import path, re_path
from django.conf import settings
from ninja import NinjaAPI

from apps.accounts.api import router as auth_router
from apps.tasks.api import router as tasks_router

api = NinjaAPI(
    csrf=settings.NINJA_CSRF,
    title="TaskRaptor API",
    version="1.0.0",
)
api.add_router("/auth", auth_router, tags=["auth"])
api.add_router("/tasks", tasks_router, tags=["tasks"])


def healthcheck_view(request):
    """Return a 200 only when the app can execute a real DB query."""
    try:
        user_count = get_user_model().objects.count()
        db_name = connections["default"].settings_dict.get("NAME")
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "database": "unreachable",
                "error": str(exc),
            },
            status=503,
        )

    return JsonResponse(
        {
            "ok": True,
            "database": "reachable",
            "database_name": db_name,
            "user_count": user_count,
        }
    )


def spa_view(request):
    """Serve the React SPA for all non-API routes."""
    index_path = settings.BASE_DIR / "frontend" / "dist" / "index.html"
    if index_path.exists():
        return FileResponse(open(index_path, "rb"), content_type="text/html")
    return HttpResponse(
        "<h1>TaskRaptor</h1>"
        "<p>Frontend not built. Run <code>cd frontend &amp;&amp; npm run build</code>.</p>",
        status=503,
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("healthz", healthcheck_view),
    re_path(r"^.*$", spa_view),
]
