from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class NetworkAccount(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    description: str | None = None
    followers_count: int | None = None
    following_count: int | None = None
    tweets_count: int | None = None
    created_at: datetime | None = None
    verified: bool = False
    protected: bool = False
    profile_image_url: str | None = None


class NetworkProvider(Protocol):
    async def get_following(self, username: str) -> list[NetworkAccount]: ...
