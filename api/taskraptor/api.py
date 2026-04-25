from django.db import DEFAULT_DB_ALIAS, connections
from django.db.utils import DatabaseError
from ninja import NinjaAPI, Schema, Status

api = NinjaAPI(title="TaskRaptor API", version="1.0.0")


class HealthOut(Schema):
    status: str
    database: str


def _database_is_healthy() -> bool:
    try:
        with connections[DEFAULT_DB_ALIAS].cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except DatabaseError:
        return False


@api.get("/health", response={200: HealthOut, 503: HealthOut}, tags=["health"])
def health(request):
    if _database_is_healthy():
        return Status(200, {"status": "ok", "database": "ok"})
    return Status(503, {"status": "error", "database": "unavailable"})


def register_routers():
    from accounts.api import router as auth_router
    from agent.api import router as debug_router
    from agent.usage_api import router as usage_router
    from automations.api import router as automations_router
    from channels.web_api import router as chat_router
    from channels.api import router as telegram_router
    from tasks.api import router as tasks_router

    api.add_router("/auth", auth_router)
    api.add_router("/automations", automations_router)
    api.add_router("/chat", chat_router)
    api.add_router("/debug", debug_router)
    api.add_router("/telegram", telegram_router)
    api.add_router("/tasks", tasks_router)
    api.add_router("/usage", usage_router)


register_routers()
