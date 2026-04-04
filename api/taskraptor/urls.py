from django.urls import path

from taskraptor.api import api

urlpatterns = [
    path("api/", api.urls),
]
