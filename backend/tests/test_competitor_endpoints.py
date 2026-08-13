"""Backend tests for competitor price tracking endpoints (Modules 1-3)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://price-pulse-51.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

USERNAME = "arigastro"
PASSWORD = "Arigastro2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"username": USERNAME, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# --- Products listing / filters ---
class TestProductsListing:
    def test_list_products_default(self, client):
        r = client.get(f"{API}/competitor/products", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "products" in d and isinstance(d["products"], list)
        assert "total" in d and d["total"] > 0
        assert "categories" in d and isinstance(d["categories"], list)
        assert "sub_categories" in d and isinstance(d["sub_categories"], list)
        assert "brands" in d and isinstance(d["brands"], list)
        # Per problem statement: 9 top-level, 79 sub, 55 brands
        assert len(d["categories"]) >= 5, f"Expected >=5 top categories, got {len(d['categories'])}"
        assert len(d["brands"]) >= 20, f"Expected many brands, got {len(d['brands'])}"
        p = d["products"][0]
        # Product structure
        assert "slug" in p and "name" in p
        assert "match_count" in p
        assert "category" in p  # parsed from category_path

    def test_search_filter(self, client):
        r = client.get(f"{API}/competitor/products", params={"search": "Tava"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        # Every product should contain 'tava' (case-insensitive)
        for p in d["products"][:10]:
            assert "tava" in p["name"].lower()

    def test_category_filter(self, client):
        r = client.get(f"{API}/competitor/products", timeout=30)
        cats = r.json()["categories"]
        if not cats:
            pytest.skip("No categories available")
        cat = cats[0]
        r2 = client.get(f"{API}/competitor/products", params={"category": cat}, timeout=30)
        assert r2.status_code == 200
        d = r2.json()
        assert len(d["products"]) >= 0

    def test_brand_filter(self, client):
        r = client.get(f"{API}/competitor/products", timeout=30)
        brands = r.json()["brands"]
        if not brands:
            pytest.skip("No brands")
        brand = brands[0]
        r2 = client.get(f"{API}/competitor/products", params={"brand": brand}, timeout=30)
        assert r2.status_code == 200
        d = r2.json()
        for p in d["products"][:10]:
            assert (p.get("brand") or "").lower() == brand.lower()

    def test_match_status_matched(self, client):
        r = client.get(f"{API}/competitor/products", params={"match_status": "matched"}, timeout=30)
        assert r.status_code == 200
        for p in r.json()["products"][:10]:
            assert p["match_count"] > 0

    def test_match_status_unmatched(self, client):
        r = client.get(f"{API}/competitor/products", params={"match_status": "unmatched"}, timeout=30)
        assert r.status_code == 200
        for p in r.json()["products"][:10]:
            assert p["match_count"] == 0

    def test_pagination(self, client):
        r1 = client.get(f"{API}/competitor/products", params={"page": 1, "limit": 10}, timeout=30)
        r2 = client.get(f"{API}/competitor/products", params={"page": 2, "limit": 10}, timeout=30)
        assert r1.status_code == 200 and r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        if d1["pages"] > 1:
            slugs1 = {p["slug"] for p in d1["products"]}
            slugs2 = {p["slug"] for p in d2["products"]}
            assert slugs1 != slugs2


# --- Price settings ---
class TestPriceSettings:
    def test_update_price_settings(self, client):
        r = client.get(f"{API}/competitor/products", params={"limit": 1}, timeout=30)
        slug = r.json()["products"][0]["slug"]
        r2 = client.put(
            f"{API}/competitor/price-settings/{slug}",
            json={"floor_price": 111.5, "purchase_price": 88.25},
            timeout=20,
        )
        assert r2.status_code == 200
        assert r2.json().get("success") is True


# --- Category rules ---
class TestCategoryRules:
    TEST_CAT = "TEST_Kategori_Bir"

    def test_list_rules_initial(self, client):
        r = client.get(f"{API}/competitor/category-rules", timeout=20)
        assert r.status_code == 200
        assert "rules" in r.json()

    def test_create_rule_and_verify_persistence(self, client):
        payload = {
            "category_name": self.TEST_CAT,
            "enabled": True,
            "undercut_amount": 100,
            "profit_margin_pct": 20,
            "scan_hour": 3,
        }
        r = client.post(f"{API}/competitor/category-rules", json=payload, timeout=20)
        assert r.status_code == 200
        # Verify via GET
        r2 = client.get(f"{API}/competitor/category-rules", timeout=20)
        rules = r2.json()["rules"]
        found = [x for x in rules if x["category_name"] == self.TEST_CAT]
        assert len(found) == 1
        assert found[0]["undercut_amount"] == 100
        assert found[0]["profit_margin_pct"] == 20

    def test_delete_rule(self, client):
        r = client.delete(f"{API}/competitor/category-rules/{self.TEST_CAT}", timeout=20)
        assert r.status_code == 200
        r2 = client.get(f"{API}/competitor/category-rules", timeout=20)
        assert not any(x["category_name"] == self.TEST_CAT for x in r2.json()["rules"])


# --- Dashboard ---
class TestDashboard:
    def test_dashboard_stats(self, client):
        r = client.get(f"{API}/competitor/dashboard", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for key in ["total_products", "matched_products", "cheaper_count", "recommend_count", "category_rules"]:
            assert key in d
        assert isinstance(d["category_rules"], list)


# --- Scan controls ---
class TestScan:
    def test_scan_status(self, client):
        r = client.get(f"{API}/competitor/scan-status", timeout=20)
        assert r.status_code == 200

    def test_scan_all_starts(self, client):
        # Only call trigger; ScraperAPI will fail but scan should start
        r = client.post(f"{API}/competitor/scan-all", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "started" in d or "message" in d
        # Try to stop it
        client.post(f"{API}/competitor/scan-stop", timeout=20)


# --- Price changes ---
class TestPriceChanges:
    def test_list_price_changes(self, client):
        r = client.get(f"{API}/competitor/price-changes", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "changes" in d and "total" in d
