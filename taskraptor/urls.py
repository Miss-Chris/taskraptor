from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.urls import path, re_path
from django.conf import settings
from ninja import NinjaAPI

from apps.accounts.api import router as auth_router
from apps.tasks.api import router as tasks_router

api = NinjaAPI(
    csrf=True,
    title="TaskRaptor API",
    version="1.0.0",
)
api.add_router("/auth", auth_router, tags=["auth"])
api.add_router("/tasks", tasks_router, tags=["tasks"])


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
    re_path(r"^.*$", spa_view),
]
