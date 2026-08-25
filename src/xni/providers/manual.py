from copy import deepcopy
from datetime import datetime
from typing import Any

from .base import NetworkAccount


_X_CREATED_AT_FORMAT = "%a %b %d %H:%M:%S %z %Y"


class ManualImportProvider:
    def __init__(self, payload: dict[str, Any]):
        mode = payload.get("mode")
        if mode != "following":
            raise ValueError("manual import payload mode must be 'following'")

        target_label = payload.get("targetLabel")
        if not isinstance(target_label, str) or not target_label.strip():
            raise ValueError("manual import payload requires targetLabel")

        users = payload.get("users")
        if not isinstance(users, list):
            raise ValueError("manual import payload requires users list")

        self.target_label = target_label.strip().lstrip("@")
        self.mode = mode
        self._payload = deepcopy(payload)
        self._raw_users: dict[str, dict[str, Any]] = {}
        self._accounts: list[NetworkAccount] = []

        for user in users:
            if not isinstance(user, dict):
                raise ValueError("every users item must be an object")
            account_id = str(user.get("id", "")).strip()
            username = str(user.get("username", "")).strip().lstrip("@")
            if not account_id or not username:
                raise ValueError("every user requires id and username")
            self._raw_users[account_id] = deepcopy(user)
            self._accounts.append(self._normalize_user(user, account_id, username))

    @property
    def raw_payload(self) -> dict[str, Any]:
        return deepcopy(self._payload)

    def raw_user(self, account_id: str) -> dict[str, Any]:
        return deepcopy(self._raw_users[account_id])

    async def get_following(self, username: str) -> list[NetworkAccount]:
        normalized = username.strip().lstrip("@")
        if normalized != self.target_label:
            raise ValueError(f"payload targetLabel is {self.target_label!r}, not {normalized!r}")
        return [account.model_copy(deep=True) for account in self._accounts]

    @staticmethod
    def _normalize_user(user: dict[str, Any], account_id: str, username: str) -> NetworkAccount:
        created_at = user.get("created_at")
        parsed_created_at = None
        if isinstance(created_at, str) and created_at.strip():
            parsed_created_at = datetime.strptime(created_at, _X_CREATED_AT_FORMAT)

        return NetworkAccount(
            id=account_id,
            username=username,
            display_name=user.get("display_name"),
            description=user.get("description"),
            followers_count=user.get("followers_count"),
            following_count=user.get("followings_count", user.get("following_count")),
            tweets_count=user.get("tweets_count"),
            created_at=parsed_created_at,
            verified=bool(user.get("verified", False)),
            protected=bool(user.get("protected", False)),
            profile_image_url=user.get("profile_image_url"),
        )
