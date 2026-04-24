from ninja import NinjaAPI

api = NinjaAPI(title="TaskRaptor API", version="1.0.0")


def register_routers():
    from accounts.api import router as auth_router
    from channels.api import router as telegram_router
    from tasks.api import router as tasks_router

    api.add_router("/auth", auth_router)
    api.add_router("/telegram", telegram_router)
    api.add_router("/tasks", tasks_router)


register_routers()
