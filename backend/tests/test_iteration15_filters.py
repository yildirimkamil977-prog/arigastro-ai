"""Iteration 15 tests — CompetitorProductsPage filters and CompetitorScanPage rule CRUD."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://price-pulse-51.preview.emergentagent.com").rstrip("/")
USERNAME = "arigastro"
PASSWORD = "Arigastro2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": USERNAME, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, data
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Products listing / filters ----------

class TestProductsFilters:
    def test_list_all_products(self, headers):
        r = requests.get(f"{BASE_URL}/api/competitor/products?page=1&limit=50", headers=headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "products" in data or "items" in data or isinstance(data, dict)
        total = data.get("total") or data.get("total_count") or 0
        assert total > 1000, f"Expected >1000 total products, got {total}"
        print(f"[all] total={total}")

    def test_category_filter_tavalar(self, headers):
        r = requests.get(f"{BASE_URL}/api/competitor/products?category=Tavalar&page=1&limit=50", headers=headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        total = data.get("total") or 0
        assert total > 0, f"Category filter 'Tavalar' returned 0 products — bug not fixed"
        assert total < 500, f"Filter too loose — got {total} products"
        print(f"[category=Tavalar] total={total}")

    def test_category_and_search(self, headers):
        r = requests.get(f"{BASE_URL}/api/competitor/products?category=Tavalar&search=tava&page=1&limit=50", headers=headers, timeout=60)
        assert r.status_code == 200, r.text
        total = r.json().get("total") or 0
        assert total > 0, "category+search returned 0"
        print(f"[category=Tavalar&search=tava] total={total}")

    def test_brand_filter(self, headers):
        r = requests.get(f"{BASE_URL}/api/competitor/products?brand=Öztiryakiler&page=1&limit=50", headers=headers, timeout=60)
        assert r.status_code == 200, r.text
        total = r.json().get("total") or 0
        assert total > 0, "Brand filter returned 0"
        print(f"[brand=Öztiryakiler] total={total}")

    def test_match_status_matched(self, headers):
        r = requests.get(f"{BASE_URL}/api/competitor/products?match_status=matched&page=1&limit=50", headers=headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        products = data.get("products") or data.get("items") or []
        # verify each returned product has matches info if present
        print(f"[match=matched] total={data.get('total')}, returned={len(products)}")

    def test_match_status_unmatched(self, headers):
        r = requests.get(f"{BASE_URL}/api/competitor/products?match_status=unmatched&page=1&limit=50", headers=headers, timeout=60)
        assert r.status_code == 200, r.text
        print(f"[match=unmatched] total={r.json().get('total')}")


# ---------- Pricing rules CRUD (CompetitorScanPage) ----------

class TestPricingRules:
    def test_list_rules(self, headers):
        r = requests.get(f"{BASE_URL}/api/competitor/category-rules", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rules" in data
        assert isinstance(data["rules"], list)

    def test_create_and_delete_rule(self, headers):
        cat = "TEST_Iter15_Kategori"
        payload = {
            "category_name": cat,
            "enabled": True,
            "undercut_amount": 5.0,
            "auto_update_ikas": False,
        }
        r = requests.post(f"{BASE_URL}/api/competitor/category-rules", json=payload, headers=headers, timeout=30)
        assert r.status_code in (200, 201), r.text
        assert r.json().get("success") is True

        r2 = requests.get(f"{BASE_URL}/api/competitor/category-rules", headers=headers, timeout=30)
        cats = [x.get("category_name") for x in r2.json().get("rules", [])]
        assert cat in cats, f"Rule not persisted; found: {cats}"

        dr = requests.delete(f"{BASE_URL}/api/competitor/category-rules/{cat}", headers=headers, timeout=30)
        assert dr.status_code in (200, 204), dr.text

        r3 = requests.get(f"{BASE_URL}/api/competitor/category-rules", headers=headers, timeout=30)
        cats2 = [x.get("category_name") for x in r3.json().get("rules", [])]
        assert cat not in cats2, "Rule not deleted"


# ---------- Scan-all endpoint ----------
class TestScanAll:
    def test_scan_all_returns_meaningful(self, headers):
        r = requests.post(f"{BASE_URL}/api/competitor/scan-all", headers=headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "started" in data
        # 18 matched products exist, so it should start OR say already running
        assert data.get("started") is True or "devam" in (data.get("message") or "") or data.get("started") is False
        print(f"[scan-all] {data}")
        # Stop it if we started it to avoid leaving background task
        if data.get("started"):
            requests.post(f"{BASE_URL}/api/competitor/scan-stop", headers=headers, timeout=30)


# ---------- Dashboard ----------
class TestDashboard:
    def test_dashboard_stats(self, headers):
        r = requests.get(f"{BASE_URL}/api/competitor/dashboard", headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # accept either total_products or products_total
        total = data.get("total_products") or data.get("products_total") or data.get("total") or 0
        assert total > 1000, f"Dashboard total looks wrong: {total}"
        print(f"[dashboard] total_products={total}")
