"""
Iteration 9 - Reports endpoint tests (Analiz & Rapor page)
Tests all GET /api/reports/* endpoints. Skips POST /api/reports/ai-report (OpenAI cost).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "arigastro",
        "password": "Arigastro2026!"
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"No token in response: {r.json()}"
    return {"Authorization": f"Bearer {token}"}


class TestReportsEndpoints:
    def test_search_terms(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/reports/search-terms", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0, "No search terms returned"
        row = data[0]
        for field in ["term", "clicks", "cost", "conversions", "roas"]:
            assert field in row, f"Missing '{field}' in row keys: {list(row.keys())}"

    def test_quality_scores(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/reports/quality-scores", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        row = data[0]
        for field in ["quality_score", "expected_ctr", "creative_quality", "landing_page_quality"]:
            assert field in row, f"Missing '{field}' in keys: {list(row.keys())}"

    def test_competition(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/reports/competition", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        row = data[0]
        for field in ["impression_share", "lost_is_rank", "lost_is_budget"]:
            assert field in row, f"Missing '{field}' in keys: {list(row.keys())}"

    def test_device_performance(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/reports/device-performance", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        devices = {row.get("device") for row in data}
        # Should include at least MOBILE / DESKTOP / TABLET
        assert devices & {"MOBILE", "DESKTOP", "TABLET"}, f"Unexpected devices: {devices}"

    def test_hourly_performance(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/reports/hourly-performance", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 24, f"Expected 24 hourly entries, got {len(data)}"

    def test_ad_assets(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/reports/ad-assets", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        row = data[0]
        for field in ["field_type", "performance_label"]:
            assert field in row, f"Missing '{field}' in keys: {list(row.keys())}"

    def test_gsc_pages(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/reports/gsc-pages", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)

    def test_landing_pages(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/reports/landing-pages", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)

    def test_history(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/reports/history", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # verify no MongoDB _id leaked
        for doc in data:
            assert "_id" not in doc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
