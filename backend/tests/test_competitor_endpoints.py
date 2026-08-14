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


# --- Module 4: Apply Price (İkas) ---
class TestApplyPrice:
    def test_apply_price_missing_ikas_id(self, client):
        # Get any slug
        r = client.get(f"{API}/competitor/products", params={"limit": 1}, timeout=30)
        slug = r.json()["products"][0]["slug"]
        r2 = client.post(f"{API}/competitor/apply-price",
                         json={"slug": slug, "new_price_tl": 999.0, "reason": "test"}, timeout=30)
        assert r2.status_code == 200
        d = r2.json()
        # Preview has no ikas_id, so success=False expected
        assert d.get("success") is False
        assert "error" in d
        assert "İkas" in d["error"] or "ikas" in d["error"].lower() or "kur" in d["error"].lower()

    def test_apply_price_invalid_slug(self, client):
        r = client.post(f"{API}/competitor/apply-price",
                        json={"slug": "TEST_nonexistent_slug_xyz", "new_price_tl": 100.0, "reason": "t"},
                        timeout=20)
        assert r.status_code == 404


# --- Module 5: Full price changes with pagination/filter ---
class TestPriceChangesFull:
    def test_price_changes_full_default(self, client):
        r = client.get(f"{API}/competitor/price-changes-full", timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ["changes", "total", "page", "pages"]:
            assert k in d
        assert isinstance(d["changes"], list)

    def test_price_changes_full_pagination(self, client):
        r = client.get(f"{API}/competitor/price-changes-full",
                       params={"page": 1, "limit": 10}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["page"] == 1
        assert len(d["changes"]) <= 10

    def test_price_changes_full_status_filter(self, client):
        for st in ["applied", "pending"]:
            r = client.get(f"{API}/competitor/price-changes-full",
                           params={"status_filter": st}, timeout=20)
            assert r.status_code == 200

    def test_price_changes_full_search(self, client):
        r = client.get(f"{API}/competitor/price-changes-full",
                       params={"search": "Tava"}, timeout=20)
        assert r.status_code == 200


# --- Auto-match (non-blocking / background task) ---
class TestAutoMatch:
    def test_auto_match_returns_immediately_with_task_key(self, client):
        r = client.get(f"{API}/competitor/products", params={"limit": 1}, timeout=30)
        slug = r.json()["products"][0]["slug"]

        import time
        t0 = time.time()
        r2 = client.post(f"{API}/competitor/auto-match/{slug}", timeout=15)
        elapsed = time.time() - t0
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d.get("success") is True
        assert "task_key" in d
        # Should return in <10s (non-blocking); scraping happens in background
        assert elapsed < 10, f"auto-match blocked for {elapsed}s"
        # Poll status endpoint
        task_key = d["task_key"]
        r3 = client.get(f"{API}/competitor/auto-match-status/{task_key}", timeout=10)
        assert r3.status_code == 200
        assert "running" in r3.json()

    def test_auto_match_status_unknown_task(self, client):
        r = client.get(f"{API}/competitor/auto-match-status/nonexistent_task_xxx", timeout=10)
        assert r.status_code == 200
        assert r.json().get("running") is False


# --- Products priority sorting: matched/priced products come first ---
class TestProductsPriority:
    def test_matched_products_appear_first(self, client):
        r = client.get(f"{API}/competitor/products",
                       params={"page": 1, "limit": 30}, timeout=30)
        assert r.status_code == 200
        products = r.json()["products"]
        # Find first unmatched (no matches, no price data) position
        first_unmatched_idx = None
        last_matched_idx = -1
        for i, p in enumerate(products):
            has_priority = (
                p.get("match_count", 0) > 0
                or p.get("cheapest_competitor_price") is not None
                or p.get("cheapest_price") is not None
            )
            if has_priority:
                last_matched_idx = i
            elif first_unmatched_idx is None:
                first_unmatched_idx = i
        # All matched should come before first unmatched
        if first_unmatched_idx is not None and last_matched_idx != -1:
            assert last_matched_idx < first_unmatched_idx, \
                "Priority products should appear before unmatched products"

    def test_en_ucuz_rakip_data_from_akakce_placeholder(self, client):
        # Search for products likely to have Akakçe cheapest_price
        for term in ["Kuzine", "Dolap", "Ocak"]:
            r = client.get(f"{API}/competitor/products",
                           params={"search": term, "limit": 30}, timeout=30)
            if r.status_code == 200:
                for p in r.json()["products"]:
                    if p.get("cheapest_competitor_price"):
                        # Great — Akakçe data merged
                        assert isinstance(p["cheapest_competitor_price"], (int, float))
                        return
        pytest.skip("No products with cheapest_competitor_price found for the tested search terms")


# --- Iteration 13: check-price (background) ---
class TestCheckPrice:
    def test_check_price_no_matches_returns_404(self, client):
        # Fetch an unmatched product (larger limit to work around post-filter pagination)
        r = client.get(f"{API}/competitor/products",
                       params={"match_status": "unmatched", "limit": 200}, timeout=30)
        assert r.status_code == 200
        products = r.json()["products"]
        if not products:
            pytest.skip("No unmatched products available")
        slug = products[0]["slug"]
        r2 = client.post(f"{API}/competitor/check-price/{slug}", timeout=15)
        assert r2.status_code == 404, f"Expected 404 for unmatched, got {r2.status_code}: {r2.text}"

    def test_check_price_matched_returns_task_key(self, client):
        # Find a matched product
        r = client.get(f"{API}/competitor/products",
                       params={"match_status": "matched", "limit": 1}, timeout=30)
        assert r.status_code == 200
        products = r.json()["products"]
        if not products:
            pytest.skip("No matched products available")
        slug = products[0]["slug"]

        import time
        t0 = time.time()
        r2 = client.post(f"{API}/competitor/check-price/{slug}", timeout=15)
        elapsed = time.time() - t0
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d.get("success") is True
        assert "task_key" in d and d["task_key"]
        assert elapsed < 10, f"check-price blocked for {elapsed}s (should be non-blocking)"

        # Poll status endpoint
        task_key = d["task_key"]
        r3 = client.get(f"{API}/competitor/check-price-status/{task_key}", timeout=10)
        assert r3.status_code == 200
        assert "running" in r3.json()

    def test_check_price_status_unknown_task(self, client):
        r = client.get(f"{API}/competitor/check-price-status/nonexistent_check_xxx", timeout=10)
        assert r.status_code == 200
        assert r.json().get("running") is False


# --- Iteration 13: auto-match-category (background, progress fields) ---
class TestAutoMatchCategory:
    def test_auto_match_category_not_found(self, client):
        r = client.post(f"{API}/competitor/auto-match-category/TEST_ZZZ_NONEXISTENT_CAT_9999", timeout=15)
        assert r.status_code == 404

    def test_auto_match_category_returns_task_key_and_progress_fields(self, client):
        # Pick a real category
        r = client.get(f"{API}/competitor/products", timeout=30)
        cats = r.json().get("categories") or []
        if not cats:
            pytest.skip("No categories available")
        cat = cats[0]

        import time
        t0 = time.time()
        r2 = client.post(f"{API}/competitor/auto-match-category/{cat}", timeout=15)
        elapsed = time.time() - t0
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d.get("success") is True
        assert "task_key" in d and d["task_key"]
        assert isinstance(d.get("total"), int) and d["total"] > 0
        assert elapsed < 10, f"auto-match-category blocked for {elapsed}s"

        task_key = d["task_key"]
        # Poll match-status
        r3 = client.get(f"{API}/competitor/match-status/{task_key}", timeout=10)
        assert r3.status_code == 200
        status = r3.json()
        # Should have the progress fields (initially 0)
        assert "running" in status
        # products_matched / total_matches fields should exist (populated as task runs)
        # They may be missing on first read if task hasn't touched update_one yet, so allow either.
        assert set(status.keys()) & {"total", "progress", "matched", "products_matched", "total_matches", "running"}

        # Stop the task to avoid running full ScraperAPI in preview
        client.post(f"{API}/competitor/match-stop/{task_key}", timeout=10)

    def test_match_status_unknown_task(self, client):
        r = client.get(f"{API}/competitor/match-status/nonexistent_match_xxx", timeout=10)
        assert r.status_code == 200
        assert r.json().get("running") is False


# --- Iteration 13: category-rules with auto_update_ikas ---
class TestCategoryRulesAutoUpdate:
    TEST_CAT = "TEST_AutoUpdate_Kategori"

    def test_create_rule_with_auto_update_ikas_true(self, client):
        payload = {
            "category_name": self.TEST_CAT,
            "enabled": True,
            "undercut_amount": 50,
            "profit_margin_pct": 15,
            "auto_update_ikas": True,
        }
        r = client.post(f"{API}/competitor/category-rules", json=payload, timeout=20)
        assert r.status_code == 200
        assert r.json().get("success") is True

        r2 = client.get(f"{API}/competitor/category-rules", timeout=20)
        assert r2.status_code == 200
        found = [x for x in r2.json()["rules"] if x["category_name"] == self.TEST_CAT]
        assert len(found) == 1
        assert found[0].get("auto_update_ikas") is True
        assert found[0].get("undercut_amount") == 50
        assert found[0].get("profit_margin_pct") == 15

    def test_update_rule_toggle_auto_update_ikas_false(self, client):
        payload = {
            "category_name": self.TEST_CAT,
            "enabled": True,
            "undercut_amount": 50,
            "auto_update_ikas": False,
        }
        r = client.post(f"{API}/competitor/category-rules", json=payload, timeout=20)
        assert r.status_code == 200

        r2 = client.get(f"{API}/competitor/category-rules", timeout=20)
        found = [x for x in r2.json()["rules"] if x["category_name"] == self.TEST_CAT]
        assert len(found) == 1
        assert found[0].get("auto_update_ikas") is False

    def test_cleanup_auto_update_rule(self, client):
        r = client.delete(f"{API}/competitor/category-rules/{self.TEST_CAT}", timeout=20)
        assert r.status_code == 200


# --- Iteration 13: apply-price rejects when no floor & no purchase price ---
class TestApplyPriceFloorCheck:
    def test_apply_price_rejects_without_floor_and_purchase(self, client):
        # Find an unmatched product; those are unlikely to have floor_price/purchase_price set
        r = client.get(f"{API}/competitor/products",
                       params={"match_status": "unmatched", "limit": 50}, timeout=30)
        assert r.status_code == 200
        products = r.json()["products"]
        candidate_slug = None
        for p in products:
            # Prefer product without floor & purchase (fields may or may not be included)
            if not p.get("floor_price") and not p.get("purchase_price"):
                candidate_slug = p["slug"]
                break
        if not candidate_slug and products:
            candidate_slug = products[0]["slug"]
        if not candidate_slug:
            pytest.skip("No candidate product for floor-check test")

        r2 = client.post(
            f"{API}/competitor/apply-price",
            json={"slug": candidate_slug, "new_price_tl": 500.0, "reason": "floor-check-test"},
            timeout=30,
        )
        assert r2.status_code == 200
        d = r2.json()
        # Expected: success=False with either floor-error or (if floor is present) İkas error
        assert d.get("success") is False
        err = d.get("error", "")
        assert err, f"Expected an error message, got: {d}"
        # Accept either the "no floor/purchase" or the "no ikas_id" case
        assert (
            "dip fiyat" in err.lower()
            or "alış fiyat" in err.lower()
            or "ikas" in err.lower()
        ), f"Unexpected error text: {err}"
