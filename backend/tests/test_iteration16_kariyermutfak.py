"""Iteration 16 — verify Kariyer Mutfak scraping config + core review endpoints."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://price-pulse-51.preview.emergentagent.com").rstrip("/")
USERNAME = "arigastro"
PASSWORD = "Arigastro2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": USERNAME, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"No token in response: {data}"
    return tok


@pytest.fixture
def headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- Auth / health ---
class TestAuth:
    def test_login_returns_jwt(self, token):
        # JWT is 3 dot-separated base64 segments
        assert token.count(".") == 2

    def test_me(self, headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=15)
        assert r.status_code == 200
        assert r.json().get("username") == USERNAME


# --- Review endpoints ---
class TestReviewEndpoints:
    def test_category_rules(self, headers):
        r = requests.get(f"{BASE_URL}/api/competitor/category-rules", headers=headers, timeout=20)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_products_list(self, headers):
        r = requests.get(f"{BASE_URL}/api/competitor/products?page=1&limit=10",
                         headers=headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "total" in data
        assert isinstance(data["total"], int)
        # products key may be 'products' or 'items'
        items = data.get("products") or data.get("items") or []
        assert isinstance(items, list)

    def test_dashboard_stats(self, headers):
        r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, dict)
        assert len(data.keys()) > 0


# --- Kariyer Mutfak code-level checks ---
class TestKariyerMutfakConfig:
    def test_competitor_dict_entry(self):
        from competitor_pricing import COMPETITORS
        assert "kariyermutfak" in COMPETITORS
        c = COMPETITORS["kariyermutfak"]
        assert c.get("scrape_needs_ultra_premium") is True
        assert "/Arama?src=" in c.get("search_url", "")
        assert c.get("domain") == "www.kariyermutfak.com"

    def test_scrape_uses_ultra_premium(self):
        import inspect
        from competitor_pricing import scrape_competitor_price
        src = inspect.getsource(scrape_competitor_price)
        assert "scrape_needs_ultra_premium" in src or "needs_ultra" in src
        assert 'ultra_premium' in src and '"true"' in src

    def test_price_selectors_present(self):
        import inspect
        from competitor_pricing import _extract_price
        src = inspect.getsource(_extract_price)
        for sel in [".discountPriceSpan", ".discountPrice", "#kdvliFiyat", ".productPrice"]:
            assert sel in src, f"Missing selector: {sel}"

    def test_search_skips_ultra_premium_sites(self):
        import inspect
        from competitor_pricing import _search_on_site
        src = inspect.getsource(_search_on_site)
        assert "scrape_needs_ultra_premium" in src
        # returns [] for ultra sites
        assert "return []" in src


# --- Scheduler timezone ---
class TestScheduler:
    def test_server_configures_istanbul_tz(self):
        with open("/app/backend/server.py", "r") as f:
            src = f.read()
        assert 'Europe/Istanbul' in src
        # scheduler timezone or job timezones use TR
        assert re.search(r'pytz_tz\(["\']Europe/Istanbul["\']\)', src) or \
               'timezone="Europe/Istanbul"' in src
