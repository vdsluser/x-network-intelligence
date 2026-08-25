from fastapi.testclient import TestClient
from xni.app import create_app
from xni.config import Settings


def _user(account_id, username, description):
    return {
        "id": account_id,
        "username": username,
        "display_name": username.title(),
        "description": description,
        "followers_count": 100,
        "followings_count": 500,
        "created_at": "Sun Nov 05 08:05:40 +0000 2023",
        "tweets_count": 20,
        "verified": False,
        "protected": False,
        "profile_image_url": None,
    }


def test_fingerprint_api_reads_selected_classifier_version(tmp_path):
    settings = Settings(database_path=tmp_path / "xni.db")
    with TestClient(create_app(settings)) as client:
        imported = client.post("/api/import/manual/batch", json={
            "payloads": [
                {"targetLabel":"alpha","mode":"following","users":[
                    _user("1","ai_one","AI researcher | Python | @ExampleAI"),
                    _user("2","news_one","경제 전문 기자 | 뉴스룸"),
                ]},
                {"targetLabel":"beta","mode":"following","users":[
                    _user("1","ai_one","AI researcher | Python | @ExampleAI"),
                ]},
            ],
            "min_shared": 1,
        })
        assert imported.status_code == 200
        classified = client.post("/api/analysis/classify", json={"classifier_version":"rule-v1","replace_version":True})
        assert classified.status_code == 200
        fp = client.get("/api/analysis/fingerprints/alpha?classifier_version=rule-v1")
        assert fp.status_code == 200
        body = fp.json()
        assert body["following_count"] == 2
        assert any(row["topic"] == "AI" for row in body["topic_distribution"])
        assert body["classified_account_count"] == 2
        assert body["classifier_version"] == "rule-v1"

        unsupported = client.get("/api/analysis/fingerprints/alpha?classifier_version=rule-v2")
        assert unsupported.status_code == 400
