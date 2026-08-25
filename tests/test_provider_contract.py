from xni.providers.base import NetworkAccount


def test_network_account_requires_id_and_username() -> None:
    account = NetworkAccount(id="1", username="example")
    assert account.id == "1"
    assert account.username == "example"
