from aiogram.filters import BaseFilter
from aiogram.types import Message

from src.core.config import Settings


class OwnerOnlyFilter(BaseFilter):
    def __init__(self, settings: Settings) -> None:
        self.owner_tg_id = settings.owner_tg_id

    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id == self.owner_tg_id
