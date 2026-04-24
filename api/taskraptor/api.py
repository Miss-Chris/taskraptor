from ninja import NinjaAPI

api = NinjaAPI(title="TaskRaptor API", version="1.0.0")


def register_routers():
    from accounts.api import router as auth_router
    from agent.api import router as debug_router
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


register_routers()
