"""
Typed Django requests for use with django-ninja + ``AuthBearer``.

Ninja sets ``request.auth`` to the return value of the auth backend (here, ``User``).
The runtime object is a normal ``HttpRequest``; this class exists for static analysis.
"""

from __future__ import annotations

from django.http import HttpRequest

from accounts.models import User


class AuthedHttpRequest(HttpRequest):
    """HTTP request where ``auth`` is the signed-in :class:`User` (Ninja + ``AuthBearer``)."""

    auth: User
