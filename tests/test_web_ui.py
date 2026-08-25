from fastapi.testclient import TestClient
from xni.app import create_app
from xni.config import Settings


def test_root_and_static_assets_are_local(tmp_path):
    with TestClient(create_app(Settings(database_path=tmp_path/"xni.db"))) as client:
        root = client.get("/")
        app_js = client.get("/static/app.js")
        css = client.get("/static/styles.css")
        vendor = client.get("/static/vendor/cytoscape.min.js")
    assert root.status_code == 200
    html = root.text
    assert 'id="cy"' in html
    assert '/static/app.js' in html
    assert '/static/styles.css' in html
    assert '/static/vendor/cytoscape.min.js' in html
    assert "unpkg" not in html and "jsdelivr" not in html and "cdnjs" not in html
    assert app_js.status_code == 200
    assert css.status_code == 200
    assert vendor.status_code == 200
    assert "cytoscape" in vendor.text.lower()


def test_ui_contains_filter_and_detail_contract(tmp_path):
    with TestClient(create_app(Settings(database_path=tmp_path/"xni.db"))) as client:
        html = client.get("/").text
        js = client.get("/static/app.js").text
    for marker in ["target-filter","topic-filter","type-filter","new-only","coverage-filter","search-input","layout-select","detail-panel","status-banner","empty-state"]:
        assert marker in html
    for marker in ["/api/graph", "/api/graph/options", "/api/analysis/fingerprints/", "/api/accounts/", "cose", "concentric", "breadthfirst", "grid"]:
        assert marker in js
