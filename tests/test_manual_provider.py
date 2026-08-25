import asyncio

import pytest

from xni.providers.manual import ManualImportProvider


def test_manual_provider_maps_sorsa_following_payload():
    payload = {
        "users": [{
            "id": "123",
            "username": "alice",
            "display_name": "Alice",
            "description": "AI researcher",
            "followers_count": 10,
            "followings_count": 4,
            "created_at": "Sun Nov 05 08:05:40 +0000 2023",
            "tweets_count": 20,
            "verified": False,
            "protected": False,
            "profile_image_url": "https://example.com/a.jpg",
        }],
        "targetLabel": "target_user",
        "mode": "following",
    }

    provider = ManualImportProvider(payload)
    accounts = asyncio.run(provider.get_following("target_user"))

    assert provider.target_label == "target_user"
    assert accounts[0].id == "123"
    assert accounts[0].following_count == 4
    assert accounts[0].created_at.year == 2023
    assert provider.raw_user("123")["display_name"] == "Alice"


def test_manual_provider_rejects_non_following_payload():
    with pytest.raises(ValueError, match="following"):
        ManualImportProvider({"users": [], "targetLabel": "target_user", "mode": "followers"})
