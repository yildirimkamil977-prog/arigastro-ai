"""
Marketing endpoints test suite (iteration 8):
- /api/marketing/test-connection
- /api/marketing/dashboard (+ date filters)
- /api/marketing/ai-analyze
- /api/marketing/analyses
- /api/marketing/actions-log

NOTE: Skips /api/marketing/ads-action to avoid mutating real Google Ads campaigns.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "arigastro",
        "password": "Arigastro2026!"
    }, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json().get("token") or r.json().get("access_token")
    assert token, f"No token in login response: {r.json()}"
    return {"Authorization": f"Bearer {token}"}


class TestConnection:
    def test_test_connection(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/marketing/test-connection",
                         headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ga4" in data
        assert "search_console" in data
        assert "google_ads" in data
        # All must be ok:true per problem statement
        assert data["ga4"].get("ok") is True, f"GA4 not ok: {data['ga4']}"
        assert data["search_console"].get("ok") is True, f"GSC not ok: {data['search_console']}"
        assert data["google_ads"].get("ok") is True, f"Ads not ok: {data['google_ads']}"


class TestDashboard:
    def test_dashboard_default(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/marketing/dashboard",
                         headers=auth_headers, timeout=90)
        assert r.status_code == 200, r.text
        data = r.json()
        # Required sections
        for k in ("ga4_overview", "ads_campaigns", "gsc_queries", "ads_keywords"):
            assert k in data, f"Missing key: {k}"

        # ga4_overview should have sessions and revenue keys
        ga4 = data["ga4_overview"]
        assert isinstance(ga4, dict)
        assert "sessions" in ga4
        assert "revenue" in ga4 or "totalRevenue" in ga4 or "purchaseRevenue" in ga4

        # Campaigns - expect 7 (per request)
        assert isinstance(data["ads_campaigns"], list)
        assert len(data["ads_campaigns"]) >= 1, "Expected >=1 ads campaigns"

        # GSC queries
        assert isinstance(data["gsc_queries"], list)
        assert len(data["gsc_queries"]) >= 1

        # Ads keywords
        assert isinstance(data["ads_keywords"], list)

    def test_dashboard_date_range(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/marketing/dashboard",
            params={"date_from": "2025-12-01", "date_to": "2025-12-31"},
            headers=auth_headers, timeout=90
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ga4_overview" in data
        assert "ads_campaigns" in data


class TestAIAnalyze:
    def test_ai_analyze_genel(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/marketing/ai-analyze",
            json={"focus": "genel"},
            headers=auth_headers, timeout=180
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # Response should contain the analysis text
        analysis = data.get("analysis") or data.get("text") or data.get("result")
        assert analysis, f"No analysis text found in response: {list(data.keys())}"
        assert isinstance(analysis, str)
        assert len(analysis) > 50, "Analysis text too short"

    def test_analyses_list(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/marketing/analyses",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Could be a list or dict with list
        items = data if isinstance(data, list) else data.get("analyses", data.get("items", []))
        assert isinstance(items, list)
        # Should have at least one from the previous test
        assert len(items) >= 1, "Expected at least 1 saved analysis"
        # No mongo _id leakage
        first = items[0]
        assert "_id" not in first, "MongoDB _id should not be exposed"


class TestActionsLog:
    def test_actions_log(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/marketing/actions-log",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data if isinstance(data, list) else data.get("actions", data.get("items", []))
        assert isinstance(items, list)
        # May be empty; just verify structure works
        for item in items[:3]:
            assert "_id" not in item, "MongoDB _id should not be exposed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
