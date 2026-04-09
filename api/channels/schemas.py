from datetime import datetime

from ninja import Schema


class TelegramStatusOut(Schema):
    connected: bool
    bot_name: str


class JoinCodeOut(Schema):
    code: str
    expires_at: datetime
    bot_name: str
